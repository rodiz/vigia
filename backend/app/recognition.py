import asyncio
import json
import logging
import os
import threading
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

# Suppress NNPACK "Unsupported hardware" warning from PyTorch/YOLO
# (fires on CPUs without AVX2; harmless — PyTorch falls back automatically)
warnings.filterwarnings("ignore", message=".*NNPACK.*")
os.environ.setdefault("TORCH_CPP_LOG_LEVEL", "ERROR")

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# dlib / face_recognition is NOT thread-safe.
# All calls must hold this lock before touching any dlib function.
_DLIB_LOCK = threading.Lock()

# Lazy imports for heavy libraries
try:
    import face_recognition as fr
    FACE_RECOGNITION_AVAILABLE = True
except ImportError:
    FACE_RECOGNITION_AVAILABLE = False
    logger.warning("face_recognition not available - facial recognition disabled")

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    logger.warning("ultralytics not available - object detection disabled")

RELEVANT_CLASSES = {"person", "car", "motorcycle", "truck", "backpack", "handbag", "suitcase"}


class RecognitionService:
    def __init__(self):
        self.known_face_encodings: list = []
        self.known_face_ids: list = []  # list of (type, id, nombre) tuples
        self.yolo_model = None
        self._confidence_threshold = float(os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.6"))
        self._last_recognition_time = 0.0
        self._recognition_interval = 1.0  # seconds between full recognition passes
        self._last_results: dict = {"faces": [], "objects": []}
        # Dedicated single-worker pool so dlib lock contention never blocks
        # FastAPI's request handler threads (fixes 5+ second API response delays)
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="recognition")

    def _load_yolo(self):
        if not YOLO_AVAILABLE:
            return
        if self.yolo_model is None:
            try:
                self.yolo_model = YOLO("yolov8n.pt")
                logger.info("YOLOv8n model loaded")
            except Exception as e:
                logger.error(f"Failed to load YOLO: {e}")

    async def load_known_faces(self, db):
        """Load all resident and visitor face encodings from DB."""
        from .models import Resident, Visitor

        self.known_face_encodings = []
        self.known_face_ids = []

        try:
            residents = db.query(Resident).filter(
                Resident.activo == True,
                Resident.face_encoding != None
            ).all()

            for r in residents:
                try:
                    enc = json.loads(r.face_encoding)
                    self.known_face_encodings.append(np.array(enc))
                    self.known_face_ids.append(("resident", r.id, r.nombre))
                except Exception as e:
                    logger.error(f"Error loading resident {r.id} encoding: {e}")

            visitors = db.query(Visitor).filter(
                Visitor.face_encoding != None
            ).all()

            for v in visitors:
                try:
                    enc = json.loads(v.face_encoding)
                    self.known_face_encodings.append(np.array(enc))
                    self.known_face_ids.append(("visitor", v.id, v.nombre))
                except Exception as e:
                    logger.error(f"Error loading visitor {v.id} encoding: {e}")

            logger.info(
                f"Loaded {len(residents)} resident(s) and {len(visitors)} visitor(s) face encodings"
            )
        except Exception as e:
            logger.error(f"Error loading known faces: {e}")

    def encode_face_from_image(self, image_bytes: bytes) -> Optional[list]:
        """Return face encoding from image bytes, or None if no face found."""
        if not FACE_RECOGNITION_AVAILABLE:
            return None

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if img is None:
                return None

            rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            with _DLIB_LOCK:
                locations = fr.face_locations(rgb, model="hog")
                if not locations:
                    return None
                encodings = fr.face_encodings(rgb, locations)

            if not encodings:
                return None
            return encodings[0].tolist()
        except Exception as e:
            logger.error(f"Error encoding face: {e}")
            return None

    def recognize_faces(self, frame: np.ndarray) -> list:
        """Returns list of dicts with face recognition results."""
        if not FACE_RECOGNITION_AVAILABLE:
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
                top *= 2; right *= 2; bottom *= 2; left *= 2
                bbox = [left, top, right, bottom]

                if self.known_face_encodings:
                    with _DLIB_LOCK:
                        distances = fr.face_distance(self.known_face_encodings, encoding)
                    best_idx = int(np.argmin(distances))
                    best_dist = float(distances[best_idx])
                    confidence = max(0.0, 1.0 - best_dist)

                    if confidence >= self._confidence_threshold:
                        person_type, person_id, nombre = self.known_face_ids[best_idx]
                        results.append({
                            "type": person_type, "id": person_id, "nombre": nombre,
                            "confianza": round(confidence, 3), "bbox": bbox, "known": True
                        })
                    else:
                        results.append({
                            "type": "unknown", "id": None, "nombre": "Desconocido",
                            "confianza": round(confidence, 3), "bbox": bbox, "known": False
                        })
                else:
                    results.append({
                        "type": "unknown", "id": None, "nombre": "Desconocido",
                        "confianza": 0.0, "bbox": bbox, "known": False
                    })

        except Exception as e:
            logger.error(f"Error recognizing faces: {e}")

        return results

    def detect_objects(self, frame: np.ndarray) -> list:
        """Returns list of detected objects filtered to relevant classes."""
        if not YOLO_AVAILABLE or self.yolo_model is None:
            return []

        results_list = []
        try:
            results = self.yolo_model(frame, verbose=False, conf=0.4)
            for r in results:
                for box in r.boxes:
                    cls_name = r.names[int(box.cls)]
                    if cls_name not in RELEVANT_CLASSES:
                        continue
                    x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
                    results_list.append({
                        "class": cls_name,
                        "confidence": round(float(box.conf), 3),
                        "bbox": [x1, y1, x2, y2]
                    })
        except Exception as e:
            logger.error(f"Error detecting objects: {e}")

        return results_list

    def draw_detections(self, frame: np.ndarray, faces: list, objects: list) -> np.ndarray:
        """Draw bounding boxes on frame."""
        img = frame.copy()

        # Draw object boxes (blue)
        for obj in objects:
            if obj["class"] != "person":  # skip person - handled by face
                x1, y1, x2, y2 = obj["bbox"]
                cv2.rectangle(img, (x1, y1), (x2, y2), (255, 100, 0), 2)
                label = f"{obj['class']} {obj['confidence']:.0%}"
                cv2.putText(img, label, (x1, y1 - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 100, 0), 1)

        # Draw face boxes
        for face in faces:
            x1, y1, x2, y2 = face["bbox"]
            color = (0, 200, 0) if face["known"] else (0, 200, 255)  # green / yellow
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            label = f"{face['nombre']} {face['confianza']:.0%}"
            cv2.putText(img, label, (x1, y1 - 8),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

        return img

    async def process_frame(self, frame: np.ndarray, db) -> dict:
        """Full processing: faces + objects. Rate-limited to every 1000ms."""
        now = time.monotonic()
        if now - self._last_recognition_time >= self._recognition_interval:
            self._last_recognition_time = now
            # Use dedicated single-worker executor so dlib lock contention never
            # blocks FastAPI's default thread pool (which handles sync API routes)
            loop = asyncio.get_event_loop()
            faces = await loop.run_in_executor(self._executor, self.recognize_faces, frame)
            self._load_yolo()
            objects = await loop.run_in_executor(self._executor, self.detect_objects, frame)
            self._last_results = {"faces": faces, "objects": objects}

        return self._last_results

    def update_threshold(self, threshold: float):
        self._confidence_threshold = threshold


# ── Compatibility shim ────────────────────────────────────────────────────────
#
# Este módulo mantiene su API pública intacta para no romper ningún import
# existente en main.py, routers/residents.py, routers/visitors.py y
# routers/settings.py.
#
# El singleton `recognition_service` ahora apunta a la nueva implementación
# en services/recognition_service.py, que es engine-agnostic y soporta
# tanto dlib como InsightFace según la variable FACE_ENGINE.
#
# La clase RecognitionService original permanece aquí (sin cambios) como
# referencia y fallback. Si por cualquier motivo el nuevo servicio falla
# al importar, el sistema puede volver a usar la implementación local
# cambiando la línea de importación de abajo.
#
# Para rollback inmediato: comentar el import de abajo y descomentar:
#   recognition_service = RecognitionService()

try:
    from .services.recognition_service import recognition_service  # noqa: F401
except Exception as _shim_error:
    import logging as _logging
    _logging.getLogger(__name__).error(
        f"No se pudo cargar el nuevo RecognitionService: {_shim_error}. "
        "Usando implementación legacy de recognition.py como fallback."
    )
    recognition_service = RecognitionService()
