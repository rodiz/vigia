from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user, require_admin
from ..notifications import notification_service
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
def add_camera(
    data: schemas.CameraCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    cam = models.Camera(**data.model_dump())
    db.add(cam)
    db.commit()
    db.refresh(cam)
    return cam


@router.put("/cameras/{camera_id}", response_model=schemas.CameraResponse)
def update_camera(
    camera_id: int,
    data: schemas.CameraUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    cam = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(cam, field, value)
    db.commit()
    db.refresh(cam)
    return cam


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
