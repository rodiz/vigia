"""
Configuración centralizada de VigIA.

Todas las variables de entorno del sistema se leen aquí.
Los demás módulos importan `settings` en lugar de llamar os.getenv() directamente.

Variables relevantes al motor biométrico:
  FACE_ENGINE               — "dlib" (default) o "insightface"
  INSIGHTFACE_MODEL         — modelo InsightFace (default: "buffalo_s")
  FACE_CONFIDENCE_THRESHOLD — umbral de similitud para aceptar match (0–1)
  RECOGNITION_INTERVAL      — segundos mínimos entre inferencias (rate-limit)
  RECOGNITION_DOWNSCALE     — factor de resize antes de inferencia (0.25–1.0)
  RECOGNITION_MAX_FPS       — máx frames/seg procesados con IA

Variables de infraestructura:
  SECRET_KEY   — clave JWT
  DATABASE_URL — URL SQLAlchemy
  DATA_DIR     — directorio raíz de datos (fotos, snapshots)

  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

Rendimiento por plataforma (documentativo):
  - Laptop / mini PC x86:   FACE_ENGINE=insightface, INSIGHTFACE_MODEL=buffalo_l, DOWNSCALE=0.5
  - Raspberry Pi 5:         FACE_ENGINE=insightface, INSIGHTFACE_MODEL=buffalo_s, DOWNSCALE=0.25, MAX_FPS=2
  - Tablet como cliente UI: el tablet solo muestra el stream; la inferencia corre en el backend
"""

import os


class Settings:
    # ── Motor biométrico ──────────────────────────────────────────────────────

    # "dlib" mantiene el comportamiento legacy (default conservador).
    # Cambiar a "insightface" activa el nuevo motor.
    # Si el motor solicitado falla al importar, se hace fallback a "dlib".
    face_engine: str = os.getenv("FACE_ENGINE", "dlib").lower()

    # Modelo InsightFace a usar.
    # "buffalo_s" — ligero, recomendado para edge y Raspberry Pi.
    # "buffalo_l" — más preciso, requiere más RAM y CPU.
    insightface_model: str = os.getenv("INSIGHTFACE_MODEL", "buffalo_s")

    # Umbral de confianza: score mínimo para declarar un match.
    # Rango 0–1. Valores más altos = más estricto.
    # Default 0.6 (dlib). InsightFace suele necesitar ~0.4–0.5 con coseno.
    face_confidence_threshold: float = float(
        os.getenv("FACE_CONFIDENCE_THRESHOLD", "0.6")
    )

    # ── Rendimiento de inferencia ─────────────────────────────────────────────

    # Segundos mínimos entre ejecuciones completas de reconocimiento.
    # Evita saturar CPU/GPU en el loop de frames.
    recognition_interval: float = float(os.getenv("RECOGNITION_INTERVAL", "1.0"))

    # Factor de escala aplicado al frame antes de inferencia.
    # 0.5 = mitad de resolución → 4× menos píxeles → inferencia más rápida.
    # Para Pi o hardware limitado, usa 0.25.
    recognition_downscale: float = float(os.getenv("RECOGNITION_DOWNSCALE", "0.5"))

    # Máximo de frames por segundo procesados con IA.
    # El stream de cámara puede ir a 30 fps; la IA no necesita correr a esa velocidad.
    recognition_max_fps: int = int(os.getenv("RECOGNITION_MAX_FPS", "5"))

    # Segundos de cooldown entre alertas Telegram para una misma cámara.
    detection_cooldown_seconds: int = int(os.getenv("DETECTION_COOLDOWN_SECONDS", "30"))

    # ── Infraestructura ───────────────────────────────────────────────────────

    secret_key: str = os.getenv(
        "SECRET_KEY", "change-this-secret-key-vigia-2024"
    )
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./vigia.db")
    data_dir: str = os.getenv("DATA_DIR", "./data")

    telegram_bot_token: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    telegram_chat_id: str = os.getenv("TELEGRAM_CHAT_ID", "")


# Singleton — importar este objeto en lugar de instanciar Settings()
settings = Settings()
