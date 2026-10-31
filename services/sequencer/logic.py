"""Step rules. Pure functions with no network, so the reflex can never wait on one."""

from dataclasses import dataclass, field

from contracts.models import Procedure, Verdict


@dataclass
class Run:
    run_id: str
    serial: str = ""
    revision: str = "A"
    photo_checks: bool = True
    done: list[str] = field(default_factory=list)
    waived: list[str] = field(default_factory=list)
    active: str | None = None
    placed: bool = False
    held: tuple[str, str] | None = None  # (expected step, attempted step)
    awaiting_verdict: bool = False
    held_placed: bool = False  # work done during a hold, credited if the verdict clears it
    held_cleared: bool = False

    def complete(self, step_id: str) -> bool:
        return step_id in self.done or step_id in self.waived


@dataclass
class OutOfSequence:
    expected: str
    actual: str
    text: str
    clip: str


@dataclass
class StepFinished:
    step_id: str


Output = OutOfSequence | StepFinished


def on_pick(run: Run, procedure: Procedure, zone: str) -> list[Output]:
    step = procedure.step_for_bin(zone)
    if step is None or run.complete(step.id):
        return []

    missing = [r for r in step.requires if not run.complete(r)]
    if missing:
        expected = procedure.step(missing[0])
        pair = (expected.id, step.id)
        if run.held == pair or run.awaiting_verdict:
            return []  # one flag at a time, and a hand re-entering the bin must not repeat it
        run.held = pair
        run.awaiting_verdict = True
        run.held_placed = run.held_cleared = False
        run.active = None
        return [OutOfSequence(expected.id, step.id, expected.correction, expected.clip)]

    run.held = None
    run.active = step.id
    run.placed = False
    return []


def on_place(run: Run) -> list[Output]:
    if run.held:
        run.held_placed = True
    if run.active:
        run.placed = True
    return []


def on_hands_clear(run: Run) -> list[Output]:
    if run.held and run.held_placed:
        run.held_cleared = True
    if not run.active or not run.placed:
        return []
    finished = run.active
    run.done.append(finished)
    run.active = None
    run.placed = False
    return [StepFinished(finished)]


def on_verdict(run: Run, procedure: Procedure, verdict: Verdict) -> list[Output]:
    if verdict.reason == "out_of_sequence":
        run.awaiting_verdict = False
        if verdict.status == "cleared" and run.held:
            # The manual allows this unit to skip ahead, so the skipped steps count as waived.
            expected, actual = run.held
            attempted = procedure.step(actual)
            for step_id in attempted.requires if attempted else []:
                if not run.complete(step_id):
                    run.waived.append(step_id)
            run.held = None
            run.active = actual
            # The verdict takes seconds, so the operator may have finished this step already.
            run.placed = run.held_placed
            return on_hands_clear(run) if run.held_cleared else []
    elif verdict.reason == "step_check" and verdict.status == "confirmed":
        # The step looked wrong, so it must be done again.
        if verdict.step_id in run.done:
            run.done.remove(verdict.step_id)
            run.held = None
    return []


def finished(run: Run, procedure: Procedure) -> bool:
    return all(run.complete(step.id) for step in procedure.steps)
