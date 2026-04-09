"""
FaceRegistryService — gestiona el registro en memoria de embeddings conocidos.

Responsabilidad única: mantener sincronizados los embeddings de residentes
y visitantes entre la base de datos y la memoria del proceso.

Por qué existe separado de RecognitionService
----------------------------------------------
RecognitionService procesa frames en tiempo real.
FaceRegistryService gestiona el "quién está registrado".
Son responsabilidades distintas: si las mezclamos, cualquier cambio
en el registro de personas afecta el código de streaming y viceversa.

Nota sobre compatibilidad de embeddings entre motores
------------------------------------------------------
dlib genera vectores de 128 dims.
InsightFace genera vectores de 512 dims.
NO son comparables entre sí.

Al cambiar FACE_ENGINE, los embeddings almacenados en la BD quedan
obsoletos. El sistema detecta esto comparando el `embedding_model`
del registro con el motor activo y omite los embeddings incompatibles
(en lugar de crashear o dar falsos positivos).

Para regenerar embeddings con el nuevo motor:
    python backend/scripts/reindex_embeddings.py --engine insightface
"""

import json
import logging

import numpy as np
from sqlalchemy.orm import Session

from ..biometrics.factory import get_engine

logger = logging.getLogger(__name__)


class FaceRegistryService:
    """
    Mantiene en memoria los embeddings de residentes y visitantes.

    Atributos públicos:
        known_encodings: list[np.ndarray]  — vectores de embeddings
        known_ids:       list[tuple]       — (type, id, nombre) en mismo orden
    """

    def __init__(self):
        self.known_encodings: list = []
        self.known_ids: list = []  # [(type, id, nombre), ...]

    async def load(self, db: Session) -> None:
        """
        Carga todos los embeddings activos de la BD a memoria.

        Omite registros cuyo embedding_model no coincide con el motor activo
        para evitar comparaciones entre vectores de distinta dimensión.
        """
        from ..models import Resident, Visitor

        engine = get_engine()
        active_model = engine.model_name

        self.known_encodings = []
        self.known_ids = []

        loaded = 0
        skipped_model = 0

        try:
            residents = db.query(Resident).filter(
                Resident.activo == True,
                Resident.face_encoding != None,
            ).all()

            for r in residents:
                enc = self._parse_encoding(r.face_encoding, r.embedding_model, active_model)
                if enc is None:
                    skipped_model += 1
                    continue
                self.known_encodings.append(enc)
                self.known_ids.append(("resident", r.id, r.nombre))
                loaded += 1

            visitors = db.query(Visitor).filter(
                Visitor.face_encoding != None,
            ).all()

            for v in visitors:
                enc = self._parse_encoding(v.face_encoding, v.embedding_model, active_model)
                if enc is None:
                    skipped_model += 1
                    continue
                self.known_encodings.append(enc)
                self.known_ids.append(("visitor", v.id, v.nombre))
                loaded += 1

        except Exception as exc:
            logger.error(f"FaceRegistryService.load error: {exc}")

        logger.info(
            f"Embeddings cargados: {loaded} | "
            f"Omitidos por motor incompatible: {skipped_model} | "
            f"Motor activo: {active_model}"
        )

        if skipped_model > 0:
            logger.warning(
                f"{skipped_model} registros tienen embeddings generados con un motor "
                f"diferente a '{active_model}'. Ejecuta el script de reindexación: "
                f"python backend/scripts/reindex_embeddings.py"
            )

    def _parse_encoding(
        self,
        encoding_json: str,
        stored_model: str | None,
        active_model: str,
    ) -> np.ndarray | None:
        """
        Parsea el JSON del embedding y verifica compatibilidad de motor.

        Si el registro no tiene `embedding_model` (legado pre-refactor),
        asume que fue generado con dlib (comportamiento conservador).
        """
        try:
            vec = json.loads(encoding_json)
            if not vec:
                return None

            # Registros sin metadatos de motor = legacy dlib
            effective_model = stored_model or "dlib_hog_128"

            # Si el motor activo es distinto al que generó el embedding → omitir
            if effective_model != active_model:
                return None

            return np.array(vec)
        except Exception as exc:
            logger.error(f"Error parseando embedding JSON: {exc}")
            return None

    @property
    def count(self) -> int:
        return len(self.known_encodings)


# Singleton
face_registry_service = FaceRegistryService()
