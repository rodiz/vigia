"""
InsightFaceEngine — motor biométrico moderno basado en InsightFace + ONNX Runtime.

Por qué InsightFace mejora sobre dlib/face_recognition
--------------------------------------------------------
1. Arquitectura moderna:
   - dlib usa descriptores HOG + SVM (2010). Robusto pero limitado.
   - InsightFace usa redes neuronales profundas (ArcFace, 2018+).
     Mejor con variaciones de pose, luz, oclusión parcial.

2. Embeddings de mayor capacidad:
   - dlib: 128 dimensiones.
   - InsightFace buffalo_s/l: 512 dimensiones.
   Mayor dimensión = más espacio de representación = menos colisiones.

3. Rendimiento en inferencia:
   - ONNX Runtime permite exportar el modelo a un formato portable
     y ejecutarlo eficientemente en CPU sin dependencias de PyTorch/TensorFlow.
   - buffalo_s está optimizado para CPU y dispositivos edge.

4. Instalación más predecible:
   - dlib requiere compilar C++ contra Boost. En Linux ARM (Pi) o entornos
     sin compilador es frágil.
   - InsightFace + ONNX Runtime: pip install, sin compilación.

Modelos disponibles
--------------------
  "buffalo_s" — modelo liviano, recomendado para:
                  Raspberry Pi 5, mini PC, tablet + backend remoto
                Precisión: buena. Velocidad: ~50-100ms en CPU.

  "buffalo_l" — modelo completo, recomendado para:
                  Servidor dedicado, laptop con CPU moderna
                Precisión: muy buena. Velocidad: ~200-400ms en CPU.

  El modelo se descarga automáticamente en ~/.insightface/models/
  en el primer uso. Requiere conexión a internet.

Métricas de similitud
----------------------
InsightFace retorna embeddings normalizados (norma L2 = 1).
La similitud se calcula como producto punto (= coseno para vectores normalizados).
Rango: -1 (opuesto) a 1 (idéntico).

El umbral recomendado para InsightFace es 0.4–0.5 (vs 0.6 de dlib).
Ajusta FACE_CONFIDENCE_THRESHOLD al migrar.

Instalación
-----------
    pip install insightface onnxruntime

    Para GPU:
    pip install onnxruntime-gpu  (en lugar de onnxruntime)
"""

import logging
from typing import Optional

import cv2
import numpy as np

from .base import FaceEngine, EmbeddingResult, FaceMatch

logger = logging.getLogger(__name__)

try:
    import insightface
    from insightface.app import FaceAnalysis
    _INSIGHTFACE_AVAILABLE = True
except ImportError:
    _INSIGHTFACE_AVAILABLE = False


class InsightFaceEngine(FaceEngine):
    """
    Implementación del motor biométrico usando InsightFace + ONNX Runtime.

    Embedding: vector de 512 floats (ArcFace, L2-normalizado).
    Matching:  similitud coseno (producto punto entre vectores normalizados).
    Umbral:    0.4–0.5 recomendado (vs 0.6 de dlib).
    """

    def __init__(self, model_name: str = "buffalo_s"):
        self._model_name = model_name
        self._app: Optional["FaceAnalysis"] = None
        self._initialized = False

    @property
    def model_name(self) -> str:
        return f"insightface_{self._model_name}_512"

    @property
    def embedding_dim(self) -> int:
        return 512

    def is_available(self) -> bool:
        return _INSIGHTFACE_AVAILABLE

    def warmup(self) -> None:
        """
        Inicializa el modelo InsightFace en memoria.

        Se llama en el startup del servidor para evitar latencia
        en el primer frame de cámara. Descarga el modelo si no existe.
        """
        if not _INSIGHTFACE_AVAILABLE:
            logger.error(
                "InsightFace no está instalado. "
                "Instala con: pip install insightface onnxruntime"
            )
            return
        if self._initialized:
            return
        try:
            self._app = FaceAnalysis(
                name=self._model_name,
                providers=["CPUExecutionProvider"],
            )
            # ctx_id=0 para GPU, -1 para CPU
            self._app.prepare(ctx_id=-1, det_size=(640, 640))
            self._initialized = True
            logger.info(
                f"InsightFaceEngine inicializado: modelo={self._model_name}"
            )
        except Exception as exc:
            logger.error(f"Error inicializando InsightFace: {exc}")
            self._initialized = False

    def _ensure_initialized(self) -> bool:
        if not self._initialized:
            self.warmup()
        return self._initialized

    # ── encode_face ───────────────────────────────────────────────────────────

    def encode_face(self, image_bytes: bytes) -> EmbeddingResult:
        """
        Extrae embedding de 512 dims a partir de bytes de imagen.

        InsightFace espera imágenes BGR (formato OpenCV). Detecta el rostro
        más prominente (mayor área de bounding box) si hay varios.
        """
        if not self._ensure_initialized():
            return EmbeddingResult(
                embedding=None, detected=False,
                model_name=self.model_name, embedding_dim=self.embedding_dim,
                error="InsightFace no inicializado",
            )

        try:
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)  # BGR
            if img is None:
                return EmbeddingResult(
                    embedding=None, detected=False,
                    model_name=self.model_name, embedding_dim=self.embedding_dim,
                    error="No se pudo decodificar la imagen",
                )

            faces = self._app.get(img)
            if not faces:
                return EmbeddingResult(
                    embedding=None, detected=False,
                    model_name=self.model_name, embedding_dim=self.embedding_dim,
                )

            # Usar el rostro más grande si hay varios (más probable = el sujeto)
            face = max(faces, key=lambda f: _bbox_area(f.bbox))
            embedding = face.normed_embedding.tolist()

            return EmbeddingResult(
                embedding=embedding,
                detected=True,
                model_name=self.model_name,
                embedding_dim=self.embedding_dim,
            )

        except Exception as exc:
            logger.error(f"InsightFaceEngine.encode_face error: {exc}")
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
        Detecta rostros en el frame y los compara por similitud coseno.

        InsightFace detecta directamente en BGR — no necesita conversión.
        Los embeddings son L2-normalizados, por lo que el producto punto
        equivale a la similitud coseno (rango 0–1 para embeddings positivos).
        """
        if not self._ensure_initialized():
            return []

        results = []
        try:
            faces = self._app.get(frame)
            if not faces:
                return []

            for face in faces:
                bbox = [int(v) for v in face.bbox.tolist()]
                embedding = face.normed_embedding

                if known_encodings:
                    # Producto punto = coseno para embeddings normalizados
                    known_matrix = np.array(known_encodings)
                    similarities = known_matrix.dot(embedding)
                    best_idx = int(np.argmax(similarities))
                    score = float(similarities[best_idx])
                    # Normalizar a 0–1 (similitud coseno puede ser negativa)
                    score_normalized = max(0.0, score)

                    if score_normalized >= threshold:
                        person_type, person_id, nombre = known_ids[best_idx]
                        results.append(FaceMatch(
                            person_type=person_type,
                            person_id=person_id,
                            nombre=nombre,
                            score=round(score_normalized, 3),
                            known=True,
                            bbox=bbox,
                        ))
                    else:
                        results.append(FaceMatch(
                            person_type="unknown",
                            person_id=None,
                            nombre="Desconocido",
                            score=round(score_normalized, 3),
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
            logger.error(f"InsightFaceEngine.find_matches error: {exc}")

        return results


# ── Helpers ───────────────────────────────────────────────────────────────────

def _bbox_area(bbox) -> float:
    """Calcula el área de un bounding box [x1, y1, x2, y2]."""
    return max(0.0, (bbox[2] - bbox[0]) * (bbox[3] - bbox[1]))
