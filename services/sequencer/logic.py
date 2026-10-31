"""Step rules. Pure functions with no network, so the reflex can never wait on one."""

from dataclasses import dataclass, field

from contracts.models import Procedure, Verdict


@dataclass
class Run:
    run_id: str
    serial: str = ""
    revision: str = "A"
    done: list[str] = field(default_factory=list)
    waived: list[str] = field(default_factory=list)
    active: str | None = None
    placed: bool = False
    held: tuple[str, str] | None = None  # (expected step, attempted step)

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
        if run.held == pair:
            return []  # already flagged, and a hand re-entering the bin must not repeat it
        run.held = pair
        run.active = None
        return [OutOfSequence(expected.id, step.id, expected.correction, expected.clip)]

    run.held = None
    run.active = step.id
    run.placed = False
    return []


def on_place(run: Run) -> list[Output]:
    if run.active:
        run.placed = True
    return []


def on_hands_clear(run: Run) -> list[Output]:
    if not run.active or not run.placed:
        return []
    finished = run.active
    run.done.append(finished)
    run.active = None
    run.placed = False
    return [StepFinished(finished)]


def on_verdict(run: Run, procedure: Procedure, verdict: Verdict) -> None:
    if verdict.reason == "out_of_sequence" and verdict.status == "cleared" and run.held:
        # The manual allows this unit to skip ahead, so the skipped steps count as waived.
        expected, actual = run.held
        attempted = procedure.step(actual)
        for step_id in attempted.requires if attempted else []:
            if not run.complete(step_id):
                run.waived.append(step_id)
        run.held = None
        run.active = actual
        run.placed = False
    elif verdict.reason == "step_check" and verdict.status == "confirmed":
        # The step looked wrong, so it must be done again.
        if verdict.step_id in run.done:
            run.done.remove(verdict.step_id)
            run.held = None


def finished(run: Run, procedure: Procedure) -> bool:
    return all(run.complete(step.id) for step in procedure.steps)
