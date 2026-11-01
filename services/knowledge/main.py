"""Loads a manual: python -m services.knowledge.main manual/vdn1.md"""

import argparse
from pathlib import Path

from services.knowledge.embed import backend
from services.knowledge.extract import extract
from services.knowledge.parse import hierarchy, read_pages
from services.knowledge.store import approve, propose, save


def ingest_text(pages: list[tuple[int, str]], title: str) -> tuple[int, int, dict]:
    raw = "\n".join(text for _, text in pages)
    sections = hierarchy(pages)
    procedure = extract(raw)
    doc_id = save(title, procedure.revision, raw, len(pages), sections, procedure)
    procedure_id = propose(doc_id, procedure)
    leaves = sum(len(s.leaves) for s in sections)
    return doc_id, procedure_id, {
        "pages": len(pages),
        "sections": len(sections),
        "leaves": leaves,
        "steps": len(procedure.steps),
        "embedder": backend(),
        "procedure": procedure.model_dump(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    args = parser.parse_args()
    doc_id, procedure_id, report = ingest_text(read_pages(args.path), args.path.stem)
    approve(procedure_id, "setup")  # running this by hand is the approval
    report.pop("procedure")
    print(f"document {doc_id}, procedure {procedure_id}: {report}")


if __name__ == "__main__":
    main()
