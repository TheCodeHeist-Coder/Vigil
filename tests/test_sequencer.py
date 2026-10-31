import json

from common.config import ROOT
from contracts.models import Procedure, Verdict, Zone
from services.sequencer import logic
from services.sequencer.zones import ZoneTracker, inside

PROCEDURE = Procedure(**json.loads((ROOT / "manual" / "procedure.json").read_text()))
ZONES = [Zone(**z) for z in json.loads((ROOT / "manual" / "zones.json").read_text())]
REST = (0.5, 0.95)
BIN_A = (0.12, 0.2)
TRAY = (0.5, 0.6)


def do_step(run: logic.Run, zone: str):
    outputs = logic.on_pick(run, PROCEDURE, zone)
    logic.on_place(run)
    return outputs + logic.on_hands_clear(run)


def verdict(run: logic.Run, reason: str, status: str, step_id: str) -> Verdict:
    return Verdict(flag_id="f", bench="b", run_id=run.run_id, step_id=step_id, reason=reason, status=status, explanation="")


def test_clean_run_finishes_every_step():
    run = logic.Run("r")
    for zone in "ABCDE":
        outputs = do_step(run, zone)
        assert all(isinstance(o, logic.StepFinished) for o in outputs)
    assert run.done == ["S1", "S2", "S3", "S4", "S5"]
    assert logic.finished(run, PROCEDURE)


def test_e1_module_before_gasket_flags_and_names_the_fix():
    run = logic.Run("r")
    outputs = logic.on_pick(run, PROCEDURE, "B")
    assert len(outputs) == 1
    assert outputs[0].expected == "S1" and outputs[0].actual == "S2"
    assert outputs[0].text == "Stop. Install the gasket first."
    assert run.held == ("S1", "S2")


def test_same_error_is_not_repeated_while_held():
    run = logic.Run("r")
    logic.on_pick(run, PROCEDURE, "B")
    assert logic.on_pick(run, PROCEDURE, "B") == []


def test_correct_pick_releases_the_hold():
    run = logic.Run("r")
    logic.on_pick(run, PROCEDURE, "B")
    assert logic.on_pick(run, PROCEDURE, "A") == []
    assert run.held is None and run.active == "S1"


def test_e3_cleared_verdict_waives_the_skipped_step():
    run = logic.Run("r", revision="B")
    logic.on_pick(run, PROCEDURE, "B")
    logic.on_verdict(run, PROCEDURE, verdict(run, "out_of_sequence", "cleared", "S1"))
    assert run.waived == ["S1"] and run.active == "S2" and run.held is None
    for zone in "CDE":
        logic.on_place(run)
        logic.on_hands_clear(run)
        logic.on_pick(run, PROCEDURE, zone)
    logic.on_place(run)
    logic.on_hands_clear(run)
    assert logic.finished(run, PROCEDURE)


def test_confirmed_verdict_keeps_the_hold():
    run = logic.Run("r")
    logic.on_pick(run, PROCEDURE, "B")
    logic.on_verdict(run, PROCEDURE, verdict(run, "out_of_sequence", "confirmed", "S1"))
    assert run.held == ("S1", "S2")


def test_e2_failed_step_check_reopens_the_step():
    run = logic.Run("r")
    for zone in "ABC":
        do_step(run, zone)
    logic.on_verdict(run, PROCEDURE, verdict(run, "step_check", "confirmed", "S3"))
    assert run.done == ["S1", "S2"]
    assert logic.on_pick(run, PROCEDURE, "C") == []
    assert run.active == "S3"


def test_inside_polygon():
    tray = next(z for z in ZONES if z.kind == "tray")
    assert inside(TRAY, tray.polygon)
    assert not inside(REST, tray.polygon)


def test_brief_touch_is_not_a_pick():
    tracker = ZoneTracker(ZONES)
    assert tracker.update([BIN_A], 0.0) == []
    assert tracker.update([REST], 0.1) == []
    assert tracker.update([BIN_A], 0.15) == []


def test_pick_place_and_hands_clear_fire_once_each():
    tracker = ZoneTracker(ZONES)
    events = []
    timeline = [(BIN_A, 0.0), (BIN_A, 0.25), (BIN_A, 0.4), (REST, 0.5), (TRAY, 0.6), (TRAY, 0.85), (TRAY, 1.0), (REST, 1.1), (REST, 1.5), (REST, 1.9)]
    for point, now in timeline:
        events += tracker.update([point], now)
    assert events == [("pick", "A"), ("place", "TRAY"), ("hands_clear", "TRAY")]


def test_hand_in_tray_without_a_pick_is_not_a_place():
    tracker = ZoneTracker(ZONES)
    assert tracker.update([TRAY], 0.0) == []
    assert tracker.update([TRAY], 0.5) == []
