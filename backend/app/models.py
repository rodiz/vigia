from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from .database import Base
import datetime


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), default="guard")  # admin / guard
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())


class Resident(Base):
    __tablename__ = "residents"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, index=True)
    apartamento = Column(String(20), nullable=False, index=True)
    telefono = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    foto_path = Column(String(255), nullable=True)
    face_encoding = Column(Text, nullable=True)  # JSON blob of 128 floats
    activo = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime, default=func.now())

    vehicles = relationship("Vehicle", back_populates="resident")
    access_logs = relationship("AccessLog", back_populates="resident")


class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(Integer, primary_key=True, index=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=False)
    placa = Column(String(20), nullable=False)
    marca = Column(String(50), nullable=True)
    modelo = Column(String(50), nullable=True)
    color = Column(String(30), nullable=True)
    activo = Column(Boolean, default=True)

    resident = relationship("Resident", back_populates="vehicles")


class Visitor(Base):
    __tablename__ = "visitors"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    documento = Column(String(30), nullable=True)
    telefono = Column(String(20), nullable=True)
    apartamento_destino = Column(String(20), nullable=True)  # e.g. "514"
    foto_path = Column(String(255), nullable=True)
    face_encoding = Column(Text, nullable=True)  # JSON blob
    primera_visita = Column(DateTime, default=func.now())
    ultima_visita = Column(DateTime, default=func.now())
    total_visitas = Column(Integer, default=0)

    access_logs = relationship("AccessLog", back_populates="visitor")


class AccessLog(Base):
    __tablename__ = "access_logs"

    id = Column(Integer, primary_key=True, index=True)
    visitor_id = Column(Integer, ForeignKey("visitors.id"), nullable=True, index=True)
    resident_id = Column(Integer, ForeignKey("residents.id"), nullable=True, index=True)
    tipo = Column(String(10), nullable=False, index=True)  # entrada / salida
    timestamp = Column(DateTime, default=func.now(), index=True)
    confianza_facial = Column(Float, nullable=True)
    objetos_detectados = Column(Text, nullable=True)  # JSON
    imagen_path = Column(String(255), nullable=True)
    notificacion_enviada = Column(Boolean, default=False)
    notas = Column(Text, nullable=True)

    visitor = relationship("Visitor", back_populates="access_logs")
    resident = relationship("Resident", back_populates="access_logs")


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    url = Column(String(255), nullable=False)  # rtsp:// or integer index
    activo = Column(Boolean, default=True)
    tipo = Column(String(20), default="entrada")  # entrada / salida / interior


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False)
    value = Column(Text, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
