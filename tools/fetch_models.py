"""Downloads the vision models into models/ and exports YOLOv8-Pose to OpenVINO."""

import shutil
import urllib.request
from pathlib import Path

from ultralytics import YOLO

from common.config import ROOT

MODELS = ROOT / "models"
HAND_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"


def main() -> None:
    hand = MODELS / "hand_landmarker.task"
    if not hand.exists():
        print("downloading hand_landmarker.task")
        urllib.request.urlretrieve(HAND_URL, hand)

    for size in (640, 480):
        target = MODELS / f"yolov8n-pose-{size}_openvino_model"
        if target.exists():
            continue
        weights = MODELS / "yolov8n-pose.pt"
        model = YOLO(str(weights) if weights.exists() else "yolov8n-pose.pt")
        if not weights.exists():
            shutil.move(str(Path(model.ckpt_path)), weights)
            model = YOLO(str(weights))
        exported = Path(model.export(format="openvino", imgsz=size, half=False, verbose=False))
        shutil.move(str(exported), target)
    print("models ready")


if __name__ == "__main__":
    main()
