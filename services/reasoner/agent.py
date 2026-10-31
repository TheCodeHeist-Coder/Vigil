"""The incident agent. After a confirmed fault it works out what happened and what to do."""

import uuid

from common.config import settings
from common.db import connect
from contracts.models import Flag, Incident, Procedure, Verdict
from services.knowledge.retrieve import search
from services.reasoner.context import INCIDENT_AGENT, AgentContext

REPEAT_LIMIT = 3  # manual section 6.4

SYSTEM = """You write the incident record for one confirmed assembly fault.
Use your tools: read what happened in this run, search the manual, and check past incidents at this step.
Then write 3 to 5 plain sentences: the fault, the rework in order, the manual sections that apply,
and whether this step keeps failing. If a step has failed three times, say so and name manual section 6.4.
The rework steps you are given are computed from the procedure. Do not change them."""


def rework_steps(procedure: Procedure, failed: str, completed: list[str]) -> list[str]:
    """Everything completed that depends on the failed step comes off first, latest first."""
    dependents: set[str] = set()
    changed = True
    while changed:
        changed = False
        for step in procedure.steps:
            if step.id in dependents:
                continue
            if failed in step.requires or dependents & set(step.requires):
                dependents.add(step.id)
                changed = True

    order = [s.id for s in procedure.steps]
    undo = sorted((s for s in dependents if s in completed), key=order.index, reverse=True)
    plan = [f"Undo {step_id}: {procedure.step(step_id).title}" for step_id in undo]
    plan.append(f"Do {failed}: {procedure.step(failed).title}")
    return plan


def past_count(step_id: str) -> int:
    with connect() as db:
        return db.execute("SELECT count(*) FROM incidents WHERE step_id = %s", (step_id,)).fetchone()[0]


def template_report(verdict: Verdict, rework: list[str], occurrences: int) -> str:
    sections = ", ".join(c.section for c in verdict.citations) or "none"
    report = f"Confirmed fault at {verdict.step_id}. {verdict.explanation} Rework: {'; '.join(rework)}. Manual sections: {sections}."
    if occurrences >= REPEAT_LIMIT:
        report += f" This is fault {occurrences} at this step, so manual section 6.4 applies: stop and raise it with the process engineer."
    return report


def agent_report(flag: Flag, verdict: Verdict, procedure: Procedure, rework: list[str], occurrences: int, notes: list[str]) -> str:
    from google import genai
    from google.genai import types

    def get_run() -> dict:
        """Returns what is known about this run."""
        return {
            "unit_revision": flag.unit_revision,
            "completed_steps": flag.completed_steps,
            "fault_step": verdict.step_id,
            "attempted_step": flag.actual_step,
            "verdict": verdict.explanation,
        }

    def search_manual(query: str) -> list[dict]:
        """Searches the assembly manual and returns matching sections."""
        return [{"section": e.section, "page": e.page, "text": e.body} for e in search(query)]

    def past_incidents(step_id: str) -> dict:
        """Returns how many incidents this step has had, and notes from earlier runs."""
        return {"count": past_count(step_id), "notes": notes}

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=(
            f"Fault at {verdict.step_id}, occurrence {occurrences}. Rework steps: {rework}. "
            f"Sections the verdict cited: {[c.section for c in verdict.citations]}."
        ),
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0,
            tools=[get_run, search_manual, past_incidents],
        ),
    )
    return response.text


def investigate(flag: Flag, verdict: Verdict, procedure: Procedure, context: AgentContext) -> Incident:
    rework = rework_steps(procedure, verdict.step_id, flag.completed_steps)
    occurrences = past_count(verdict.step_id) + 1
    notes = context.recall(verdict.step_id)
    report = ""
    if settings.gemini_api_key:
        try:
            report = agent_report(flag, verdict, procedure, rework, occurrences, notes)
        except Exception as error:
            print(f"incident agent failed, using template: {error}", flush=True)
    report = report or template_report(verdict, rework, occurrences)
    if occurrences >= REPEAT_LIMIT and "6.4" not in report:
        report += f" This is fault {occurrences} at this step, so manual section 6.4 applies: stop and raise it with the process engineer."

    incident = Incident(
        id=str(uuid.uuid4()),
        bench=flag.bench,
        run_id=flag.run_id,
        step_id=verdict.step_id,
        rework=rework,
        report=report,
        occurrences=occurrences,
        memory_backend=context.backend,
    )
    with connect() as db:
        db.execute(
            "INSERT INTO incidents (id, run_id, step_id, rework, report) VALUES (%s, %s, %s, %s, %s)",
            (incident.id, incident.run_id, incident.step_id, incident.rework, incident.report),
        )
    context.remember(flag.run_id, verdict.step_id, f"Fault {occurrences} at {verdict.step_id}: {verdict.explanation}")
    context.trace(flag.run_id, INCIDENT_AGENT, f"Investigate fault at {verdict.step_id}", report, f"Rework: {rework}")
    return incident
