"""How JPEG frames travel on frames.raw. The bytes are the value; the rest are headers."""

import time
from dataclasses import dataclass

import cv2
import numpy as np
from confluent_kafka import Message, Producer

from contracts.topics import FRAMES_RAW

JPEG_QUALITY = 80


@dataclass
class Frame:
    jpeg: bytes
    bench: str
    frame_no: int
    offset: int
    times: dict[str, float]

    def image(self) -> np.ndarray:
        return cv2.imdecode(np.frombuffer(self.jpeg, np.uint8), cv2.IMREAD_COLOR)


def encode_jpeg(image: np.ndarray) -> bytes:
    ok, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
    if not ok:
        raise ValueError("JPEG encoding failed")
    return buffer.tobytes()


def publish_frame(p: Producer, jpeg: bytes, bench: str, frame_no: int, t_capture: float) -> None:
    headers = [
        ("bench", bench.encode()),
        ("frame_no", str(frame_no).encode()),
        ("t_capture", str(t_capture).encode()),
        ("t_ingest", str(time.time()).encode()),
    ]
    p.produce(FRAMES_RAW, value=jpeg, key=bench, headers=headers)
    p.poll(0)


def read_frame(msg: Message) -> Frame:
    headers = {key: value.decode() for key, value in (msg.headers() or [])}
    return Frame(
        jpeg=msg.value(),
        bench=headers.get("bench", ""),
        frame_no=int(headers.get("frame_no", 0)),
        offset=msg.offset(),
        times={
            "t_capture": float(headers.get("t_capture", 0)),
            "t_ingest": float(headers.get("t_ingest", 0)),
        },
    )
