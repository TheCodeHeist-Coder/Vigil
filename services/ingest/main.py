"""Receives camera video over WebRTC and writes JPEG frames to frames.raw."""

import asyncio
import time
from contextlib import asynccontextmanager

import cv2
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from common.bus import producer
from common.config import settings
from common.frames import encode_jpeg, publish_frame

MAX_WIDTH = 1280

connections: set[RTCPeerConnection] = set()
kafka = producer()
stats = {"frames": 0, "dropped": 0, "connected": 0}


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    await asyncio.gather(*(pc.close() for pc in list(connections)))
    kafka.flush(5)


app = FastAPI(title="vigil-ingest", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


class Offer(BaseModel):
    sdp: str
    type: str
    bench: str = settings.bench_id


def to_jpeg(frame) -> bytes:
    image = frame.to_ndarray(format="bgr24")
    height, width = image.shape[:2]
    if width > MAX_WIDTH:
        image = cv2.resize(image, (MAX_WIDTH, height * MAX_WIDTH // width))
    return encode_jpeg(image)


async def pump(track: MediaStreamTrack, bench: str) -> None:
    """Keeps only the newest frame, so a slow encode drops frames instead of adding lag."""
    newest = None
    arrived = asyncio.Event()

    async def receive() -> None:
        nonlocal newest
        while True:
            frame = await track.recv()
            if newest is not None:
                stats["dropped"] += 1
            newest = (frame, time.time())
            arrived.set()

    receiver = asyncio.create_task(receive())
    frame_no = 0
    try:
        while True:
            await arrived.wait()
            arrived.clear()
            frame, t_capture = newest
            newest = None
            jpeg = await asyncio.to_thread(to_jpeg, frame)
            publish_frame(kafka, jpeg, bench, frame_no, t_capture)
            frame_no += 1
            stats["frames"] += 1
    except asyncio.CancelledError:
        pass
    finally:
        receiver.cancel()


@app.post("/webrtc/offer")
async def offer(body: Offer) -> dict[str, str]:
    # No ICE servers: the camera and this service share a LAN.
    pc = RTCPeerConnection()
    connections.add(pc)
    tasks: list[asyncio.Task] = []
    stats["connected"] += 1

    @pc.on("track")
    def on_track(track: MediaStreamTrack) -> None:
        if track.kind == "video":
            tasks.append(asyncio.create_task(pump(track, body.bench)))

    @pc.on("connectionstatechange")
    async def on_state() -> None:
        if pc.connectionState in ("failed", "closed", "disconnected"):
            for task in tasks:
                task.cancel()
            connections.discard(pc)
            stats["connected"] -= 1
            await pc.close()

    await pc.setRemoteDescription(RTCSessionDescription(sdp=body.sdp, type=body.type))
    await pc.setLocalDescription(await pc.createAnswer())
    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


@app.get("/health")
def health() -> dict[str, int]:
    return stats


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8101, log_level="warning", timeout_graceful_shutdown=1)
