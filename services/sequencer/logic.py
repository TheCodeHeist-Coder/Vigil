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
    failed: str | None = None  # a step that failed its photo check
    rechecking: str | None = None  # the step a fresh photo is checking now

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


@dataclass
class Recheck:
    step_id: str


Output = OutOfSequence | StepFinished | Recheck


def blocking_step(run: Run) -> str | None:
    """The step that has to be put right before work can carry on."""
    return run.held[0] if run.held else run.failed


def request_recheck(run: Run) -> list[Output]:
    """Looks at the bench again, because a fix does not always pass through the right bin."""
    step_id = blocking_step(run)
    if step_id is None or run.awaiting_verdict or run.rechecking:
        return []
    run.rechecking = step_id
    return [Recheck(step_id)]


def earliest_missing(run: Run, procedure: Procedure, step_id: str) -> str | None:
    """Walks back through the requirements, so the alert names the first step to do now."""
    found = None
    waiting = list(procedure.step(step_id).requires)
    while waiting:
        current = waiting.pop()
        if not run.complete(current):
            found = current
        waiting += procedure.step(current).requires
    return found


def on_pick(run: Run, procedure: Procedure, zone: str) -> list[Output]:
    # Several steps can share a bin, like two sets of wires from one pile, so take the next one.
    step = next((s for s in procedure.steps if s.bin == zone and not run.complete(s.id)), None)
    if step is None:
        return []

    missing = earliest_missing(run, procedure, step.id)
    if missing:
        expected = procedure.step(missing)
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
    if blocking_step(run) and not run.active:
        return request_recheck(run)  # hands are clear after a stop, so look at the fix
    if not run.active or not run.placed:
        return []
    finished = run.active
    run.done.append(finished)
    run.active = None
    run.placed = False
    if run.failed == finished:
        run.failed = None
    return [StepFinished(finished)]


def fixed(run: Run, step_id: str) -> None:
    """The step is right now, so the stop is over."""
    if not run.complete(step_id):
        run.done.append(step_id)
    run.held = None
    run.failed = None
    run.active = None
    run.placed = False
    run.awaiting_verdict = False


def on_verdict(run: Run, procedure: Procedure, verdict: Verdict) -> list[Output]:
    if verdict.reason == "supervisor_release":
        run.rechecking = None
        fixed(run, verdict.step_id)
        return []
    if verdict.reason == "step_check" and run.rechecking == verdict.step_id:
        run.rechecking = None
        if verdict.status == "cleared":
            fixed(run, verdict.step_id)
        return []
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
            run.failed = verdict.step_id
    return []


def finished(run: Run, procedure: Procedure) -> bool:
    return all(run.complete(step.id) for step in procedure.steps)
