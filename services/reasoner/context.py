"""Agent context: what the agents remember between runs.

Meko holds memory, conversations and decision traces when MEKO_API_KEY is set. Otherwise
memory stays in YugabyteDB. Every Meko call runs on its own thread, so a slow network
can never delay a verdict. Agents read notes fetched ahead of time, never live.
"""

import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from common.config import settings
from common.db import connect
from services.reasoner.meko import MekoClient

VERDICT_AGENT = "vigil-verdict"
INCIDENT_AGENT = "vigil-incident"


def _items(result: Any) -> list:
    return (result.get("results") or []) if isinstance(result, dict) else (result or [])


def memories(result: Any) -> list[str]:
    return [item["memory"] if isinstance(item, dict) else str(item) for item in _items(result)]


def notes_by_step(result: Any) -> dict[str, list[str]]:
    notes: dict[str, list[str]] = {}
    for item in _items(result):
        step_id = (item.get("metadata") or {}).get("step_id")
        if step_id:
            notes.setdefault(step_id, []).append(item["memory"])
    return notes


@dataclass
class AgentContext:
    client: MekoClient | None = None
    datapack_id: str | None = None
    conversations: dict[str, str] = field(default_factory=dict)
    notes: dict[str, list[str]] = field(default_factory=dict)
    error: str = ""
    worker: ThreadPoolExecutor = field(default_factory=lambda: ThreadPoolExecutor(1, thread_name_prefix="meko"))

    @property
    def backend(self) -> str:
        return "meko" if self.client and not self.error else "yugabyte"

    def _background(self, fn, *args) -> None:
        def guarded() -> None:
            try:
                fn(*args)
            except Exception as error:  # Meko must never stop the bench
                self.error = str(error)[:200]
                print(f"meko: {self.error}", flush=True)

        self.worker.submit(guarded)

    def _conversation(self, run_id: str, title: str = "") -> str:
        if run_id in self.conversations:
            return self.conversations[run_id]
        created = self.client.call(
            "conversation_create",
            agent_id=VERDICT_AGENT,
            session_id=run_id,
            datapack_id=self.datapack_id,
            title=title or f"Run {run_id[:8]}",
            run_id=run_id,
        )
        self.conversations[run_id] = created["id"]
        return created["id"]

    def _find_datapack(self) -> None:
        # Meko needs a conversation before it will search datapacks.
        start = self.client.call("conversation_create", agent_id=VERDICT_AGENT, session_id=str(uuid.uuid4()), title="Vigil start")
        found = self.client.call("datapack_search", name=settings.meko_datapack_name, conversation_id=start["id"])
        packs = found.get("datapacks") or []
        if packs:
            self.datapack_id = packs[0].get("datapack_id") or packs[0].get("id")
        else:
            created = self.client.call("datapack_create", name=settings.meko_datapack_name, conversation_id=start["id"])
            self.datapack_id = created["datapack_id"]

    def _start_run(self, run_id: str, title: str) -> None:
        if not self.datapack_id:
            self._find_datapack()
        conversation = self._conversation(run_id, title)
        # memory_search takes about 10 s, so one search runs here on Meko's own thread.
        found = self.client.call(
            "memory_search",
            query="assembly faults and rework at each step",
            conversation_id=conversation,
            agent_id=VERDICT_AGENT,
            datapack_id=self.datapack_id,
            limit=20,
        )
        self.notes.update(notes_by_step(found))
        self.error = ""

    def start_run(self, run_id: str, serial: str, steps: list[str]) -> None:
        """Loads notes ahead of time, so verdicts can read them instantly."""
        with connect() as db:
            for step_id in steps:
                rows = db.execute(
                    "SELECT note FROM agent_memory WHERE step_id = %s ORDER BY created_at DESC LIMIT 3",
                    (step_id,),
                ).fetchall()
                self.notes[step_id] = [row[0] for row in rows]
        if self.client:
            self._background(self._start_run, run_id, f"Unit {serial}")

    def recall(self, step_id: str) -> list[str]:
        return self.notes.get(step_id, [])

    def _remember(self, run_id: str, step_id: str, note: str) -> None:
        self.client.call(
            "memory_add",
            text=note,
            conversation_id=self._conversation(run_id),
            agent_id=INCIDENT_AGENT,
            run_id=run_id,
            metadata=json.dumps({"step_id": step_id}),  # Meko takes metadata as a JSON string
            datapack_id=self.datapack_id,
        )

    def remember(self, run_id: str, step_id: str, note: str) -> None:
        self.notes.setdefault(step_id, []).insert(0, note)
        with connect() as db:  # YugabyteDB keeps a copy, so a Meko outage loses nothing
            db.execute("INSERT INTO agent_memory (step_id, note) VALUES (%s, %s)", (step_id, note))
        if self.client:
            self._background(self._remember, run_id, step_id, note)

    def _trace(self, run_id: str, agent: str, question: str, answer: str, reasoning: str) -> None:
        self.client.call(
            "conversation_add_message",
            conversation_id=self._conversation(run_id),
            input=question,
            output=answer,
            agent_id=agent,
            reasoning=reasoning,
            datapack_id=self.datapack_id,
        )

    def trace(self, run_id: str, agent: str, question: str, answer: str, reasoning: str) -> None:
        """Records why an agent decided, so the next agent inherits the reasoning."""
        if self.client:
            self._background(self._trace, run_id, agent, question, answer, reasoning)


def build_context() -> AgentContext:
    if not settings.meko_api_key:
        return AgentContext()
    return AgentContext(client=MekoClient(settings.meko_mcp_url, settings.meko_api_key))
