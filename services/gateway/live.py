"""Fans Kafka out to browsers. One thread reads Kafka, and every socket gets a copy."""

import asyncio
import json
import threading
import time

import cv2
import numpy as np
from confluent_kafka import OFFSET_END, Consumer, TopicPartition
from fastapi import WebSocket

from common.bus import consumer
from common.config import settings
from contracts.topics import (
    ALERTS_REFLEX,
    BENCH_EVENTS,
    FRAMES_RAW,
    HAND_TRACKS,
    INCIDENTS,
    RUN_STATE,
    VERDICTS,
)

TRACK_INTERVAL = 1 / 15  # hand positions are frequent, so browsers get them at 15 Hz
PREVIEW_SIDE = 640  # the live view stays light, so it works on a slow connection
PREVIEW_QUALITY = 60
CAMERA_TIMEOUT = 2.0


class Hub:
    def __init__(self) -> None:
        self.sockets: set[WebSocket] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.jpeg: bytes | None = None
        self.frame_count = 0
        self.last_frame_at = 0.0
        self.last_state: dict | None = None
        self.preview_jpeg: bytes | None = None
        self.preview_of = -1

    def preview(self) -> bytes | None:
        """The newest frame, made small. Each frame is only resized once, however many watch."""
        if self.jpeg is None or time.time() - self.last_frame_at > CAMERA_TIMEOUT:
            return None
        if self.preview_of != self.frame_count:
            count, jpeg = self.frame_count, self.jpeg
            image = cv2.imdecode(np.frombuffer(jpeg, np.uint8), cv2.IMREAD_COLOR)
            height, width = image.shape[:2]
            scale = PREVIEW_SIDE / max(height, width)
            small = cv2.resize(image, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)
            self.preview_jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, PREVIEW_QUALITY])[1].tobytes()
            self.preview_of = count
        return self.preview_jpeg

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        self.loop = loop
        threading.Thread(target=self._read_messages, daemon=True).start()
        threading.Thread(target=self._read_frames, daemon=True).start()

    async def join(self, socket: WebSocket) -> None:
        await socket.accept()
        self.sockets.add(socket)
        if self.last_state:
            await socket.send_text(json.dumps({"topic": RUN_STATE, "body": self.last_state}))

    def leave(self, socket: WebSocket) -> None:
        self.sockets.discard(socket)

    async def announce(self, topic: str, body: dict) -> None:
        """Tells every screen about something that did not come from Kafka."""
        await self._broadcast(json.dumps({"topic": topic, "body": body}))

    async def _broadcast(self, text: str) -> None:
        for socket in list(self.sockets):
            try:
                await socket.send_text(text)
            except Exception:
                self.leave(socket)

    def _read_messages(self) -> None:
        c = consumer(
            f"gateway-{time.time_ns()}",
            [ALERTS_REFLEX, VERDICTS, INCIDENTS, RUN_STATE, BENCH_EVENTS, HAND_TRACKS],
        )
        last_track = 0.0
        while True:
            msg = c.poll(0.2)
            if msg is None or msg.error():
                continue
            topic = msg.topic()
            if topic == HAND_TRACKS:
                if time.time() - last_track < TRACK_INTERVAL:
                    continue
                last_track = time.time()
            body = json.loads(msg.value())
            if topic == RUN_STATE:
                self.last_state = body
            text = json.dumps({"topic": topic, "body": body, "received": time.time()})
            asyncio.run_coroutine_threadsafe(self._broadcast(text), self.loop)

    def _read_frames(self) -> None:
        c = Consumer(
            {
                "bootstrap.servers": settings.kafka_bootstrap,
                "group.id": f"gateway-video-{time.time_ns()}",
                "enable.auto.commit": False,
                "fetch.message.max.bytes": 2_097_152,
            }
        )
        c.assign([TopicPartition(FRAMES_RAW, 0, OFFSET_END)])
        while True:
            first = c.poll(0.2)
            if first is None or first.error():
                continue
            waiting = [m for m in c.consume(num_messages=500, timeout=0) if not m.error()]
            self.jpeg = (waiting[-1] if waiting else first).value()
            self.frame_count += 1
            self.last_frame_at = time.time()


hub = Hub()
