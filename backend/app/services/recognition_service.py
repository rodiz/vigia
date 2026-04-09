"""
RecognitionService — orquestación del pipeline de reconocimiento en tiempo real.

Responsabilidades:
    1. Recibir frames de cámara.
    2. Ejecutar reconocimiento facial via FaceEngine (agnóstico al motor).
    3. Ejecutar detección de objetos via YOLO (presencia, no identidad).
    4. Dibujar anotaciones visuales sobre el frame.
    5. Rate-limiting para no saturar CPU/GPU.

Por qué YOLO no se usa para identidad
--------------------------------------
YOLO es un detector de objetos de propósito general. Clasifica "persona"
pero no puede distinguir entre Juan Pérez y María García. Intentar usar
YOLO para identidad sería un error de diseño: generaría falsos positivos
masivos y no agregaría información útil.

En este sistema, YOLO cumple un rol diferente:
    - Detectar si hay alguien en cámara (presencia).
    - Detectar objetos relevantes para la portería (vehículos, maletas).
    - Disparar alertas cuando hay actividad, independientemente de si
      el rostro fue reconocido.

La identidad es responsabilidad exclusiva de FaceEngine.

Rendimiento y configuración
-----------------------------
El parámetro `recognition_interval` (default 1.0s) controla cada cuánto
corre el pipeline completo. Entre ejecuciones, se retornan los últimos
resultados cacheados. Esto permite streams a 30fps sin sobrecargar la CPU.

Para hardware limitado (Raspberry Pi, tablet remota):
    RECOGNITION_INTERVAL=2.0   → inferencia cada 2 segundos
    RECOGNITION_DOWNSCALE=0.25 → frame a 1/4 de resolución
    RECOGNITION_MAX_FPS=2      → máximo 2 inferencias/seg
"""

import asyncio
import logging
import os
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

import cv2
import numpy as np

from ..biometrics.base import FaceMatch
from ..biometrics.factory import get_engine
from ..core.settings import settings
from .face_registry_service import face_registry_service

# Silenciar advertencia cosmética de PyTorch/YOLO en hardware sin AVX2
warnings.filterwarnings("ignore", message=".*NNPACK.*")
os.environ.setdefault("TORCH_CPP_LOG_LEVEL", "ERROR")

logger = logging.getLogger(__name__)

RELEVANT_YOLO_CLASSES = {
    "person", "car", "motorcycle", "truck",
    "backpack", "handbag", "suitcase",
}


class RecognitionService:
    """
    Servicio principal de reconocimiento en tiempo real.

    Usa FaceEngine (via factory) para reconocimiento facial y
    YOLOv8n para detección de objetos/presencia.
    """

    def __init__(self):
        self._yolo_model = None
        self._confidence_threshold: float = settings.face_confidence_threshold
        self._last_recognition_time: float = 0.0
        self._last_results: dict = {"faces": [], "objects": []}
        # Pool de un solo worker: evita que dlib lock contention bloquee
        # los threads de FastAPI (reproduce comportamiento del código original)
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="recognition"
        )

    # ── Carga de modelos ──────────────────────────────────────────────────────

    def _load_yolo(self) -> None:
        if self._yolo_model is not None:
            return
        try:
            from ultralytics import YOLO
            self._yolo_model = YOLO("yolov8n.pt")
            logger.info("YOLOv8n cargado")
        except Exception as exc:
            logger.warning(f"No se pudo cargar YOLOv8n: {exc}")

    # ── API pública ───────────────────────────────────────────────────────────

    async def load_known_faces(self, db) -> None:
        """
        Recarga embeddings de la BD a memoria.
        Delegado a FaceRegistryService.
        """
        await face_registry_service.load(db)

    def encode_face_from_image(self, image_bytes: bytes) -> Optional[list]:
        """
        Extrae embedding de una imagen en bytes.

        Retorna lista de floats o None si no se detectó rostro.
        Usado al registrar fotos de residentes y visitantes.
        """
        engine = get_engine()
        result = engine.encode_face(image_bytes)
        if not result.detected or result.embedding is None:
            return None
        return result.embedding

    def encode_face_with_metadata(self, image_bytes: bytes) -> dict:
        """
        Como encode_face_from_image pero también retorna metadatos del motor.

        Retorna:
            {
                "encoding": list | None,
                "detected": bool,
                "model_name": str,
                "embedding_dim": int,
                "error": str | None,
            }
        """
        engine = get_engine()
        result = engine.encode_face(image_bytes)
        return {
            "encoding": result.embedding,
            "detected": result.detected,
            "model_name": result.model_name,
            "embedding_dim": result.embedding_dim,
            "error": result.error,
        }

    def recognize_faces(self, frame: np.ndarray) -> list:
        """
        Detecta y reconoce rostros en un frame.

        Retorna lista de dicts compatibles con el contrato original
        de recognition.py para no romper ningún consumidor existente.

        Formato de cada dict:
            {
                "type":      "resident" | "visitor" | "unknown",
                "id":        int | None,
                "nombre":    str,
                "confianza": float,
                "bbox":      [x1, y1, x2, y2],
                "known":     bool,
            }
        """
        engine = get_engine()
        matches: list[FaceMatch] = engine.find_matches(
            frame=frame,
            known_encodings=face_registry_service.known_encodings,
            known_ids=face_registry_service.known_ids,
            threshold=self._confidence_threshold,
        )

        # Convertir FaceMatch → dict legacy para compatibilidad total
        return [
            {
                "type":      m.person_type,
                "id":        m.person_id,
                "nombre":    m.nombre,
                "confianza": m.score,
                "bbox":      m.bbox,
                "known":     m.known,
            }
            for m in matches
        ]

    def detect_objects(self, frame: np.ndarray) -> list:
        """
        Detecta objetos relevantes usando YOLOv8n.

        YOLO solo detecta presencia y tipo de objeto — nunca identidad.
        """
        if self._yolo_model is None:
            return []

        results = []
        try:
            yolo_results = self._yolo_model(frame, verbose=False, conf=0.4)
            for r in yolo_results:
                for box in r.boxes:
                    cls_name = r.names[int(box.cls)]
                    if cls_name not in RELEVANT_YOLO_CLASSES:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                    results.append({
                        "class":      cls_name,
                        "confidence": round(float(box.conf), 3),
                        "bbox":       [x1, y1, x2, y2],
                    })
        except Exception as exc:
            logger.error(f"detect_objects error: {exc}")

        return results

    def draw_detections(
        self,
        frame: np.ndarray,
        faces: list,
        objects: list,
    ) -> np.ndarray:
        """
        Dibuja bounding boxes sobre el frame.

        Colores:
            Verde  → residente o visitante conocido
            Amarillo → persona desconocida
            Azul   → objeto detectado por YOLO (no persona)
        """
        img = frame.copy()

        for obj in objects:
            if obj["class"] == "person":
                continue  # Personas manejadas por face boxes
            x1, y1, x2, y2 = obj["bbox"]
            cv2.rectangle(img, (x1, y1), (x2, y2), (255, 100, 0), 2)
            label = f"{obj['class']} {obj['confidence']:.0%}"
            cv2.putText(img, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 1)

        for face in faces:
            x1, y1, x2, y2 = face["bbox"]
            color = (0, 200, 0) if face["known"] else (0, 200, 255)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            label = f"{face['nombre']} {face['confianza']:.0%}"
            cv2.putText(img, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        return img

    async def process_frame(self, frame: np.ndarray, db) -> dict:
        """
        Pipeline completo: reconocimiento + detección de objetos.

        Rate-limitado: corre inferencia como máximo una vez por
        `recognition_interval` segundos. Entre ejecuciones retorna
        el último resultado cacheado.

        Ejecuta en thread pool dedicado para no bloquear el event loop
        de FastAPI durante la inferencia (que es síncrona y pesada).
        """
        now = time.monotonic()
        if now - self._last_recognition_time < settings.recognition_interval:
            return self._last_results

        self._last_recognition_time = now
        self._load_yolo()

        loop = asyncio.get_event_loop()
        faces = await loop.run_in_executor(
            self._executor, self.recognize_faces, frame
        )
        objects = await loop.run_in_executor(
            self._executor, self.detect_objects, frame
        )
        self._last_results = {"faces": faces, "objects": objects}
        return self._last_results

    def update_threshold(self, threshold: float) -> None:
        """Actualiza umbral de confianza en runtime."""
        self._confidence_threshold = threshold

    @property
    def active_engine(self) -> str:
        """Nombre del motor biométrico activo."""
        return get_engine().model_name


# Singleton — usado por el shim de recognition.py y por los servicios internos
recognition_service = RecognitionService()
