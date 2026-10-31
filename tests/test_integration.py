"""Needs Kafka and YugabyteDB running."""

import time
import uuid
from dataclasses import replace

import cv2
import numpy as np
import pytest
from confluent_kafka import Consumer, TopicPartition

from common.bus import producer
from common.config import settings
from common.db import connect
from common.frames import encode_jpeg, publish_frame
from contracts.models import BenchEvent, Flag
from contracts.topics import FRAMES_RAW
from services.reasoner import main as reasoner

pytestmark = pytest.mark.integration


def test_evidence_frames_read_by_offset_are_fast():
    bench = f"test-{uuid.uuid4().hex[:6]}"
    p = producer()
    image = np.random.default_rng(1).integers(0, 255, (720, 1280, 3), dtype=np.uint8)
    jpeg = encode_jpeg(cv2.GaussianBlur(image, (9, 9), 0))
    for i in range(12):
        publish_frame(p, jpeg, bench, i, time.time())
    p.flush(5)

    c = Consumer({"bootstrap.servers": settings.kafka_bootstrap, "group.id": bench})
    _, high = c.get_watermark_offsets(TopicPartition(FRAMES_RAW, 0), timeout=5)
    c.close()
    offsets = [high - 12, high - 8, high - 4, high - 1]

    reader = reasoner.FrameReader()
    reader.read(offsets)  # the first read also joins the cluster
    started = time.perf_counter()
    frames = reader.read(offsets)
    took = (time.perf_counter() - started) * 1000
    print(f"\n4 evidence frames in {took:.0f} ms")

    assert len(frames) == 4
    decoded = cv2.imdecode(np.frombuffer(frames[0], np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape[1] == reasoner.FRAME_WIDTH
    assert took < 300


def test_replay_returns_a_saved_verdict_marked_as_replay(monkeypatch):
    run_id, flag_id = str(uuid.uuid4()), str(uuid.uuid4())
    step = f"T{uuid.uuid4().hex[:6]}"
    with connect() as db:
        db.execute("INSERT INTO runs (id, serial, revision) VALUES (%s, 'test', 'A')", (run_id,))
        db.execute(
            """INSERT INTO verdicts (flag_id, run_id, step_id, reason, revision, status, explanation, citations, model, latency_ms, source)
               VALUES (%s, %s, %s, 'out_of_sequence', 'A', 'confirmed', 'saved', '[{"section": "4.1", "page": 6, "quote": "q"}]', 'gemini', 900, 'live')""",
            (flag_id, run_id, step),
        )
    event = BenchEvent(id="e", bench="b", run_id=run_id, kind="pick", zone="B", frame_offset=1)
    flag = Flag(id=str(uuid.uuid4()), bench="b", run_id=run_id, event=event, reason="out_of_sequence", expected_step=step, unit_revision="A")

    verdict = reasoner.saved_verdict(flag)
    assert verdict.source == "replay"
    assert verdict.status == "confirmed"
    assert verdict.citations[0].section == "4.1"

    other_revision = flag.model_copy(update={"unit_revision": "B"})
    assert reasoner.saved_verdict(other_revision) is None
