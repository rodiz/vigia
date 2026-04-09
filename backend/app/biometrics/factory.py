"""
Factory del motor biométrico.

Selecciona e instancia el FaceEngine correcto según la variable de entorno
FACE_ENGINE. Si el motor solicitado no está disponible (dependencia no
instalada), hace fallback a dlib y registra una advertencia.

Uso:
    from backend.app.biometrics.factory import get_engine
    engine = get_engine()  # retorna DlibFaceEngine o InsightFaceEngine

Valores válidos de FACE_ENGINE:
    "dlib"        → DlibFaceEngine (default, legacy, siempre disponible si
                    face_recognition está instalado)
    "insightface" → InsightFaceEngine (nuevo motor, requiere insightface +
                    onnxruntime instalados)

Fallback:
    Si se solicita "insightface" pero no está instalado, el sistema cae
    automáticamente a dlib y sigue funcionando. Nunca falla en silencio:
    se registra un WARNING con instrucciones de instalación.
"""

import logging

from ..core.settings import settings
from .base import FaceEngine

logger = logging.getLogger(__name__)

# Singleton: el engine se instancia una sola vez por proceso
_engine_instance: FaceEngine | None = None


def get_engine() -> FaceEngine:
    """
    Retorna el singleton del motor biométrico activo.

    Se instancia en el primer llamado y se reutiliza en los siguientes.
    Thread-safe para el caso de uso de FastAPI (el startup lo llama una vez).
    """
    global _engine_instance
    if _engine_instance is not None:
        return _engine_instance

    requested = settings.face_engine
    _engine_instance = _build_engine(requested)
    return _engine_instance


def _build_engine(requested: str) -> FaceEngine:
    if requested == "insightface":
        engine = _try_insightface()
        if engine is not None:
            return engine
        logger.warning(
            "InsightFaceEngine no disponible — cayendo a DlibFaceEngine. "
            "Para instalar InsightFace: pip install insightface onnxruntime"
        )

    return _build_dlib()


def _build_dlib() -> FaceEngine:
    from .dlib_engine import DlibFaceEngine
    engine = DlibFaceEngine()
    if not engine.is_available():
        logger.error(
            "DlibFaceEngine tampoco está disponible. "
            "El reconocimiento facial estará desactivado. "
            "Instala: pip install face-recognition"
        )
    else:
        logger.info("Motor biométrico activo: DlibFaceEngine (dlib_hog_128)")
    return engine


def _try_insightface() -> FaceEngine | None:
    try:
        from .insightface_engine import InsightFaceEngine
        engine = InsightFaceEngine()
        if engine.is_available():
            logger.info(
                f"Motor biométrico activo: InsightFaceEngine "
                f"({settings.insightface_model})"
            )
            return engine
        logger.warning("InsightFaceEngine instanciado pero is_available() retornó False")
        return None
    except ImportError as exc:
        logger.warning(f"No se pudo importar InsightFaceEngine: {exc}")
        return None
    except Exception as exc:
        logger.error(f"Error inicializando InsightFaceEngine: {exc}")
        return None


def reset_engine() -> None:
    """
    Limpia el singleton. Útil para tests o para forzar
    recarga del motor (ej. después de cambiar FACE_ENGINE en runtime).
    """
    global _engine_instance
    _engine_instance = None
