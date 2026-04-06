import logging
import threading
import time
from typing import Dict, Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class CameraStream:
    """Dedicated reader thread per camera. Only one thread calls cap.read()."""

    def __init__(self, camera_id: int, url):
        self.camera_id = camera_id
        self.url = url
        self._cap: Optional[cv2.VideoCapture] = None
        self._frame: Optional[np.ndarray] = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._failures = 0

    def start(self) -> bool:
        self._cap = cv2.VideoCapture(self.url)
        if not self._cap.isOpened():
            logger.error(f"Camera {self.camera_id}: cannot open {self.url}")
            return False

        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

        # Warm up — discard first frames so sensor stabilizes
        for _ in range(10):
            self._cap.read()

        # Store first valid frame immediately
        ret, frame = self._cap.read()
        if ret and frame is not None:
            with self._lock:
                self._frame = frame

        self._running = True
        self._thread = threading.Thread(target=self._reader, daemon=True)
        self._thread.start()
        logger.info(f"Camera {self.camera_id} stream started")
        return True

    def _reader(self):
        """Background thread: the ONLY place cap.read() is called."""
        while self._running:
            if self._cap is None or not self._cap.isOpened():
                time.sleep(1)
                continue
            ret, frame = self._cap.read()
            if ret and frame is not None:
                with self._lock:
                    self._frame = frame
                self._failures = 0
            else:
                self._failures += 1
                if self._failures > 30:
                    logger.warning(f"Camera {self.camera_id}: too many read failures, reopening")
                    self._cap.release()
                    time.sleep(2)
                    self._cap = cv2.VideoCapture(self.url)
                    self._failures = 0
                time.sleep(0.05)

    def get_frame(self) -> Optional[np.ndarray]:
        """Thread-safe — returns a copy of the latest frame."""
        with self._lock:
            if self._frame is None:
                return None
            return self._frame.copy()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)
        if self._cap:
            self._cap.release()
        logger.info(f"Camera {self.camera_id} stopped")

    @property
    def is_open(self) -> bool:
        return self._running and self._frame is not None


class CameraManager:
    def __init__(self):
        self._streams: Dict[int, CameraStream] = {}

    def _parse_url(self, url: str):
        try:
            return int(url)
        except (ValueError, TypeError):
            return url

    async def start_camera(self, camera_id: int, url: str) -> bool:
        if camera_id in self._streams and self._streams[camera_id].is_open:
            return True
        # Stop existing if any
        if camera_id in self._streams:
            self._streams[camera_id].stop()

        stream = CameraStream(camera_id, self._parse_url(url))
        if not stream.start():
            return False
        self._streams[camera_id] = stream
        return True

    def stop_camera(self, camera_id: int):
        if camera_id in self._streams:
            self._streams[camera_id].stop()
            del self._streams[camera_id]

    def is_camera_open(self, camera_id: int) -> bool:
        return camera_id in self._streams and self._streams[camera_id].is_open

    def get_raw_frame(self, camera_id: int) -> Optional[np.ndarray]:
        if camera_id not in self._streams:
            return None
        return self._streams[camera_id].get_frame()

    def get_last_raw_frame(self, camera_id: int) -> Optional[np.ndarray]:
        return self.get_raw_frame(camera_id)

    def encode_frame(self, frame: np.ndarray, quality: int = 80) -> Optional[bytes]:
        try:
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, quality])
            return jpeg.tobytes()
        except Exception as e:
            logger.error(f"Error encoding frame: {e}")
            return None

    def generate_frames(self, camera_id: int):
        """MJPEG generator — reads from shared frame, never calls cap.read()."""
        while True:
            frame = self.get_raw_frame(camera_id)

            if frame is None:
                # Show status placeholder
                blank = np.zeros((480, 640, 3), dtype=np.uint8)
                cv2.putText(blank, "Conectando camara...", (100, 240),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.9, (100, 100, 255), 2)
                _, jpeg = cv2.imencode(".jpg", blank)
                frame_bytes = jpeg.tobytes()
                time.sleep(1)
            else:
                _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frame_bytes = jpeg.tobytes()
                time.sleep(0.033)  # ~30 fps

            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
            )

    def get_active_camera_ids(self) -> list:
        return [cid for cid, s in self._streams.items() if s.is_open]

    # Legacy alias used by snapshot endpoint
    def get_frame(self, camera_id: int) -> Optional[bytes]:
        frame = self.get_raw_frame(camera_id)
        if frame is None:
            return None
        _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return jpeg.tobytes()


# Singleton
camera_manager = CameraManager()
