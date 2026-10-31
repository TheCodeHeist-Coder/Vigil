"""Finds hands in one frame.

YOLOv8-Pose finds the person and the wrists, but has no finger points. So we extend each
forearm to estimate the hand, crop there, and let MediaPipe find the 21 hand landmarks.
If YOLO sees no person, MediaPipe searches the whole frame.
"""

from dataclasses import dataclass, field

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision
from ultralytics import YOLO

from common.config import ROOT

LEFT_ELBOW, RIGHT_ELBOW, LEFT_WRIST, RIGHT_WRIST = 7, 8, 9, 10
THUMB_TIP, INDEX_TIP = 4, 8
FOREARM_EXTENSION = 0.35
KEYPOINT_CONFIDENCE = 0.35
CROP_SCALE = 1.1
MIN_CROP = 160
PINCH_DISTANCE = 0.09  # of the crop or frame width


@dataclass
class Detection:
    hands: list[tuple[float, float]] = field(default_factory=list)
    pinch: tuple[float, float] | None = None
    skeleton: list[tuple[float, float]] = field(default_factory=list)
    source: str = "none"


class HandDetector:
    def __init__(self, imgsz: int = 480) -> None:
        self.imgsz = imgsz
        self.pose = YOLO(str(ROOT / "models" / f"yolov8n-pose-{imgsz}_openvino_model"), task="pose")
        options = vision.HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(ROOT / "models" / "hand_landmarker.task")),
            running_mode=vision.RunningMode.IMAGE,
            num_hands=2,
            min_hand_detection_confidence=0.35,
            min_hand_presence_confidence=0.35,
        )
        self.landmarker = vision.HandLandmarker.create_from_options(options)
        self.turn = 0

    def detect(self, image: np.ndarray) -> Detection:
        height, width = image.shape[:2]
        estimates, skeleton = self._forearms(image)

        # MediaPipe costs about 27 ms a hand on this CPU, so refine one hand per frame in turn.
        self.turn += 1
        refine = self.turn % len(estimates) if estimates else -1

        hands: list[tuple[float, float]] = []
        pinch = None
        used_mediapipe = False
        for i, (x, y, reach) in enumerate(estimates):
            if i != refine:
                hands.append((x / width, y / height))
                continue
            box = self._crop_box(x, y, reach, width, height)
            found, closed = self._landmarks(image, box)
            if found is None:
                hands.append((x / width, y / height))
                continue
            used_mediapipe = True
            hands.append(found)
            if closed:
                pinch = found

        if not estimates:
            found_all = self._landmarks_all(image)
            hands = [hand for hand, _ in found_all]
            pinch = next((hand for hand, closed in found_all if closed), None)
            used_mediapipe = bool(found_all)

        if estimates and used_mediapipe:
            source = "yolo+mediapipe"
        elif estimates:
            source = "yolo"
        elif used_mediapipe:
            source = "mediapipe"
        else:
            source = "none"
        return Detection(hands=hands, pinch=pinch, skeleton=skeleton, source=source)

    def _forearms(self, image: np.ndarray) -> tuple[list[tuple[float, float, float]], list[tuple[float, float]]]:
        result = self.pose.predict(image, imgsz=self.imgsz, verbose=False, device="cpu", conf=0.25)[0]
        if result.keypoints is None or len(result.keypoints) == 0:
            return [], []

        height, width = image.shape[:2]
        points = result.keypoints.xy.cpu().numpy()
        scores = result.keypoints.conf
        scores = scores.cpu().numpy() if scores is not None else np.ones(points.shape[:2])

        # The operator is the largest person in frame. Passers-by must not trigger events.
        boxes = result.boxes.xyxy.cpu().numpy()
        areas = (boxes[:, 2] - boxes[:, 0]) * (boxes[:, 3] - boxes[:, 1])
        operator = int(np.argmax(areas))
        person, confidence = points[operator], scores[operator]

        estimates: list[tuple[float, float, float]] = []
        skeleton: list[tuple[float, float]] = []
        for elbow, wrist in ((LEFT_ELBOW, LEFT_WRIST), (RIGHT_ELBOW, RIGHT_WRIST)):
            if confidence[wrist] < KEYPOINT_CONFIDENCE:
                continue
            wx, wy = person[wrist]
            skeleton.append((float(wx) / width, float(wy) / height))
            if confidence[elbow] < KEYPOINT_CONFIDENCE:
                estimates.append((float(wx), float(wy), MIN_CROP / 2))
                continue
            ex, ey = person[elbow]
            skeleton.append((float(ex) / width, float(ey) / height))
            dx, dy = wx - ex, wy - ey
            estimates.append(
                (
                    float(wx + FOREARM_EXTENSION * dx),
                    float(wy + FOREARM_EXTENSION * dy),
                    float(np.hypot(dx, dy)),
                )
            )
        return estimates, skeleton

    @staticmethod
    def _crop_box(x: float, y: float, reach: float, width: int, height: int) -> tuple[int, int, int, int]:
        half = max(MIN_CROP, reach * CROP_SCALE) / 2
        left, top = int(max(0, x - half)), int(max(0, y - half))
        right, bottom = int(min(width, x + half)), int(min(height, y + half))
        return left, top, right, bottom

    def _run(self, image: np.ndarray):
        rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        return self.landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))

    def _landmarks(self, image: np.ndarray, box: tuple[int, int, int, int]):
        left, top, right, bottom = box
        if right - left < 32 or bottom - top < 32:
            return None, False
        result = self._run(image[top:bottom, left:right])
        if not result.hand_landmarks:
            return None, False

        height, width = image.shape[:2]
        marks = result.hand_landmarks[0]
        thumb, index = marks[THUMB_TIP], marks[INDEX_TIP]
        mid_x = left + (thumb.x + index.x) / 2 * (right - left)
        mid_y = top + (thumb.y + index.y) / 2 * (bottom - top)
        closed = float(np.hypot(thumb.x - index.x, thumb.y - index.y)) < PINCH_DISTANCE * 2
        return (mid_x / width, mid_y / height), closed

    def _landmarks_all(self, image: np.ndarray) -> list[tuple[tuple[float, float], bool]]:
        found = []
        for marks in self._run(image).hand_landmarks:
            thumb, index = marks[THUMB_TIP], marks[INDEX_TIP]
            point = ((thumb.x + index.x) / 2, (thumb.y + index.y) / 2)
            closed = float(np.hypot(thumb.x - index.x, thumb.y - index.y)) < PINCH_DISTANCE
            found.append((point, closed))
        return found
