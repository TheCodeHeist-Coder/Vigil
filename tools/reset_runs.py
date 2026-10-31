"""Clears runs, verdicts, incidents and agent memory, so test data cannot inflate results.

The manual and its embeddings stay. Run this once before the real test runs.
"""

from common.config import settings
from common.db import connect
from services.reasoner.context import INCIDENT_AGENT, build_context


def clear_meko() -> None:
    context = build_context()
    context._find_datapack()
    conversation = context._conversation("00000000-0000-4000-8000-000000000000", "Reset")
    context.client.call("memory_delete_all", conversation_id=conversation, agent_id=INCIDENT_AGENT, datapack_id=context.datapack_id)
    print("cleared Meko memory")


def main() -> None:
    with connect() as db:
        for table in ("incidents", "verdicts", "runs", "agent_memory"):
            db.execute(f"DELETE FROM {table}")
    print("cleared runs, verdicts, incidents and agent memory")
    if settings.meko_api_key:
        clear_meko()


if __name__ == "__main__":
    main()
