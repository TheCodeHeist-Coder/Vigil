"""Hierarchical search: find the right sections, then the best leaves inside them."""

from dataclasses import dataclass

from common.db import connect, vector
from services.knowledge.embed import embed
from services.knowledge.store import active_doc_id

TOP_SECTIONS = 3
TOP_LEAVES = 5


@dataclass(frozen=True)
class Excerpt:
    section: str
    page: int
    title: str
    body: str
    reason: str  # "step" came from an exact tag, "search" from vector search


def search(query: str, step_ids: list[str] | None = None) -> list[Excerpt]:
    query_vector = vector(embed([query])[0])
    with connect() as db:
        doc_id = active_doc_id(db)
        if doc_id is None:
            return []

        found: dict[str, Excerpt] = {}

        # Step text is fetched exactly, so it never depends on embedding quality.
        if step_ids:
            rows = db.execute(
                "SELECT section, page, path, body FROM chunks WHERE doc_id = %s AND level = 'leaf' AND step_id = ANY(%s)",
                (doc_id, step_ids),
            ).fetchall()
            for section, page, path, body in rows:
                found[section] = Excerpt(section, page, path[-1], body, "step")

        sections = db.execute(
            """SELECT id FROM chunks WHERE doc_id = %s AND level = 'section'
               ORDER BY embedding <=> %s::vector LIMIT %s""",
            (doc_id, query_vector, TOP_SECTIONS),
        ).fetchall()
        parents = [row[0] for row in sections]
        rows = db.execute(
            """SELECT section, page, path, body FROM chunks
               WHERE doc_id = %s AND level = 'leaf' AND parent_id = ANY(%s)
               ORDER BY embedding <=> %s::vector LIMIT %s""",
            (doc_id, parents, query_vector, TOP_LEAVES),
        ).fetchall()
        for section, page, path, body in rows:
            found.setdefault(section, Excerpt(section, page, path[-1], body, "search"))
    return list(found.values())
