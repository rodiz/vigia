from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
from datetime import datetime


# ── Auth ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str


class UserResponse(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserCreate(BaseModel):
    username: str
    email: Optional[str] = None
    password: str
    role: str = "guard"


class PasswordChange(BaseModel):
    current_password: str
    new_password: str


# ── Residents ─────────────────────────────────────────────────────────────────

class VehicleCreate(BaseModel):
    placa: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    color: Optional[str] = None


class VehicleResponse(BaseModel):
    id: int
    placa: str
    marca: Optional[str] = None
    modelo: Optional[str] = None
    color: Optional[str] = None
    activo: bool

    class Config:
        from_attributes = True


class ResidentCreate(BaseModel):
    nombre: str
    apartamento: str
    telefono: Optional[str] = None
    email: Optional[str] = None


class ResidentUpdate(BaseModel):
    nombre: Optional[str] = None
    apartamento: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    activo: Optional[bool] = None


class ResidentResponse(BaseModel):
    id: int
    nombre: str
    apartamento: str
    telefono: Optional[str] = None
    email: Optional[str] = None
    foto_path: Optional[str] = None
    activo: bool
    created_at: datetime
    vehicles: List[VehicleResponse] = []

    class Config:
        from_attributes = True


# ── Visitors ──────────────────────────────────────────────────────────────────

class VisitorCreate(BaseModel):
    nombre: str
    documento: Optional[str] = None
    telefono: Optional[str] = None
    apartamento_destino: Optional[str] = None


class VisitorUpdate(BaseModel):
    nombre: Optional[str] = None
    documento: Optional[str] = None
    telefono: Optional[str] = None
    apartamento_destino: Optional[str] = None


class VisitorResponse(BaseModel):
    id: int
    nombre: str
    documento: Optional[str] = None
    telefono: Optional[str] = None
    apartamento_destino: Optional[str] = None
    foto_path: Optional[str] = None
    primera_visita: datetime
    ultima_visita: datetime
    total_visitas: int

    class Config:
        from_attributes = True


# ── Access Logs ───────────────────────────────────────────────────────────────

class AccessLogCreate(BaseModel):
    visitor_id: Optional[int] = None
    resident_id: Optional[int] = None
    tipo: str  # entrada / salida
    notas: Optional[str] = None


class AccessLogResponse(BaseModel):
    id: int
    visitor_id: Optional[int] = None
    resident_id: Optional[int] = None
    tipo: str
    timestamp: datetime
    confianza_facial: Optional[float] = None
    objetos_detectados: Optional[str] = None
    imagen_path: Optional[str] = None
    notificacion_enviada: bool
    notas: Optional[str] = None
    visitor: Optional[VisitorResponse] = None
    resident: Optional[ResidentResponse] = None

    class Config:
        from_attributes = True


class AccessLogStats(BaseModel):
    accesos_hoy: int
    residentes_activos: int
    visitantes_mes: int
    alertas_hoy: int
    entradas_hoy: int
    salidas_hoy: int


# ── Cameras ───────────────────────────────────────────────────────────────────

class CameraCreate(BaseModel):
    nombre: str
    url: str
    tipo: str = "entrada"


class CameraUpdate(BaseModel):
    nombre: Optional[str] = None
    url: Optional[str] = None
    activo: Optional[bool] = None
    tipo: Optional[str] = None


class CameraResponse(BaseModel):
    id: int
    nombre: str
    url: str
    activo: bool
    tipo: str

    class Config:
        from_attributes = True


# ── Settings ──────────────────────────────────────────────────────────────────

class ConfigUpdate(BaseModel):
    key: str
    value: str


class ConfigBulkUpdate(BaseModel):
    settings: dict


class ConfigResponse(BaseModel):
    key: str
    value: Optional[str] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class TelegramTestResponse(BaseModel):
    success: bool
    message: str


# ── Recognition ───────────────────────────────────────────────────────────────

class RecognitionResult(BaseModel):
    recognized: bool
    person_type: Optional[str] = None  # resident / visitor / unknown
    person_id: Optional[int] = None
    nombre: Optional[str] = None
    confianza: Optional[float] = None
    objects_detected: List[dict] = []
