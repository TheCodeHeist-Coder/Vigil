"""Clears runs, verdicts, incidents and agent memory, so test data cannot inflate results.

The manual and its embeddings stay. Run this once before the real test runs.
"""

from common.db import connect


def main() -> None:
    with connect() as db:
        for table in ("incidents", "verdicts", "runs", "agent_memory"):
            db.execute(f"DELETE FROM {table}")
    print("cleared runs, verdicts, incidents and agent memory")


if __name__ == "__main__":
    main()
