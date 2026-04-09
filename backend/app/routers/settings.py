import asyncio
import urllib.request

import cv2
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user, require_admin
from ..notifications import notification_service
from ..camera import camera_manager
from .. import models, schemas

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _get_or_create_config(db: Session, key: str, default: str = "") -> models.SystemConfig:
    cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == key).first()
    if not cfg:
        cfg = models.SystemConfig(key=key, value=default)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


@router.get("/")
def get_all_settings(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    configs = db.query(models.SystemConfig).all()
    return {c.key: c.value for c in configs}


@router.put("/")
def update_settings(
    data: schemas.ConfigBulkUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    for key, value in data.settings.items():
        cfg = db.query(models.SystemConfig).filter(models.SystemConfig.key == key).first()
        if cfg:
            cfg.value = str(value)
        else:
            cfg = models.SystemConfig(key=key, value=str(value))
            db.add(cfg)

    db.commit()

    # Update services if telegram settings changed
    if "telegram_bot_token" in data.settings or "telegram_chat_id" in data.settings:
        token_cfg = db.query(models.SystemConfig).filter(
            models.SystemConfig.key == "telegram_bot_token"
        ).first()
        chat_cfg = db.query(models.SystemConfig).filter(
            models.SystemConfig.key == "telegram_chat_id"
        ).first()
        notification_service.update_credentials(
            token_cfg.value if token_cfg else "",
            chat_cfg.value if chat_cfg else ""
        )

    # Update recognition threshold if changed
    if "face_confidence_threshold" in data.settings:
        from ..recognition import recognition_service
        try:
            threshold = float(data.settings["face_confidence_threshold"])
            recognition_service.update_threshold(threshold)
        except ValueError:
            pass

    return {"message": "Configuración actualizada"}


@router.post("/test-telegram", response_model=schemas.TelegramTestResponse)
async def test_telegram(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    # Load latest credentials from DB
    token_cfg = db.query(models.SystemConfig).filter(
        models.SystemConfig.key == "telegram_bot_token"
    ).first()
    chat_cfg = db.query(models.SystemConfig).filter(
        models.SystemConfig.key == "telegram_chat_id"
    ).first()

    if not token_cfg or not chat_cfg or not token_cfg.value or not chat_cfg.value:
        return schemas.TelegramTestResponse(
            success=False,
            message="Token o Chat ID de Telegram no configurados"
        )

    notification_service.update_credentials(token_cfg.value, chat_cfg.value)
    ok = await notification_service.test_connection()

    return schemas.TelegramTestResponse(
        success=ok,
        message="Conexión exitosa - revisa tu chat de Telegram" if ok else "Error de conexión - verifica el token y chat ID"
    )


# ── Camera management ─────────────────────────────────────────────────────────

@router.get("/cameras", response_model=list[schemas.CameraResponse])
def list_cameras(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    return db.query(models.Camera).all()


@router.post("/cameras", response_model=schemas.CameraResponse, status_code=201)
async def add_camera(
    data: schemas.CameraCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    cam = models.Camera(**data.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    # Auto-start the camera immediately after creation
    await camera_manager.start_camera(cam.id, cam.url)
    return cam


@router.put("/cameras/{camera_id}", response_model=schemas.CameraResponse)
async def update_camera(
    camera_id: int,
    data: schemas.CameraUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    cam = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    url_changed = data.url is not None and data.url != cam.url
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cam, field, value)
    db.commit()
    db.refresh(cam)

    # Restart if URL changed or camera was re-activated
    if cam.activo and (url_changed or data.activo is True):
        camera_manager.stop_camera(camera_id)
        await camera_manager.start_camera(cam.id, cam.url)
    elif not cam.activo:
        camera_manager.stop_camera(camera_id)

    return cam


@router.get("/cameras/{camera_id}/status")
def camera_connection_status(
    camera_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Returns whether OpenCV is actually streaming this camera."""
    cam = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    connected = camera_manager.is_camera_open(camera_id)
    return {"camera_id": camera_id, "connected": connected, "activo": cam.activo}


@router.post("/cameras/test-url")
async def test_camera_url(
    body: dict,
    _=Depends(get_current_user),
):
    """Diagnose a camera URL: HTTP reachability + OpenCV open test."""
    url: str = body.get("url", "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL requerida")

    result = {"url": url, "http_ok": None, "opencv_ok": False, "suggestion": None}

    # 1. HTTP reachability check (only for http/https URLs)
    if url.startswith("http"):
        try:
            req = urllib.request.Request(url, method="GET")
            req.add_header("User-Agent", "VigIA/1.0")
            with urllib.request.urlopen(req, timeout=4) as resp:
                result["http_ok"] = resp.status < 400
                result["http_status"] = resp.status
        except Exception as e:
            result["http_ok"] = False
            result["http_error"] = str(e)

    # 2. OpenCV open test (run in thread to avoid blocking event loop)
    def _try_opencv(u):
        cap = cv2.VideoCapture(u)
        opened = cap.isOpened()
        if opened:
            ret, _ = cap.read()
            cap.release()
            return ret
        cap.release()
        return False

    loop = asyncio.get_event_loop()
    try:
        result["opencv_ok"] = await asyncio.wait_for(
            loop.run_in_executor(None, _try_opencv, url), timeout=6
        )
    except asyncio.TimeoutError:
        result["opencv_ok"] = False
        result["opencv_error"] = "Timeout al intentar abrir con OpenCV"

    # 3. Build suggestion
    if not result["http_ok"] and url.startswith("http"):
        result["suggestion"] = (
            "El servidor no responde. Verifica: "
            "(1) IP Webcam esté activa en el tablet, "
            "(2) La IP sea correcta, "
            "(3) Ambos dispositivos en la misma red WiFi."
        )
    elif result["http_ok"] and not result["opencv_ok"]:
        # HTTP works but OpenCV fails — suggest alternative paths
        base = url.rsplit("/", 1)[0]
        result["suggestion"] = (
            f"El servidor responde pero OpenCV no puede leer el stream. "
            f"Prueba estas URLs alternativas: "
            f"{base}/videofeed  |  {base}/mjpeg  |  {base}/video?dummy=x.mjpg"
        )
    elif result["opencv_ok"]:
        result["suggestion"] = "Conexión exitosa."

    return result


@router.delete("/cameras/{camera_id}")
def delete_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    cam = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    db.delete(cam)
    db.commit()
    return {"message": "Cámara eliminada"}
