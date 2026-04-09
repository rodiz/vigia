"""
Interfaz abstracta del motor biométrico de VigIA.

Por qué existe esta abstracción
--------------------------------
El sistema original acopla directamente la lógica de reconocimiento facial
con la librería `face_recognition` (dlib). Si queremos cambiar de motor
(p.ej. a InsightFace) o agregar un motor de respaldo, tendríamos que
modificar múltiples archivos y romper contratos existentes.

Esta interfaz define el contrato que cualquier motor debe cumplir,
independientemente de la librería subyacente. El resto del sistema
habla solo con `FaceEngine`, nunca con dlib ni InsightFace directamente.

Nota de diseño: biometría como apoyo operativo
-----------------------------------------------
Este sistema está diseñado para portería, NO para control automático de acceso.

- YOLO detecta presencia de personas/objetos — NO determina identidad.
- FaceEngine sugiere una coincidencia — NO abre puertas ni toma decisiones.
- El portero siempre confirma o rechaza la sugerencia.
- Los eventos `access_accepted_by_guard` / `access_rejected_by_guard`
  son la fuente de verdad de quién entró o salió.

Esto es intencional: la biometría tiene tasas de error. Una coincidencia
al 90% aún tiene un 10% de error. En un sistema de portería residencial,
el error debe ser visible y corregible por un humano, no silencioso.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class EmbeddingResult:
    """Resultado de extraer el embedding de una imagen."""
    embedding: Optional[list]       # Vector de floats, o None si no se detectó rostro
    detected: bool                  # ¿Se encontró al menos un rostro?
    model_name: str = ""            # Nombre del modelo que generó el embedding
    embedding_dim: int = 0          # Dimensión del vector (128 para dlib, 512 para InsightFace)
    error: Optional[str] = None     # Descripción del error si falló


@dataclass
class FaceMatch:
    """
    Resultado de comparar un rostro contra la base de conocidos.

    El campo `score` es una similitud normalizada entre 0 y 1.
    No es una probabilidad exacta — es una guía para el portero.

    Un score >= threshold sugiere coincidencia, pero el portero
    siempre debe confirmar antes de registrar un acceso.
    """
    person_type: str                # "resident", "visitor" o "unknown"
    person_id: Optional[int]        # ID en la base de datos, o None si desconocido
    nombre: str                     # Nombre mostrado al portero
    score: float                    # Similitud 0–1 (mayor = más parecido)
    known: bool                     # True si supera el umbral configurado
    bbox: list = field(default_factory=list)  # [x1, y1, x2, y2] en píxeles


class FaceEngine(ABC):
    """
    Contrato que debe cumplir cualquier motor de reconocimiento facial.

    Implementaciones concretas:
      - DlibFaceEngine   → usa face_recognition + dlib (motor legacy)
      - InsightFaceEngine → usa InsightFace + ONNX Runtime (motor nuevo)

    Selección del motor: ver biometrics/factory.py
    """

    # ── Información del motor ─────────────────────────────────────────────────

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Identificador del motor. Ej: 'dlib_hog_128' o 'insightface_buffalo_s_512'."""
        ...

    @property
    @abstractmethod
    def embedding_dim(self) -> int:
        """Dimensión del vector de embedding. 128 para dlib, 512 para InsightFace."""
        ...

    # ── Operaciones principales ───────────────────────────────────────────────

    @abstractmethod
    def encode_face(self, image_bytes: bytes) -> EmbeddingResult:
        """
        Extrae el embedding facial de una imagen en bytes.

        Usado al registrar una foto de residente o visitante.
        Si no se detecta rostro, retorna EmbeddingResult(detected=False).

        Args:
            image_bytes: bytes de una imagen JPEG, PNG o similar.

        Returns:
            EmbeddingResult con el vector o indicación de fallo.
        """
        ...

    @abstractmethod
    def find_matches(
        self,
        frame: np.ndarray,
        known_encodings: list,
        known_ids: list,
        threshold: float,
    ) -> list[FaceMatch]:
        """
        Detecta rostros en un frame y los compara contra los conocidos.

        Usado en el loop de streaming de cámara para sugerir coincidencias
        al portero en tiempo real.

        Args:
            frame:            Frame BGR de OpenCV.
            known_encodings:  Lista de np.ndarray con embeddings registrados.
            known_ids:        Lista de tuplas (type, id, nombre) en mismo orden.
            threshold:        Score mínimo para considerar match (0–1).

        Returns:
            Lista de FaceMatch, uno por rostro detectado en el frame.
            Puede ser lista vacía si no hay rostros.
        """
        ...

    # ── Utilidades opcionales ─────────────────────────────────────────────────

    def is_available(self) -> bool:
        """
        Retorna True si el motor está correctamente instalado y funcional.
        Usado por factory.py para decidir si hacer fallback a dlib.
        """
        return True

    def warmup(self) -> None:
        """
        Carga modelos en memoria antes de procesar el primer frame.
        Llamado en startup para evitar latencia en el primer uso.
        Implementación opcional — los motores pueden no-op si no aplica.
        """
        pass
