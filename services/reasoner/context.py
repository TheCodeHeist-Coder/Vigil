"""Agent context: what the agents remember between runs.

Meko holds memory, conversations and decision traces when MEKO_API_KEY is set. Otherwise
memory stays in YugabyteDB. Every Meko call runs on its own thread, so a slow network
can never delay a verdict. Agents read notes fetched ahead of time, never live.
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from common.config import settings
from common.db import connect
from services.reasoner.meko import MekoClient

VERDICT_AGENT = "vigil-verdict"
INCIDENT_AGENT = "vigil-incident"


def _text(item: Any) -> str:
    if isinstance(item, dict):
        return str(item.get("memory") or item.get("text") or item.get("content") or item)
    return str(item)


def memories(result: Any) -> list[str]:
    if isinstance(result, dict):
        result = result.get("results") or result.get("memories") or result.get("items") or []
    return [_text(item) for item in result or []]


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
        conversation = created.get("conversation_id") or created.get("id") if isinstance(created, dict) else str(created)
        self.conversations[run_id] = conversation
        return conversation

    def _find_datapack(self, conversation_id: str | None = None) -> None:
        found = self.client.call("datapack_search", name=settings.meko_datapack_name, conversation_id=conversation_id)
        packs = found.get("datapacks") or found.get("results") or found.get("items") or [] if isinstance(found, dict) else found
        if packs:
            self.datapack_id = packs[0].get("datapack_id") or packs[0].get("id")
            return
        created = self.client.call("datapack_create", name=settings.meko_datapack_name, conversation_id=conversation_id)
        self.datapack_id = created.get("datapack_id") or created.get("id")

    def _start_run(self, run_id: str, title: str, steps: list[str]) -> None:
        if self.client is None:
            return
        if not self.datapack_id:
            self._find_datapack()
        conversation = self._conversation(run_id, title)
        for step_id in steps:
            self.notes[step_id] = memories(
                self.client.call(
                    "memory_search",
                    query=f"faults at step {step_id}",
                    conversation_id=conversation,
                    agent_id=VERDICT_AGENT,
                    datapack_id=self.datapack_id,
                    limit=3,
                )
            )
        self.error = ""

    def start_run(self, run_id: str, serial: str, steps: list[str]) -> None:
        """Opens the conversation and fetches notes, so verdicts can read them instantly."""
        if self.client:
            self._background(self._start_run, run_id, f"Unit {serial}", steps)
            return
        with connect() as db:
            for step_id in steps:
                rows = db.execute(
                    "SELECT note FROM agent_memory WHERE step_id = %s ORDER BY created_at DESC LIMIT 3",
                    (step_id,),
                ).fetchall()
                self.notes[step_id] = [row[0] for row in rows]

    def recall(self, step_id: str) -> list[str]:
        return self.notes.get(step_id, [])

    def _remember(self, run_id: str, step_id: str, note: str) -> None:
        self.client.call(
            "memory_add",
            text=note,
            conversation_id=self._conversation(run_id),
            agent_id=INCIDENT_AGENT,
            run_id=run_id,
            metadata={"step_id": step_id},
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
