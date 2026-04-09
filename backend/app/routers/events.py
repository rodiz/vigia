import csv
import io
import json
import os
from datetime import datetime, date, timedelta
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..auth import get_current_user
from .. import models, schemas

router = APIRouter(prefix="/api/events", tags=["events"])

BOGOTA_TZ = ZoneInfo("America/Bogota")
UTC_TZ    = ZoneInfo("UTC")


def _bogota_date_to_utc_range(d: date):
    """Return (start_utc, end_utc) naive datetimes covering the full local date in Bogotá."""
    start = datetime(d.year, d.month, d.day, 0, 0, 0, tzinfo=BOGOTA_TZ).astimezone(UTC_TZ).replace(tzinfo=None)
    end   = datetime(d.year, d.month, d.day, 23, 59, 59, 999999, tzinfo=BOGOTA_TZ).astimezone(UTC_TZ).replace(tzinfo=None)
    return start, end


@router.get("/", response_model=list[schemas.AccessLogResponse])
def list_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    tipo: Optional[str] = None,
    visitor_id: Optional[int] = None,
    resident_id: Optional[int] = None,
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(models.AccessLog)

    if tipo:
        q = q.filter(models.AccessLog.tipo == tipo)
    if visitor_id:
        q = q.filter(models.AccessLog.visitor_id == visitor_id)
    if resident_id:
        q = q.filter(models.AccessLog.resident_id == resident_id)
    if fecha_inicio:
        start_utc, _ = _bogota_date_to_utc_range(fecha_inicio)
        q = q.filter(models.AccessLog.timestamp >= start_utc)
    if fecha_fin:
        _, end_utc = _bogota_date_to_utc_range(fecha_fin)
        q = q.filter(models.AccessLog.timestamp <= end_utc)

    if search:
        # Join visitor and resident for name search
        q = q.outerjoin(models.Visitor).outerjoin(models.Resident).filter(
            models.Visitor.nombre.ilike(f"%{search}%")
            | models.Resident.nombre.ilike(f"%{search}%")
            | models.AccessLog.notas.ilike(f"%{search}%")
        )

    return (
        q.order_by(models.AccessLog.timestamp.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )


@router.get("/stats", response_model=schemas.AccessLogStats)
def get_stats(
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    now_bogota  = datetime.now(BOGOTA_TZ)
    today       = now_bogota.date()
    month_first = today.replace(day=1)

    # Convert Bogotá day boundaries to UTC (DB stores UTC via func.now())
    today_start, _ = _bogota_date_to_utc_range(today)
    month_start, _ = _bogota_date_to_utc_range(month_first)

    accesos_hoy = db.query(func.count(models.AccessLog.id)).filter(
        models.AccessLog.timestamp >= today_start
    ).scalar() or 0

    entradas_hoy = db.query(func.count(models.AccessLog.id)).filter(
        models.AccessLog.timestamp >= today_start,
        models.AccessLog.tipo == "entrada"
    ).scalar() or 0

    salidas_hoy = db.query(func.count(models.AccessLog.id)).filter(
        models.AccessLog.timestamp >= today_start,
        models.AccessLog.tipo == "salida"
    ).scalar() or 0

    residentes_activos = db.query(func.count(models.Resident.id)).filter(
        models.Resident.activo == True
    ).scalar() or 0

    visitantes_mes = db.query(func.count(func.distinct(models.AccessLog.visitor_id))).filter(
        models.AccessLog.timestamp >= month_start,
        models.AccessLog.visitor_id != None
    ).scalar() or 0

    # Alertas = logs without visitor_id or resident_id (unknowns)
    alertas_hoy = db.query(func.count(models.AccessLog.id)).filter(
        models.AccessLog.timestamp >= today_start,
        models.AccessLog.visitor_id == None,
        models.AccessLog.resident_id == None
    ).scalar() or 0

    return schemas.AccessLogStats(
        accesos_hoy=accesos_hoy,
        residentes_activos=residentes_activos,
        visitantes_mes=visitantes_mes,
        alertas_hoy=alertas_hoy,
        entradas_hoy=entradas_hoy,
        salidas_hoy=salidas_hoy,
    )


@router.post("/manual", response_model=schemas.AccessLogResponse, status_code=201)
async def manual_log(
    request: Request,
    data: schemas.AccessLogCreate,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    log = models.AccessLog(**data.model_dump())
    db.add(log)
    db.commit()

    # Update visitor stats on entrada
    if data.visitor_id and data.tipo == "entrada":
        visitor = db.query(models.Visitor).filter(models.Visitor.id == data.visitor_id).first()
        if visitor:
            visitor.total_visitas += 1
            visitor.ultima_visita = datetime.now(BOGOTA_TZ).replace(tzinfo=None)
            db.commit()

    db.refresh(log)

    # Resolve person name and type for broadcast
    person_name = "Desconocido"
    person_type = "unknown"
    if log.resident:
        person_name = log.resident.nombre
        person_type = "resident"
    elif log.visitor:
        person_name = log.visitor.nombre
        person_type = "visitor"

    # Broadcast to dashboard WebSocket
    ws_manager = request.app.state.ws_manager if hasattr(request.app.state, 'ws_manager') else None
    if ws_manager is None:
        # fallback: import from main
        from ..main import ws_manager

    import asyncio
    asyncio.create_task(ws_manager.broadcast_event({
        "type": "access_log",
        "log_id": log.id,
        "person_type": person_type,
        "person_name": person_name,
        "tipo": data.tipo,
        "timestamp": datetime.now(BOGOTA_TZ).isoformat(),
    }))

    return log


@router.get("/export/csv")
def export_csv(
    fecha_inicio: Optional[date] = None,
    fecha_fin: Optional[date] = None,
    db: Session = Depends(get_db),
    _=Depends(get_current_user),
):
    q = db.query(models.AccessLog).order_by(models.AccessLog.timestamp.desc())
    if fecha_inicio:
        start_utc, _ = _bogota_date_to_utc_range(fecha_inicio)
        q = q.filter(models.AccessLog.timestamp >= start_utc)
    if fecha_fin:
        _, end_utc = _bogota_date_to_utc_range(fecha_fin)
        q = q.filter(models.AccessLog.timestamp <= end_utc)

    logs = q.limit(5000).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Fecha/Hora", "Tipo", "Nombre", "Confianza", "Objetos Detectados",
        "Notificacion Enviada", "Notas"
    ])

    for log in logs:
        nombre = "Desconocido"
        if log.visitor:
            nombre = log.visitor.nombre
        elif log.resident:
            nombre = log.resident.nombre

        writer.writerow([
            log.id,
            log.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
            log.tipo,
            nombre,
            f"{log.confianza_facial:.1%}" if log.confianza_facial else "",
            log.objetos_detectados or "",
            "Sí" if log.notificacion_enviada else "No",
            log.notas or "",
        ])

    output.seek(0)
    filename = f"vigia_eventos_{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
