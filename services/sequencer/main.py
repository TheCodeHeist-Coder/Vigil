"""Reads hand.tracks, checks each event against the procedure, and raises alerts and flags."""

import json
import time
import uuid
from collections import deque
from dataclasses import dataclass, field

from common.bus import consumer, producer, publish, stamp
from common.config import ROOT
from contracts.models import (
    BenchEvent,
    Flag,
    HandTrack,
    Procedure,
    ReflexAlert,
    RunControl,
    RunState,
    Verdict,
    Zone,
)
from contracts.topics import ALERTS_REFLEX, BENCH_EVENTS, FLAGS, HAND_TRACKS, RUN_CONTROL, RUN_STATE, VERDICTS
from services.sequencer import logic
from services.sequencer.zones import ZoneTracker

EVIDENCE_SECONDS = (1.5, 1.0, 0.5, 0.0)


def load_zones() -> list[Zone]:
    return [Zone(**z) for z in json.loads((ROOT / "manual" / "zones.json").read_text())]


def load_procedure() -> Procedure:
    return Procedure(**json.loads((ROOT / "manual" / "procedure.json").read_text()))


def in_use(zones: list[Zone], procedure: Procedure) -> list[Zone]:
    """Only bins this manual uses can fire, so a hidden bin can never cause an event."""
    bins = {step.bin for step in procedure.steps}
    return [zone for zone in zones if zone.kind == "tray" or zone.id in bins]


@dataclass
class Bench:
    id: str
    zones: list[Zone]
    procedure: Procedure
    tracker: ZoneTracker
    run: logic.Run | None = None
    history: deque = field(default_factory=lambda: deque(maxlen=120))  # (time, frame offset)


class Sequencer:
    def __init__(self, kafka) -> None:
        self.kafka = kafka
        self.benches: dict[str, Bench] = {}
        self.zones = load_zones()
        self.procedure = load_procedure()

    def bench(self, bench_id: str) -> Bench:
        if bench_id not in self.benches:
            self.benches[bench_id] = Bench(bench_id, self.zones, self.procedure, ZoneTracker(in_use(self.zones, self.procedure)))
        return self.benches[bench_id]

    def publish_state(self, bench: Bench) -> None:
        run = bench.run
        state = RunState(
            bench=bench.id,
            run_id=run.run_id,
            serial=run.serial,
            revision=run.revision,
            done=run.done,
            waived=run.waived,
            active=run.active,
            held=run.held is not None,
            finished=logic.finished(run, bench.procedure),
        )
        publish(self.kafka, RUN_STATE, state, bench.id)

    def on_control(self, control: RunControl) -> None:
        bench = self.bench(control.bench)
        if control.kind == "start":
            bench.run = logic.Run(control.run_id, control.serial or "", control.revision, control.photo_checks)
            bench.tracker = ZoneTracker(in_use(bench.zones, bench.procedure))
            self.publish_state(bench)
        elif control.kind == "stop":
            bench.run = None
        elif control.kind == "zones" and control.zones:
            self.zones = bench.zones = control.zones
            bench.tracker = ZoneTracker(in_use(bench.zones, bench.procedure))
        elif control.kind == "procedure" and control.procedure:
            self.procedure = bench.procedure = control.procedure
            bench.tracker = ZoneTracker(in_use(bench.zones, bench.procedure))
        elif control.kind == "recheck" and bench.run:
            self.send_rechecks(bench, logic.request_recheck(bench.run))
            self.publish_state(bench)
        elif control.kind == "release" and bench.run:
            step_id = logic.blocking_step(bench.run)
            if step_id:
                self.flag(bench, self.bench_event(bench), "supervisor_release", step_id, None, [])

    def bench_event(self, bench: Bench) -> BenchEvent:
        return BenchEvent(
            id=str(uuid.uuid4()),
            bench=bench.id,
            run_id=bench.run.run_id,
            kind="hands_clear",
            zone="TRAY",
            frame_offset=bench.history[-1][1] if bench.history else 0,
            times=stamp({"t_ingest": time.time()}, "sequencer"),
        )

    def send_rechecks(self, bench: Bench, outputs: list) -> None:
        for output in outputs:
            if isinstance(output, logic.Recheck):
                event = self.bench_event(bench)
                self.flag(bench, event, "step_check", output.step_id, None, [event.frame_offset])

    def on_verdict(self, verdict: Verdict) -> None:
        bench = self.bench(verdict.bench)
        if not bench.run or bench.run.run_id != verdict.run_id:
            return
        for output in logic.on_verdict(bench.run, bench.procedure, verdict):
            if not bench.run.photo_checks:
                continue
            offset = bench.history[-1][1] if bench.history else 0
            event = BenchEvent(
                id=str(uuid.uuid4()),
                bench=bench.id,
                run_id=bench.run.run_id,
                kind="hands_clear",
                zone="TRAY",
                frame_offset=offset,
                times=stamp(verdict.times, "sequencer"),
            )
            self.flag(bench, event, "step_check", output.step_id, None, [offset])
        self.publish_state(bench)

    def evidence(self, bench: Bench, event: BenchEvent) -> list[int]:
        now = event.times.get("t_sequencer", time.time())
        offsets: list[int] = []
        for ago in EVIDENCE_SECONDS:
            target = now - ago
            nearest = min(bench.history, key=lambda h: abs(h[0] - target), default=None)
            if nearest and nearest[1] not in offsets:
                offsets.append(nearest[1])
        return offsets or [event.frame_offset]

    def flag(self, bench: Bench, event: BenchEvent, reason: str, expected: str, actual: str | None, offsets: list[int]) -> str:
        run = bench.run
        flag = Flag(
            id=str(uuid.uuid4()),
            bench=bench.id,
            run_id=run.run_id,
            event=event,
            reason=reason,
            expected_step=expected,
            actual_step=actual,
            unit_revision=run.revision,
            frame_offsets=offsets,
            completed_steps=[*run.done, *run.waived],
        )
        publish(self.kafka, FLAGS, flag, bench.id)
        return flag.id

    def on_track(self, track: HandTrack) -> None:
        bench = self.bench(track.bench)
        now = track.times.get("t_ingest") or time.time()
        bench.history.append((now, track.frame_offset))
        if bench.run is None:
            return

        for kind, zone in bench.tracker.update(track.hands, now):
            run = bench.run
            event = BenchEvent(
                id=str(uuid.uuid4()),
                bench=bench.id,
                run_id=run.run_id,
                kind=kind,
                zone=zone,
                frame_offset=track.frame_offset,
                times=stamp(track.times, "sequencer"),
            )
            publish(self.kafka, BENCH_EVENTS, event, bench.id)

            if kind == "pick":
                outputs = logic.on_pick(run, bench.procedure, zone)
            elif kind == "place":
                outputs = logic.on_place(run)
            else:
                outputs = logic.on_hands_clear(run)

            for output in outputs:
                if isinstance(output, logic.Recheck):
                    self.send_rechecks(bench, [output])
                elif isinstance(output, logic.OutOfSequence):
                    flag_id = self.flag(
                        bench, event, "out_of_sequence", output.expected, output.actual, self.evidence(bench, event)
                    )
                    alert = ReflexAlert(
                        id=str(uuid.uuid4()),
                        bench=bench.id,
                        run_id=run.run_id,
                        flag_id=flag_id,
                        step_id=output.expected,
                        text=output.text,
                        clip=output.clip,
                        times=event.times,
                    )
                    publish(self.kafka, ALERTS_REFLEX, alert, bench.id)
                elif run.photo_checks:
                    self.flag(bench, event, "step_check", output.step_id, None, [track.frame_offset])
            self.publish_state(bench)


def main() -> None:
    kafka = producer()
    sequencer = Sequencer(kafka)
    c = consumer("sequencer", [HAND_TRACKS, RUN_CONTROL, VERDICTS])
    print("sequencer ready", flush=True)
    while True:
        msg = c.poll(0.2)
        if msg is None:
            continue
        if msg.error():
            print(f"kafka: {msg.error()}", flush=True)
            continue
        body = json.loads(msg.value())
        if msg.topic() == HAND_TRACKS:
            sequencer.on_track(HandTrack(**body))
        elif msg.topic() == RUN_CONTROL:
            sequencer.on_control(RunControl(**body))
        else:
            sequencer.on_verdict(Verdict(**body))


if __name__ == "__main__":
    main()
