"""Pushes a recorded clip through frames.raw, exactly like a live camera.

Everyone can develop against a clip, and it is the stage fallback if the camera link fails.

  python -m tools.replay_clip clips/e1.mp4
  python -m tools.replay_clip --synthetic --seconds 5
"""

import argparse
import time

import cv2
import numpy as np

from common.bus import producer
from common.config import settings
from common.frames import encode_jpeg, publish_frame

WIDTH, HEIGHT = 1280, 720


def clip_frames(path: str, loop: bool):
    while True:
        video = cv2.VideoCapture(path)
        if not video.isOpened():
            raise SystemExit(f"cannot open {path}")
        while True:
            ok, image = video.read()
            if not ok:
                break
            yield cv2.resize(image, (WIDTH, HEIGHT))
        video.release()
        if not loop:
            return


def synthetic_frames(seconds: float, fps: int):
    rng = np.random.default_rng(1)
    noise = rng.integers(0, 40, (HEIGHT, WIDTH, 3), dtype=np.uint8)
    for i in range(int(seconds * fps)):
        image = noise.copy()
        x = int((i * 11) % WIDTH)
        cv2.circle(image, (x, HEIGHT // 2), 40, (0, 220, 255), -1)
        cv2.putText(image, f"frame {i}", (40, 80), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3)
        yield image


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clip", nargs="?")
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--seconds", type=float, default=5)
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--bench", default=settings.bench_id)
    args = parser.parse_args()

    if not args.clip and not args.synthetic:
        parser.error("give a clip path or --synthetic")

    frames = synthetic_frames(args.seconds, args.fps) if args.synthetic else clip_frames(args.clip, args.loop)
    p = producer()
    interval = 1 / args.fps
    started = next_at = time.perf_counter()
    sent = size = 0
    for image in frames:
        jpeg = encode_jpeg(image)
        publish_frame(p, jpeg, args.bench, sent, time.time())
        sent += 1
        size += len(jpeg)
        next_at += interval
        time.sleep(max(0, next_at - time.perf_counter()))
    p.flush(10)
    took = time.perf_counter() - started
    print(f"sent {sent} frames in {took:.1f}s = {sent / took:.1f} fps, {size / took / 1e6:.1f} MB/s, avg {size / max(sent, 1) / 1e3:.0f} KB")


if __name__ == "__main__":
    main()
