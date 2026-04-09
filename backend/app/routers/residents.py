import json
import os
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session, defer as orm_defer

from ..database import get_db
from ..auth import get_current_user
from ..recognition import recognition_service
from .. import models, schemas

router = APIRouter(prefix="/api/residents", tags=["residents"])

DATA_DIR = os.getenv("DATA_DIR", "./data")
FACES_DIR = os.path.join(DATA_DIR, "faces")


def _ensure_faces_dir():
    os.makedirs(FACES_DIR, exist_ok=True)


@router.get("/", response_model=list[schemas.ResidentResponse])
def list_residents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    activo: Optional[bool] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(models.Resident).options(orm_defer(models.Resident.face_encoding))
    if activo is not None:
        q = q.filter(models.Resident.activo == activo)
    if search:
        q = q.filter(
            models.Resident.nombre.ilike(f"%{search}%")
            | models.Resident.apartamento.ilike(f"%{search}%")
        )
    return q.order_by(models.Resident.nombre).offset(skip).limit(limit).all()


@router.post("/", response_model=schemas.ResidentResponse, status_code=201)
def create_resident(
    data: schemas.ResidentCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    resident = models.Resident(**data.model_dump())
    db.add(resident)
    db.commit()
    db.refresh(resident)
    return resident


@router.get("/{resident_id}", response_model=schemas.ResidentResponse)
def get_resident(
    resident_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    r = db.query(models.Resident).filter(models.Resident.id == resident_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Residente no encontrado")
    return r


@router.put("/{resident_id}", response_model=schemas.ResidentResponse)
def update_resident(
    resident_id: int,
    data: schemas.ResidentUpdate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    r = db.query(models.Resident).filter(models.Resident.id == resident_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Residente no encontrado")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return r


@router.delete("/{resident_id}")
def delete_resident(
    resident_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    r = db.query(models.Resident).filter(models.Resident.id == resident_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Residente no encontrado")
    r.activo = False
    db.commit()
    return {"message": "Residente desactivado"}


@router.post("/{resident_id}/face")
async def upload_face(
    resident_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    r = db.query(models.Resident).filter(models.Resident.id == resident_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Residente no encontrado")

    _ensure_faces_dir()
    contents = await file.read()

    face_result = recognition_service.encode_face_with_metadata(contents)
    if not face_result["detected"] or face_result["encoding"] is None:
        raise HTTPException(
            status_code=422,
            detail="No se detectó ningún rostro en la imagen. Por favor usa una foto clara de frente."
        )

    # Save photo
    ext = os.path.splitext(file.filename or "photo.jpg")[1] or ".jpg"
    photo_filename = f"resident_{resident_id}{ext}"
    photo_path = os.path.join(FACES_DIR, photo_filename)
    async with aiofiles.open(photo_path, "wb") as f:
        await f.write(contents)

    import datetime as _dt
    r.foto_path = photo_path
    r.face_encoding = json.dumps(face_result["encoding"])
    r.embedding_model = face_result["model_name"]
    r.embedding_version = None
    r.embedding_created_at = _dt.datetime.utcnow()
    db.commit()

    # Reload known faces
    await recognition_service.load_known_faces(db)

    return {"message": "Rostro registrado correctamente", "foto_path": photo_path}


# Vehicle sub-resources
@router.post("/{resident_id}/vehicles", response_model=schemas.VehicleResponse, status_code=201)
def add_vehicle(
    resident_id: int,
    data: schemas.VehicleCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    r = db.query(models.Resident).filter(models.Resident.id == resident_id).first()
    if not r:
        raise HTTPException(status_code=404, detail="Residente no encontrado")
    v = models.Vehicle(resident_id=resident_id, **data.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.delete("/{resident_id}/vehicles/{vehicle_id}")
def remove_vehicle(
    resident_id: int,
    vehicle_id: int,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    v = db.query(models.Vehicle).filter(
        models.Vehicle.id == vehicle_id,
        models.Vehicle.resident_id == resident_id,
    ).first()
    if not v:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    v.activo = False
    db.commit()
    return {"message": "Vehículo eliminado"}
