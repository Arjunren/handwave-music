from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from src.vision.gesture_detector import GestureDetector, Point

LOGGER = logging.getLogger(__name__)

CONNECTIONS = (
    (0, 1),
    (1, 2),
    (2, 3),
    (3, 4),
    (0, 5),
    (5, 6),
    (6, 7),
    (7, 8),
    (5, 9),
    (9, 10),
    (10, 11),
    (11, 12),
    (9, 13),
    (13, 14),
    (14, 15),
    (15, 16),
    (13, 17),
    (17, 18),
    (18, 19),
    (19, 20),
    (0, 17),
)


class CameraWorker(QObject):
    frame_ready = Signal(QImage)
    gesture_ready = Signal(object)
    status_changed = Signal(str)
    cameras_found = Signal(object)

    def __init__(self, project_root: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self._running = False
        self._thread: threading.Thread | None = None
        self._camera_index = 0
        self._show_landmarks = True
        self._control_hand = "Auto"
        self._detector = GestureDetector()

    def start(
        self,
        camera_index: int,
        sensitivity: str,
        show_landmarks: bool,
        control_hand: str = "Auto",
    ) -> None:
        self.stop()
        self._camera_index = camera_index
        self._show_landmarks = show_landmarks
        self._control_hand = control_hand
        self._detector.sensitivity = sensitivity
        self._detector.reset(clear_mode=True)
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="camera-worker")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        self._thread = None

    @staticmethod
    def available_cameras(limit: int = 4) -> list[int]:
        cameras: list[int] = []
        for index in range(limit):
            cap = cv2.VideoCapture(index, cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0)
            if cap.isOpened():
                cameras.append(index)
            cap.release()
        return cameras

    def discover_async(self) -> None:
        def discover() -> None:
            self.cameras_found.emit(self.available_cameras())

        threading.Thread(target=discover, daemon=True, name="camera-discovery").start()

    def _create_tracker(self) -> tuple[str, Any]:
        import mediapipe as mp

        # MediaPipe 0.10 compatibility path.
        if hasattr(mp, "solutions"):
            return "legacy", mp.solutions.hands.Hands(
                static_image_mode=False,
                max_num_hands=2,
                model_complexity=0,
                min_detection_confidence=0.60,
                min_tracking_confidence=0.55,
            )
        model_path = self.project_root / "assets" / "hand_landmarker.task"
        if not model_path.exists():
            raise RuntimeError("MediaPipe model assets/hand_landmarker.task is missing")
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=2,
            min_hand_detection_confidence=0.60,
            min_hand_presence_confidence=0.55,
            min_tracking_confidence=0.55,
        )
        return "tasks", mp.tasks.vision.HandLandmarker.create_from_options(options)

    def _extract(
        self, mode: str, tracker: Any, rgb: np.ndarray, stamp: int
    ) -> list[tuple[list[Any], str, float]]:
        if mode == "legacy":
            result = tracker.process(rgb)
            hands: list[tuple[list[Any], str, float]] = []
            for index, landmarks in enumerate(result.multi_hand_landmarks or []):
                classification = result.multi_handedness[index].classification[0]
                hands.append((list(landmarks.landmark), classification.label, float(classification.score)))
            return hands
        import mediapipe as mp

        result = tracker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), stamp)
        hands = []
        for index, landmarks in enumerate(result.hand_landmarks):
            category = result.handedness[index][0]
            hands.append((list(landmarks), category.category_name, float(category.score or 0.0)))
        return hands

    def _draw(self, frame: np.ndarray, landmarks: list[Any]) -> None:
        height, width = frame.shape[:2]
        points = [(int(item.x * width), int(item.y * height)) for item in landmarks]
        overlay = frame.copy()
        for start, end in CONNECTIONS:
            cv2.line(overlay, points[start], points[end], (206, 123, 255), 2, cv2.LINE_AA)
        for point in points:
            cv2.circle(overlay, point, 3, (104, 237, 255), -1, cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.72, frame, 0.28, 0, frame)

    def _run(self) -> None:
        cap = None
        tracker = None
        try:
            mode, tracker = self._create_tracker()
            backend = cv2.CAP_DSHOW if hasattr(cv2, "CAP_DSHOW") else 0
            cap = cv2.VideoCapture(self._camera_index, backend)
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 960)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 540)
            cap.set(cv2.CAP_PROP_FPS, 30)
            if not cap.isOpened():
                raise RuntimeError(f"Camera {self._camera_index} could not be opened")
            self.status_changed.emit("Camera live")
            started = time.monotonic()
            failures = 0
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    failures += 1
                    if failures > 20:
                        raise RuntimeError("Camera disconnected")
                    time.sleep(0.03)
                    continue
                failures = 0
                frame = cv2.flip(frame, 1)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                hands = self._extract(mode, tracker, rgb, int((time.monotonic() - started) * 1000))
                detected = [
                    (
                        [Point(float(item.x), float(item.y), float(item.z)) for item in landmarks],
                        handedness,
                        confidence,
                    )
                    for landmarks, handedness, confidence in hands
                ]
                event = self._detector.update_hands(detected, self._control_hand)
                self.gesture_ready.emit(event)
                if self._show_landmarks:
                    for landmarks, _, _ in hands:
                        self._draw(frame, landmarks)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = QImage(
                    rgb.data, rgb.shape[1], rgb.shape[0], rgb.strides[0], QImage.Format.Format_RGB888
                ).copy()
                self.frame_ready.emit(image)
                time.sleep(0.005)
        except Exception as exc:
            LOGGER.exception("Camera worker stopped")
            self.status_changed.emit(str(exc))
        finally:
            if cap is not None:
                cap.release()
            if tracker is not None:
                try:
                    tracker.close()
                except Exception:
                    pass
            self._running = False
