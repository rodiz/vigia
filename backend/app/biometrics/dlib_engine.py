"""
DlibFaceEngine — motor biométrico legacy basado en face_recognition + dlib.

Este módulo encapsula TODA la lógica dlib/face_recognition que antes vivía
en recognition.py. No cambia el algoritmo, solo lo envuelve en la interfaz
FaceEngine para que el resto del sistema sea agnóstico al motor.

Por qué dlib sigue siendo válido
---------------------------------
- Sin dependencias de modelos externos en disco (embeddings incluidos en la librería).
- 128 dimensiones → embeddings pequeños, fáciles de almacenar.
- Funciona razonablemente bien en hardware modesto.
- Es el motor de referencia para validar InsightFace.

Limitaciones conocidas
-----------------------
- Lento en CPU para frames de alta resolución.
- No es thread-safe — requiere _DLIB_LOCK global.
- Modelo HOG funciona mal con caras de perfil, oclusión parcial, baja luz.
- face_recognition==1.3.0 depende de dlib compilado contra una versión específica
  de Boost, lo que hace la instalación frágil en algunos entornos.
"""

import logging
import threading
from typing import Optional

import cv2
import numpy as np

from .base import FaceEngine, EmbeddingResult, FaceMatch

logger = logging.getLogger(__name__)

# dlib/face_recognition no es thread-safe.
# Todos los accesos a funciones dlib deben adquirir este lock.
_DLIB_LOCK = threading.Lock()

try:
    import face_recognition as fr
    _FR_AVAILABLE = True
except ImportError:
    _FR_AVAILABLE = False
    logger.warning(
        "face_recognition no disponible — DlibFaceEngine desactivado. "
        "Instala con: pip install face-recognition"
    )


class DlibFaceEngine(FaceEngine):
    """
    Implementación del motor biométrico usando face_recognition (dlib).

    Embedding: vector de 128 floats por rostro.
    Matching:  distancia euclídea via face_distance().
    Similitud: score = max(0, 1 - distancia).
    """

    @property
    def model_name(self) -> str:
        return "dlib_hog_128"

    @property
    def embedding_dim(self) -> int:
        return 128

    def is_available(self) -> bool:
        return _FR_AVAILABLE

    def warmup(self) -> None:
        # dlib no requiere warmup explícito — los modelos están
        # empaquetados en la librería y se cargan al primer uso.
        if not _FR_AVAILABLE:
            logger.error("DlibFaceEngine no disponible — face_recognition no instalado")

    # ── encode_face ───────────────────────────────────────────────────────────

    def encode_face(self, image_bytes: bytes) -> EmbeddingResult:
        """
        Extrae embedding de 128 dims a partir de bytes de imagen.

        Pasos:
        1. Decodifica bytes → frame BGR (OpenCV)
        2. Convierte BGR → RGB (dlib espera RGB)
        3. Detecta ubicaciones de rostros con modelo HOG
        4. Extrae encoding del primer rostro encontrado
        """
        if not _FR_AVAILABLE:
            return EmbeddingResult(
                embedding=None,
                detected=False,
                model_name=self.model_name,
                embedding_dim=self.embedding_dim,
                error="face_recognition no instalado",
            )

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return EmbeddingResult(
                    embedding=None, detected=False,
                    model_name=self.model_name, embedding_dim=self.embedding_dim,
                    error="No se pudo decodificar la imagen",
                )

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

            with _DLIB_LOCK:
                locations = fr.face_locations(rgb, model="hog")
                if not locations:
                    return EmbeddingResult(
                        embedding=None, detected=False,
                        model_name=self.model_name, embedding_dim=self.embedding_dim,
                    )
                encodings = fr.face_encodings(rgb, locations)

            if not encodings:
                return EmbeddingResult(
                    embedding=None, detected=False,
                    model_name=self.model_name, embedding_dim=self.embedding_dim,
                )

            return EmbeddingResult(
                embedding=encodings[0].tolist(),
                detected=True,
                model_name=self.model_name,
                embedding_dim=self.embedding_dim,
            )

        except Exception as exc:
            logger.error(f"DlibFaceEngine.encode_face error: {exc}")
            return EmbeddingResult(
                embedding=None, detected=False,
                model_name=self.model_name, embedding_dim=self.embedding_dim,
                error=str(exc),
            )

    # ── find_matches ──────────────────────────────────────────────────────────

    def find_matches(
        self,
        frame: np.ndarray,
        known_encodings: list,
        known_ids: list,
        threshold: float,
    ) -> list[FaceMatch]:
        """
        Detecta rostros en el frame y los compara contra los conocidos.

        Downscale al 50% antes de procesar para mejorar rendimiento.
        El bbox se reescala al tamaño original del frame.
        """
        if not _FR_AVAILABLE:
            return []

        results = []
        try:
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            small = cv2.resize(rgb, (0, 0), fx=0.5, fy=0.5)

            with _DLIB_LOCK:
                locations = fr.face_locations(small, model="hog")
                if not locations:
                    return []
                encodings = fr.face_encodings(small, locations)

            for (top, right, bottom, left), encoding in zip(locations, encodings):
                # Reescalar bbox al tamaño original
                top *= 2; right *= 2; bottom *= 2; left *= 2
                bbox = [left, top, right, bottom]

                if known_encodings:
                    with _DLIB_LOCK:
                        distances = fr.face_distance(known_encodings, encoding)
                    best_idx = int(np.argmin(distances))
                    best_dist = float(distances[best_idx])
                    score = max(0.0, 1.0 - best_dist)

                    if score >= threshold:
                        person_type, person_id, nombre = known_ids[best_idx]
                        results.append(FaceMatch(
                            person_type=person_type,
                            person_id=person_id,
                            nombre=nombre,
                            score=round(score, 3),
                            known=True,
                            bbox=bbox,
                        ))
                    else:
                        results.append(FaceMatch(
                            person_type="unknown",
                            person_id=None,
                            nombre="Desconocido",
                            score=round(score, 3),
                            known=False,
                            bbox=bbox,
                        ))
                else:
                    results.append(FaceMatch(
                        person_type="unknown",
                        person_id=None,
                        nombre="Desconocido",
                        score=0.0,
                        known=False,
                        bbox=bbox,
                    ))

        except Exception as exc:
            logger.error(f"DlibFaceEngine.find_matches error: {exc}")

        return results
