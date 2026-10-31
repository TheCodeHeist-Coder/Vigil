"""Plays a scripted operator through hand.tracks, so a whole run can be tested with no bench.

  python -m tools.simulate_run clean
  python -m tools.simulate_run e1
  python -m tools.simulate_run e3 --revision B
"""

import argparse
import json
import time
import uuid

from common.bus import producer, publish
from common.config import ROOT, settings
from contracts.models import HandTrack, RunControl, Zone
from contracts.topics import HAND_TRACKS, RUN_CONTROL

FPS = 15
REST = (0.5, 0.95)  # a resting hand, outside every zone
TRAY = "TRAY"

SCENARIOS = {
    "clean": ["A", "B", "C", "D", "E"],
    "e1": ["B"],  # picks the module before the gasket
    "e2": ["A", "B", "C"],  # the hand path is normal, the cable goes through notch B
    "e3": ["B", "C", "D", "E"],  # Rev B skips the gasket
}


def centre(zone: Zone) -> tuple[float, float]:
    xs, ys = zip(*zone.polygon)
    return sum(xs) / len(xs), sum(ys) / len(ys)


def path(zones: dict[str, Zone], visits: list[str], rest_frames: int = 15):
    """Yields hand positions: rest, bin, tray, rest for each visit."""
    for bin_id in visits:
        for target, frames in ((REST, 3), (centre(zones[bin_id]), 6), (REST, 2), (centre(zones[TRAY]), 6), (REST, rest_frames)):
            for _ in range(frames):
                yield target


def play(scenario: str, revision: str, bench: str, serial: str | None = None, gap_after_bin: bool = True) -> str:
    zones = {z["id"]: Zone(**z) for z in json.loads((ROOT / "manual" / "zones.json").read_text())}
    p = producer()
    run_id = str(uuid.uuid4())
    publish(p, RUN_CONTROL, RunControl(kind="start", bench=bench, run_id=run_id, serial=serial or f"SIM-{run_id[:6]}", revision=revision), bench)
    p.flush(5)
    time.sleep(0.5)
    # A real operator stops at an alert, so e3 waits long enough for each verdict.
    rest_frames = 60 if scenario == "e3" else 15
    for i, point in enumerate(path(zones, SCENARIOS[scenario], rest_frames)):
        now = time.time()
        track = HandTrack(
            bench=bench,
            frame_offset=i,
            hands=[point],
            source="simulated",
            times={"t_capture": now, "t_ingest": now, "t_edge": now},
        )
        publish(p, HAND_TRACKS, track, bench)
        time.sleep(1 / FPS)
    p.flush(5)
    return run_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--revision", default="A", choices=["A", "B"])
    parser.add_argument("--bench", default=settings.bench_id)
    args = parser.parse_args()
    print("run", play(args.scenario, args.revision, args.bench))


if __name__ == "__main__":
    main()
