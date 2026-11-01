"""Sends real WebRTC video to ingest and checks JPEG frames reach Kafka. Needs Kafka running."""

import asyncio
import fractions
import threading
import time
import uuid

import av
import httpx
import numpy as np
import pytest
import uvicorn
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack
from confluent_kafka import Consumer

from common.config import settings
from common.frames import read_frame
from contracts.topics import FRAMES_RAW
from services.ingest.main import app
from services.ingest.ports import limit_udp_ports, parse_range

PORT = 8191


class MovingDot(VideoStreamTrack):
    def __init__(self) -> None:
        super().__init__()
        self.count = 0

    async def recv(self) -> av.VideoFrame:
        await asyncio.sleep(1 / 30)
        image = np.zeros((720, 1280, 3), dtype=np.uint8)
        image[300:400, (self.count * 7) % 1180 : (self.count * 7) % 1180 + 100] = (0, 220, 255)
        frame = av.VideoFrame.from_ndarray(image, format="bgr24")
        frame.pts = self.count
        frame.time_base = fractions.Fraction(1, 30)
        self.count += 1
        return frame


async def publish(seconds: float, bench: str) -> None:
    pc = RTCPeerConnection()
    pc.addTrack(MovingDot())
    await pc.setLocalDescription(await pc.createOffer())
    while pc.iceGatheringState != "complete":
        await asyncio.sleep(0.05)
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"http://127.0.0.1:{PORT}/webrtc/offer",
            json={"sdp": pc.localDescription.sdp, "type": pc.localDescription.type, "bench": bench},
            timeout=15,
        )
    answer = response.json()
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
    await asyncio.sleep(seconds)
    await pc.close()


def test_udp_ports_stay_in_range():
    async def scenario():
        loop = asyncio.get_running_loop()
        limit_udp_ports(loop, parse_range("41000-41002"))
        ports, transports = [], []
        for _ in range(3):
            transport, _protocol = await loop.create_datagram_endpoint(asyncio.DatagramProtocol, local_addr=("127.0.0.1", 0))
            transports.append(transport)
            ports.append(transport.get_extra_info("sockname")[1])
        with pytest.raises(OSError, match="no free UDP port"):
            await loop.create_datagram_endpoint(asyncio.DatagramProtocol, local_addr=("127.0.0.1", 0))
        for transport in transports:
            transport.close()
        return ports

    assert sorted(asyncio.run(scenario())) == [41000, 41001, 41002]


@pytest.mark.integration
def test_webrtc_video_reaches_kafka():
    bench = f"test-{uuid.uuid4().hex[:6]}"
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning", loop="asyncio"))
    threading.Thread(target=server.run, daemon=True).start()
    time.sleep(1)

    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": bench,
            "auto.offset.reset": "latest",
            "fetch.message.max.bytes": 2_097_152,
        }
    )
    consumer.subscribe([FRAMES_RAW])
    deadline = time.time() + 5
    while not consumer.assignment() and time.time() < deadline:
        consumer.poll(0.2)

    asyncio.run(publish(4, bench))

    frames = []
    deadline = time.time() + 6
    while time.time() < deadline:
        msg = consumer.poll(0.3)
        if msg is None or msg.error():
            continue
        frame = read_frame(msg)
        if frame.bench == bench:
            frames.append(frame)
    consumer.close()
    server.should_exit = True

    assert len(frames) >= 30, f"only {len(frames)} frames arrived"
    image = frames[-1].image()
    assert image.shape[0] > 0 and image.shape[1] > 0
    print(f"\n{len(frames)} frames, size {image.shape[1]}x{image.shape[0]}")
