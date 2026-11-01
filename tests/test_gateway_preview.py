import time

import cv2
import numpy as np

from services.gateway.live import PREVIEW_SIDE, RUN_RESUME_SECONDS, Hub


def loaded(width: int, height: int) -> Hub:
    hub = Hub()
    image = np.random.default_rng(1).integers(0, 255, (height, width, 3), dtype=np.uint8)
    hub.jpeg = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    hub.frame_count = 1
    hub.last_frame_at = time.time()
    return hub


def size(jpeg: bytes) -> tuple[int, int]:
    image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
    return image.shape[1], image.shape[0]


def test_preview_is_small_and_keeps_a_wide_shape():
    hub = loaded(1280, 720)
    assert size(hub.preview()) == (PREVIEW_SIDE, 360)
    assert len(hub.preview()) < len(hub.jpeg)


def test_preview_keeps_an_upright_phone_shape():
    assert size(loaded(720, 1280).preview()) == (360, PREVIEW_SIDE)


def test_each_frame_is_only_resized_once():
    hub = loaded(1280, 720)
    assert hub.preview() is hub.preview()


def test_no_preview_when_the_camera_has_stopped():
    hub = loaded(1280, 720)
    hub.last_frame_at = time.time() - 10
    assert hub.preview() is None


def test_abandoned_run_is_dropped():
    hub = Hub()
    hub.last_state = {"run_id": "old"}
    hub.last_activity = time.time() - RUN_RESUME_SECONDS - 1
    assert hub.expire_stale_run() is True
    assert hub.last_state is None


def test_active_run_is_kept():
    hub = Hub()
    hub.last_state = {"run_id": "now"}
    hub.last_activity = time.time()
    assert hub.expire_stale_run() is False
    assert hub.last_state == {"run_id": "now"}
