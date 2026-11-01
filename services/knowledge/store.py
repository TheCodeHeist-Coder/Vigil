"""Writes the manual to YugabyteDB as two levels of embedded chunks."""

import hashlib
import json

from common.db import connect, vector
from contracts.models import Procedure
from services.knowledge.embed import embed
from services.knowledge.parse import Section


def section_text(section: Section) -> str:
    """A section embeds its title and child headings, so no LLM summary is needed."""
    children = "; ".join(f"{leaf.section} {leaf.title}" for leaf in section.leaves)
    first = section.leaves[0].body[:300]
    return f"{section.section} {section.title}. Contains: {children}. {first}"


def leaf_text(section: Section, leaf_title: str, body: str) -> str:
    return f"{section.title} > {leaf_title}\n{body}"


def save(title: str, revision: str, raw: str, pages: int, sections: list[Section], procedure: Procedure) -> int:
    step_for_section = {step.section: step.id for step in procedure.steps}
    section_vectors = embed([section_text(s) for s in sections])
    leaves = [(s, leaf) for s in sections for leaf in s.leaves]
    leaf_vectors = embed([leaf_text(s, leaf.title, leaf.body) for s, leaf in leaves])
    by_leaf = {id(leaf): values for (_, leaf), values in zip(leaves, leaf_vectors)}

    with connect() as db:
        doc_id = db.execute(
            "INSERT INTO documents (title, revision, pages, sha256) VALUES (%s, %s, %s, %s) RETURNING id",
            (title, revision, pages, hashlib.sha256(raw.encode()).hexdigest()),
        ).fetchone()[0]
        for section, values in zip(sections, section_vectors):
            parent = db.execute(
                """INSERT INTO chunks (doc_id, level, path, section, page, body, embedding)
                   VALUES (%s, 'section', %s, %s, %s, %s, %s::vector) RETURNING id""",
                (doc_id, [section.title], section.section, section.page, section_text(section), vector(values)),
            ).fetchone()[0]
            for leaf in section.leaves:
                db.execute(
                    """INSERT INTO chunks (doc_id, level, parent_id, path, section, page, step_id, body, embedding)
                       VALUES (%s, 'leaf', %s, %s, %s, %s, %s, %s, %s::vector)""",
                    (
                        doc_id,
                        parent,
                        [section.title, leaf.title],
                        leaf.section,
                        leaf.page,
                        step_for_section.get(leaf.section),
                        leaf.body,
                        vector(by_leaf[id(leaf)]),
                    ),
                )
    return doc_id


def propose(doc_id: int, procedure: Procedure) -> int:
    with connect() as db:
        return db.execute(
            "INSERT INTO procedures (doc_id, body) VALUES (%s, %s) RETURNING id",
            (doc_id, json.dumps(procedure.model_dump())),
        ).fetchone()[0]


def approve(procedure_id: int, engineer: str) -> Procedure:
    with connect() as db:
        row = db.execute(
            "UPDATE procedures SET approved_by = %s, approved_at = now() WHERE id = %s RETURNING body, doc_id",
            (engineer, procedure_id),
        ).fetchone()
    return Procedure(**{**row[0], "id": procedure_id, "doc_id": row[1]})


def active_doc_id(db) -> int | None:
    """The approved manual, so an unapproved edit can never change what agents cite."""
    row = db.execute(
        "SELECT doc_id FROM procedures WHERE approved_at IS NOT NULL ORDER BY approved_at DESC LIMIT 1"
    ).fetchone()
    if row is None:
        row = db.execute("SELECT id FROM documents ORDER BY created_at DESC LIMIT 1").fetchone()
    return row[0] if row else None
