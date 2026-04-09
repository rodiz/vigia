import asyncio
import json
import logging
import os
import warnings
from datetime import datetime

# Suppress PyTorch NNPACK "Unsupported hardware" C++ log (cosmetic only)
os.environ.setdefault("TORCH_CPP_LOG_LEVEL", "ERROR")
os.environ.setdefault("NNPACK_DISABLE", "1")
warnings.filterwarnings("ignore", message=".*NNPACK.*")
from pathlib import Path
from typing import Set
from zoneinfo import ZoneInfo

import cv2
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from .database import engine, get_db, SessionLocal
from . import models
from .auth import create_default_admin, get_current_user
from .camera import camera_manager
from .recognition import recognition_service
from .notifications import notification_service
from .routers import auth, residents, visitors, events, settings as settings_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BOGOTA_TZ = ZoneInfo("America/Bogota")
DATA_DIR = os.getenv("DATA_DIR", "./data")

# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="VigIA - Sistema de Vigilancia",
    description="SaaS de vigilancia para conjuntos residenciales",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Skip ngrok browser warning page on all responses
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request as StarletteRequest

class NgrokHeaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: StarletteRequest, call_next):
        response = await call_next(request)
        response.headers["ngrok-skip-browser-warning"] = "1"
        return response

app.add_middleware(NgrokHeaderMiddleware)

# Include routers
app.include_router(auth.router)
app.include_router(residents.router)
app.include_router(visitors.router)
app.include_router(events.router)
app.include_router(settings_router.router)


# ── WebSocket manager ─────────────────────────────────────────────────────────

class ConnectionManager:
    def __init__(self):
        self.camera_connections: dict[int, Set[WebSocket]] = {}
        self.event_connections: Set[WebSocket] = set()

    async def connect_camera(self, websocket: WebSocket, camera_id: int):
        await websocket.accept()
        if camera_id not in self.camera_connections:
            self.camera_connections[camera_id] = set()
        self.camera_connections[camera_id].add(websocket)

    def disconnect_camera(self, websocket: WebSocket, camera_id: int):
        if camera_id in self.camera_connections:
            self.camera_connections[camera_id].discard(websocket)

    async def connect_events(self, websocket: WebSocket):
        await websocket.accept()
        self.event_connections.add(websocket)

    def disconnect_events(self, websocket: WebSocket):
        self.event_connections.discard(websocket)

    async def broadcast_event(self, event_data: dict):
        dead = set()
        for ws in self.event_connections:
            try:
                await ws.send_json(event_data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.event_connections.discard(ws)


ws_manager = ConnectionManager()


# ── Startup / Shutdown ────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    # Create all tables
    models.Base.metadata.create_all(bind=engine)
    logger.info("Database tables created")

    # Create data directories
    os.makedirs(os.path.join(DATA_DIR, "faces"), exist_ok=True)
    os.makedirs(os.path.join(DATA_DIR, "events"), exist_ok=True)
    logger.info(f"Data directories ready at {DATA_DIR}")

    # Create default admin
    db = SessionLocal()
    try:
        create_default_admin(db)

        # Load face encodings
        await recognition_service.load_known_faces(db)

        # Load Telegram settings from DB
        token_cfg = db.query(models.SystemConfig).filter(
            models.SystemConfig.key == "telegram_bot_token"
        ).first()
        chat_cfg = db.query(models.SystemConfig).filter(
            models.SystemConfig.key == "telegram_chat_id"
        ).first()
        if token_cfg and chat_cfg:
            notification_service.update_credentials(
                token_cfg.value or "", chat_cfg.value or ""
            )

        # Start active cameras
        cameras = db.query(models.Camera).filter(models.Camera.activo == True).all()
        for cam in cameras:
            asyncio.create_task(_start_camera_task(cam.id, cam.url))

    finally:
        db.close()

    logger.info("VigIA started successfully")


@app.on_event("shutdown")
async def shutdown():
    for cam_id in list(camera_manager._streams.keys()):
        camera_manager.stop_camera(cam_id)
    logger.info("VigIA shutdown complete")


async def _start_camera_task(camera_id: int, url: str):
    """Task to open a camera with retry."""
    await asyncio.sleep(1)
    ok = await camera_manager.start_camera(camera_id, url)
    if ok:
        logger.info(f"Camera {camera_id} started")
    else:
        logger.error(f"Failed to start camera {camera_id}")


# ── Camera stream endpoint ────────────────────────────────────────────────────

@app.get("/api/cameras/{camera_id}/stream")
async def camera_stream(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """MJPEG stream endpoint."""
    cam = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    if not camera_manager.is_camera_open(camera_id):
        ok = await camera_manager.start_camera(camera_id, cam.url)
        if not ok:
            raise HTTPException(status_code=503, detail="No se puede conectar a la cámara")

    return StreamingResponse(
        camera_manager.generate_frames(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.post("/api/cameras/{camera_id}/start")
async def start_camera(
    camera_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    cam = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")
    ok = await camera_manager.start_camera(camera_id, cam.url)
    return {"success": ok, "message": "Cámara iniciada" if ok else "Error al iniciar cámara"}


@app.post("/api/cameras/{camera_id}/stop")
async def stop_camera(
    camera_id: int,
    _=Depends(get_current_user),
):
    camera_manager.stop_camera(camera_id)
    return {"message": "Cámara detenida"}


@app.get("/api/cameras/{camera_id}/snapshot")
async def camera_snapshot(
    camera_id: int,
    db: Session = Depends(get_db),
):
    """Returns a single JPEG frame from the camera."""
    cam = db.query(models.Camera).filter(models.Camera.id == camera_id).first()
    if not cam:
        raise HTTPException(status_code=404, detail="Cámara no encontrada")

    if not camera_manager.is_camera_open(camera_id):
        ok = await camera_manager.start_camera(camera_id, cam.url)
        if not ok:
            raise HTTPException(status_code=503, detail="No se puede conectar a la cámara")

    frame = camera_manager.get_raw_frame(camera_id)
    if frame is None:
        raise HTTPException(status_code=503, detail="Sin frames disponibles")

    ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 90])
    if not ok:
        raise HTTPException(status_code=500, detail="Error al capturar frame")

    return StreamingResponse(iter([buf.tobytes()]), media_type="image/jpeg")


# ── WebSocket: Camera with detection ─────────────────────────────────────────

@app.websocket("/ws/camera/{camera_id}")
async def websocket_camera(websocket: WebSocket, camera_id: int):
    """Streams processed frames + detection events."""
    await ws_manager.connect_camera(websocket, camera_id)
    db = SessionLocal()

    try:
        while True:
            if not camera_manager.is_camera_open(camera_id):
                await websocket.send_json({
                    "type": "error",
                    "message": "Cámara no disponible",
                    "timestamp": datetime.now(BOGOTA_TZ).isoformat()
                })
                await asyncio.sleep(2)
                continue

            frame = camera_manager.get_raw_frame(camera_id)
            if frame is None:
                await asyncio.sleep(0.1)
                continue

            # Process frame (rate-limited internally)
            result = await recognition_service.process_frame(frame, db)
            faces = result.get("faces", [])
            objects = result.get("objects", [])

            # Draw detections on frame
            annotated = recognition_service.draw_detections(frame, faces, objects)
            jpeg_bytes = camera_manager.encode_frame(annotated, quality=75)

            ts = datetime.now(BOGOTA_TZ).isoformat()

            # Send frame as bytes
            if jpeg_bytes:
                await websocket.send_bytes(jpeg_bytes)

            # Send detection metadata
            event = {
                "type": "detection",
                "faces": [
                    {k: v for k, v in f.items() if k != "bbox"}
                    for f in faces
                ],
                "objects": [
                    {k: v for k, v in o.items() if k != "bbox"}
                    for o in objects
                ],
                "timestamp": ts,
                "camera_id": camera_id,
            }
            await websocket.send_json(event)

            # Log detections and handle notifications
            await _handle_detections(faces, objects, frame, camera_id, db)

            await asyncio.sleep(0.1)  # ~10 fps for WS

    except WebSocketDisconnect:
        logger.info(f"WebSocket camera {camera_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket camera error: {e}")
    finally:
        ws_manager.disconnect_camera(websocket, camera_id)
        db.close()


# ── WebSocket: Events feed ────────────────────────────────────────────────────

@app.websocket("/ws/events")
async def websocket_events(websocket: WebSocket):
    """Streams access log events in real-time."""
    await ws_manager.connect_events(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(30)
            await websocket.send_json({"type": "ping", "timestamp": datetime.now(BOGOTA_TZ).isoformat()})
    except WebSocketDisconnect:
        logger.info("Events WebSocket disconnected")
    except Exception as e:
        logger.error(f"Events WebSocket error: {e}")
    finally:
        ws_manager.disconnect_events(websocket)


# ── Detection handler ─────────────────────────────────────────────────────────

_detection_cooldown: dict[str, float] = {}
DETECTION_COOLDOWN_SECONDS = 30


async def _handle_detections(
    faces: list,
    objects: list,
    frame,
    camera_id: int,
    db: Session,
):
    """Send Telegram notifications for unknown persons only. Does NOT create access logs
    — logs are created exclusively when the guard manually confirms entry/exit."""
    import time
    now = time.monotonic()

    for face in faces:
        # Only notify for unknown persons; known persons are handled when guard confirms
        if face["type"] != "unknown":
            continue

        cooldown_key = f"unknown_{camera_id}"
        last_time = _detection_cooldown.get(cooldown_key, 0)
        if now - last_time < DETECTION_COOLDOWN_SECONDS:
            continue

        _detection_cooldown[cooldown_key] = now

        image_path = await _save_snapshot(frame, camera_id)
        asyncio.create_task(
            notification_service.send_unknown_alert(image_path, objects)
        )


async def _save_snapshot(frame, camera_id: int) -> str:
    """Save annotated frame as JPEG snapshot."""
    import aiofiles

    now = datetime.now(BOGOTA_TZ)
    date_dir = os.path.join(DATA_DIR, "events", now.strftime("%Y-%m-%d"))
    os.makedirs(date_dir, exist_ok=True)

    filename = f"cam{camera_id}_{now.strftime('%H%M%S_%f')}.jpg"
    filepath = os.path.join(date_dir, filename)

    try:
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        async with aiofiles.open(filepath, "wb") as f:
            await f.write(jpeg.tobytes())
    except Exception as e:
        logger.error(f"Error saving snapshot: {e}")
        return ""

    return filepath


# ── Static files ──────────────────────────────────────────────────────────────

# Mount data directory for face photos and snapshots
data_path = Path(DATA_DIR).resolve()
if data_path.exists():
    app.mount("/data", StaticFiles(directory=str(data_path)), name="data")
    logger.info(f"Data served at /data from {data_path}")

# Mount frontend - must be done after all API routes
frontend_path = Path(__file__).parent.parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/app", StaticFiles(directory=str(frontend_path), html=True), name="frontend")
    logger.info(f"Frontend served at /app from {frontend_path}")


@app.get("/")
def root():
    return {"message": "VigIA API", "docs": "/docs", "frontend": "/app"}
