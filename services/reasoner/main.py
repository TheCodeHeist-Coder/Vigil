"""Reads flags, decides each one with the manual and Gemini, and publishes verdicts."""

import json
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
from confluent_kafka import Consumer, TopicPartition

from common.bus import consumer, producer, publish, stamp
from common.config import ROOT, settings
from common.db import connect
from contracts.models import Flag, Procedure, RunControl, Verdict
from contracts.topics import FLAGS, FRAMES_RAW, INCIDENTS, RUN_CONTROL, VERDICTS
from services.knowledge.retrieve import search
from services.reasoner.agent import investigate
from services.reasoner.context import VERDICT_AGENT, AgentContext, build_context
from services.reasoner.judge import judge

FRAME_WIDTH = 640


class FrameReader:
    """Fetches evidence frames from Kafka by offset, which is why frames live there."""

    def __init__(self) -> None:
        self.c = Consumer(
            {
                "bootstrap.servers": settings.kafka_bootstrap,
                "group.id": "reasoner-frames",
                "enable.auto.commit": False,
                "fetch.message.max.bytes": 2_097_152,
            }
        )

    def read(self, offsets: list[int]) -> list[bytes]:
        frames: list[bytes] = []
        for offset in offsets:
            self.c.assign([TopicPartition(FRAMES_RAW, 0, offset)])
            msg = self.c.poll(0.5)
            if msg is None or msg.error():
                continue
            image = cv2.imdecode(np.frombuffer(msg.value(), np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                continue
            height, width = image.shape[:2]
            small = cv2.resize(image, (FRAME_WIDTH, height * FRAME_WIDTH // width))
            frames.append(cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes())
        return frames


def load_procedure() -> Procedure:
    return Procedure(**json.loads((ROOT / "manual" / "procedure.json").read_text()))


def saved_verdict(flag: Flag) -> Verdict | None:
    """Stage fallback: the verdict from an earlier real run of the same event."""
    with connect() as db:
        row = db.execute(
            """SELECT status, explanation, citations, model, latency_ms FROM verdicts
               WHERE step_id = %s AND reason = %s AND revision = %s AND source = 'live'
               ORDER BY created_at DESC LIMIT 1""",
            (flag.expected_step, flag.reason, flag.unit_revision),
        ).fetchone()
    if row is None:
        return None
    return Verdict(
        flag_id=flag.id,
        bench=flag.bench,
        run_id=flag.run_id,
        step_id=flag.expected_step,
        reason=flag.reason,
        status=row[0],
        explanation=row[1],
        citations=row[2] or [],
        model=row[3] or "",
        latency_ms=row[4] or 0,
        source="replay",
    )


def store(flag: Flag, verdict: Verdict) -> None:
    with connect() as db:
        db.execute(
            "INSERT INTO runs (id, serial, revision) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
            (flag.run_id, f"unit-{flag.run_id[:8]}", flag.unit_revision),
        )
        db.execute(
            """INSERT INTO verdicts (flag_id, run_id, step_id, reason, revision, status, explanation,
                                     citations, model, latency_ms, hops, source)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (flag_id) DO NOTHING""",
            (
                flag.id,
                flag.run_id,
                verdict.step_id,
                verdict.reason,
                flag.unit_revision,
                verdict.status,
                verdict.explanation,
                json.dumps([c.model_dump() for c in verdict.citations]),
                verdict.model,
                verdict.latency_ms,
                json.dumps(verdict.times),
                verdict.source,
            ),
        )


def decide(flag: Flag, procedure: Procedure, context: AgentContext, frames: FrameReader) -> Verdict:
    if settings.replay:
        saved = saved_verdict(flag)
        if saved:
            return saved
    steps = [s for s in (flag.expected_step, flag.actual_step) if s]
    query = " ".join(procedure.step(s).title for s in steps)
    excerpts = search(query, steps)
    images = frames.read(flag.frame_offsets)
    return judge(flag, procedure, excerpts, context.recall(flag.expected_step), images)


def main() -> None:
    kafka = producer()
    context = build_context()
    frames = FrameReader()
    procedure = load_procedure()
    agents = ThreadPoolExecutor(2, thread_name_prefix="incident")
    c = consumer("reasoner", [FLAGS, RUN_CONTROL])

    def run_incident(flag: Flag, verdict: Verdict) -> None:
        try:
            publish(kafka, INCIDENTS, investigate(flag, verdict, procedure, context), flag.bench)
        except Exception as error:
            print(f"incident failed: {error}", flush=True)

    print(f"reasoner ready, memory in {context.backend}, model {settings.gemini_model if settings.gemini_api_key else 'local-rules'}", flush=True)
    while True:
        msg = c.poll(0.2)
        if msg is None:
            continue
        if msg.error():
            print(f"kafka: {msg.error()}", flush=True)
            continue
        body = json.loads(msg.value())
        if msg.topic() == RUN_CONTROL:
            control = RunControl(**body)
            if control.kind == "start":
                context.start_run(control.run_id, control.serial or "", [s.id for s in procedure.steps])
            elif control.kind == "procedure" and control.procedure:
                procedure = control.procedure
            continue

        flag = Flag(**body)
        verdict = decide(flag, procedure, context, frames)
        verdict.times = stamp(flag.event.times, "reasoner")
        store(flag, verdict)
        publish(kafka, VERDICTS, verdict, flag.bench)
        context.trace(
            flag.run_id,
            VERDICT_AGENT,
            f"{flag.reason} at {flag.expected_step}, revision {flag.unit_revision}",
            f"{verdict.status}: {verdict.explanation}",
            f"Citations: {[c.section for c in verdict.citations]}. Model: {verdict.model}",
        )
        if verdict.status == "confirmed":
            agents.submit(run_incident, flag, verdict)


if __name__ == "__main__":
    main()
