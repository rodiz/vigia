import json
import os
from datetime import datetime
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session, defer as orm_defer

from ..database import get_db
from ..auth import get_current_user
from ..recognition import recognition_service
from .. import models, schemas

router = APIRouter(prefix="/api/visitors", tags=["visitors"])

DATA_DIR = os.getenv("DATA_DIR", "./data")
FACES_DIR = os.path.join(DATA_DIR, "faces")


def _ensure_faces_dir():
    os.makedirs(FACES_DIR, exist_ok=True)


@router.get("/", response_model=list[schemas.VisitorResponse])
def list_visitors(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(models.Visitor).options(orm_defer(models.Visitor.face_encoding))
    if search:
        q = q.filter(
            models.Visitor.nombre.ilike(f"%{search}%")
            | models.Visitor.documento.ilike(f"%{search}%")
        )
    return q.order_by(models.Visitor.ultima_visita.desc()).offset(skip).limit(limit).all()


@router.post("/", response_model=schemas.VisitorResponse, status_code=201)
def create_visitor(
    data: schemas.VisitorCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    visitor = models.Visitor(**data.model_dump())
    db.add(visitor)
    db.commit()
    db.refresh(visitor)
    return visitor


@router.get("/{visitor_id}", response_model=schemas.VisitorResponse)
def get_visitor(
    visitor_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    v = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Visitante no encontrado")
    return v


@router.put("/{visitor_id}", response_model=schemas.VisitorResponse)
def update_visitor(
    visitor_id: int,
    data: schemas.VisitorUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    v = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Visitante no encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(v, field, value)
    db.commit()
    db.refresh(v)
    return v


@router.post("/{visitor_id}/face")
async def upload_visitor_face(
    visitor_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    v = db.query(models.Visitor).filter(models.Visitor.id == visitor_id).first()
    if not v:
        raise HTTPException(status_code=404, detail="Visitante no encontrado")

    _ensure_faces_dir()
    contents = await file.read()

    face_result = recognition_service.encode_face_with_metadata(contents)
    if not face_result["detected"] or face_result["encoding"] is None:
        raise HTTPException(
            status_code=422,
            detail="No se detectó ningún rostro en la imagen"
        )

    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    photo_filename = f"visitor_{visitor_id}{ext}"
    photo_path = os.path.join(FACES_DIR, photo_filename)
    async with aiofiles.open(photo_path, "wb") as f:
        await f.write(contents)

    import datetime as _dt
    v.foto_path = photo_path
    v.face_encoding = json.dumps(face_result["encoding"])
    v.embedding_model = face_result["model_name"]
    v.embedding_version = None
    v.embedding_created_at = _dt.datetime.utcnow()
    db.commit()

    await recognition_service.load_known_faces(db)

    return {"message": "Rostro registrado correctamente", "foto_path": photo_path}


@router.post("/recognize")
async def recognize_visitor(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    """Upload an image and get recognition result."""
    import cv2
    import numpy as np

    contents = await file.read()
    nparr = np.frombuffer(contents, np.uint8)
    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if frame is None:
        raise HTTPException(status_code=422, detail="Imagen inválida")

    result = await recognition_service.process_frame(frame, db)
    faces = result.get("faces", [])
    objects = result.get("objects", [])

    if not faces:
        return schemas.RecognitionResult(
            recognized=False,
            objects_detected=objects
        )

    best = max(faces, key=lambda x: x.get("confianza", 0))
    return schemas.RecognitionResult(
        recognized=best["known"],
        person_type=best["type"] if best["known"] else "unknown",
        person_id=best.get("id"),
        nombre=best.get("nombre"),
        confianza=best.get("confianza"),
        objects_detected=objects,
    )
