"""Reads the newest frame from frames.raw and publishes hand positions to hand.tracks."""

import os
import time

from confluent_kafka import OFFSET_END, Consumer, TopicPartition

from common.bus import producer, publish, stamp
from common.config import settings
from common.frames import read_frame
from contracts.models import HandTrack
from contracts.topics import FRAMES_RAW, HAND_TRACKS
from services.edge.detector import HandDetector

REPORT_EVERY = 5.0


def newest_frame(c: Consumer):
    """Waits for a frame, then drains the rest and keeps the last, so lag can never build up."""
    first = c.poll(0.2)
    if first is None or first.error():
        return None, 0
    waiting = [m for m in c.consume(num_messages=500, timeout=0) if not m.error()]
    return (waiting[-1] if waiting else first), len(waiting)


def main() -> None:
    detector = HandDetector(int(os.getenv("YOLO_IMGSZ", "480")))
    c = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap,
            "group.id": "edge",
            "enable.auto.commit": False,
            "fetch.message.max.bytes": 2_097_152,
        }
    )
    c.assign([TopicPartition(FRAMES_RAW, 0, OFFSET_END)])
    p = producer()

    done = skipped_total = 0
    window = time.time()
    print("edge ready", flush=True)
    while True:
        msg, skipped = newest_frame(c)
        skipped_total += skipped
        if msg is None:
            continue
        frame = read_frame(msg)
        detection = detector.detect(frame.image())
        track = HandTrack(
            bench=frame.bench,
            frame_offset=frame.offset,
            hands=detection.hands,
            pinch=detection.pinch,
            skeleton=detection.skeleton,
            source=detection.source,
            times=stamp(frame.times, "edge"),
        )
        publish(p, HAND_TRACKS, track, frame.bench)
        done += 1
        if time.time() - window >= REPORT_EVERY:
            print(f"edge {done / (time.time() - window):.1f} fps, skipped {skipped_total}", flush=True)
            done = skipped_total = 0
            window = time.time()


if __name__ == "__main__":
    main()
