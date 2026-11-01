import json

from common.config import ROOT
from contracts.models import Procedure, Verdict, Zone
from services.sequencer import logic
from services.sequencer.zones import ZoneTracker, inside

PROCEDURE = Procedure(**json.loads((ROOT / "tests" / "fixtures" / "procedure.json").read_text()))
ZONES = [Zone(**z) for z in json.loads((ROOT / "tests" / "fixtures" / "zones.json").read_text())]
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


def test_e3_work_done_before_the_verdict_arrives_is_credited():
    run = logic.Run("r", revision="B")
    logic.on_pick(run, PROCEDURE, "B")
    logic.on_place(run)
    logic.on_hands_clear(run)
    outputs = logic.on_verdict(run, PROCEDURE, verdict(run, "out_of_sequence", "cleared", "S1"))
    assert run.done == ["S2"] and run.waived == ["S1"] and run.active is None
    assert isinstance(outputs[0], logic.StepFinished) and outputs[0].step_id == "S2"


def test_no_second_flag_while_a_verdict_is_pending():
    run = logic.Run("r", revision="B")
    logic.on_pick(run, PROCEDURE, "B")
    assert logic.on_pick(run, PROCEDURE, "C") == []
    assert run.held == ("S1", "S2")


def test_new_error_can_flag_once_the_verdict_is_in():
    run = logic.Run("r")
    logic.on_pick(run, PROCEDURE, "B")
    logic.on_verdict(run, PROCEDURE, verdict(run, "out_of_sequence", "confirmed", "S1"))
    outputs = logic.on_pick(run, PROCEDURE, "C")
    assert outputs[0].expected == "S1" and outputs[0].actual == "S3"


def test_hand_test_run_still_finishes_every_step():
    run = logic.Run("r", photo_checks=False)
    for zone in "ABCDE":
        do_step(run, zone)
    assert logic.finished(run, PROCEDURE)


def test_alert_names_the_earliest_missing_step():
    run = logic.Run("r")
    do_step(run, "A")
    do_step(run, "B")
    outputs = logic.on_pick(run, PROCEDURE, "E")
    assert outputs[0].expected == "S3" and outputs[0].actual == "S5"


def stopped(run: logic.Run) -> None:
    logic.on_pick(run, PROCEDURE, "B")
    logic.on_verdict(run, PROCEDURE, verdict(run, "out_of_sequence", "confirmed", "S1"))


def test_hands_clear_after_a_stop_looks_at_the_fix():
    run = logic.Run("r")
    stopped(run)
    outputs = logic.on_hands_clear(run)
    assert isinstance(outputs[0], logic.Recheck) and outputs[0].step_id == "S1"


def test_a_passing_recheck_clears_the_stop_with_no_bin_visit():
    run = logic.Run("r")
    stopped(run)
    logic.request_recheck(run)
    logic.on_verdict(run, PROCEDURE, verdict(run, "step_check", "cleared", "S1"))
    assert run.held is None and run.done == ["S1"]
    assert logic.on_pick(run, PROCEDURE, "B") == [] and run.active == "S2"


def test_a_failing_recheck_keeps_the_stop_and_can_be_tried_again():
    run = logic.Run("r")
    stopped(run)
    logic.request_recheck(run)
    logic.on_verdict(run, PROCEDURE, verdict(run, "step_check", "confirmed", "S1"))
    assert run.held == ("S1", "S2") and run.rechecking is None
    logic.on_verdict(run, PROCEDURE, verdict(run, "step_check", "uncertain", "S1"))
    assert isinstance(logic.request_recheck(run)[0], logic.Recheck)


def test_no_recheck_before_the_first_verdict():
    run = logic.Run("r")
    logic.on_pick(run, PROCEDURE, "B")
    assert logic.request_recheck(run) == []


def test_only_one_recheck_at_a_time():
    run = logic.Run("r")
    stopped(run)
    assert len(logic.request_recheck(run)) == 1
    assert logic.request_recheck(run) == []


def test_failed_photo_check_can_be_fixed_by_a_recheck():
    run = logic.Run("r")
    for zone in "ABC":
        do_step(run, zone)
    logic.on_verdict(run, PROCEDURE, verdict(run, "step_check", "confirmed", "S3"))
    assert logic.blocking_step(run) == "S3"
    logic.request_recheck(run)
    logic.on_verdict(run, PROCEDURE, verdict(run, "step_check", "cleared", "S3"))
    assert run.done == ["S1", "S2", "S3"] and run.failed is None


def test_supervisor_release_ends_the_stop():
    run = logic.Run("r")
    stopped(run)
    logic.on_verdict(run, PROCEDURE, verdict(run, "supervisor_release", "cleared", "S1"))
    assert run.held is None and run.done == ["S1"]


def test_nothing_to_recheck_on_a_healthy_run():
    assert logic.request_recheck(logic.Run("r")) == []


def shared_bin_procedure() -> Procedure:
    def step(number: int, bin_id: str) -> dict:
        requires = [f"S{number - 1}"] if number > 1 else []
        return dict(id=f"S{number}", section=f"4.{number}", title=f"Step {number}", bin=bin_id, requires=requires, check="c", correction=f"Do {number}.")

    return Procedure(steps=[step(1, "A"), step(2, "B"), step(3, "C"), step(4, "C")])


def test_two_steps_can_share_one_bin():
    procedure = shared_bin_procedure()
    run = logic.Run("r")
    for zone in "ABCC":
        logic.on_pick(run, procedure, zone)
        logic.on_place(run)
        logic.on_hands_clear(run)
    assert run.done == ["S1", "S2", "S3", "S4"] and logic.finished(run, procedure)


def test_going_back_to_a_shared_bin_stays_on_the_same_step():
    procedure = shared_bin_procedure()
    run = logic.Run("r")
    for zone in "AB":
        logic.on_pick(run, procedure, zone)
        logic.on_place(run)
        logic.on_hands_clear(run)
    logic.on_pick(run, procedure, "C")
    logic.on_pick(run, procedure, "C")
    assert run.active == "S3" and run.held is None


def test_wires_before_the_display_is_flagged_on_a_shared_bin():
    procedure = shared_bin_procedure()
    run = logic.Run("r")
    logic.on_pick(run, procedure, "A")
    logic.on_place(run)
    logic.on_hands_clear(run)
    outputs = logic.on_pick(run, procedure, "C")
    assert outputs[0].expected == "S2" and outputs[0].actual == "S3"


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


def test_one_missed_detection_does_not_reset_a_pick():
    tracker = ZoneTracker(ZONES)
    assert tracker.update([BIN_A], 0.0) == []
    assert tracker.update([], 0.09) == []
    assert tracker.update([BIN_A], 0.21) == [("pick", "A")]


def test_hand_that_really_left_does_not_count():
    tracker = ZoneTracker(ZONES)
    tracker.update([BIN_A], 0.0)
    assert tracker.update([REST], 0.3) == []
    assert tracker.update([BIN_A], 0.35) == []
