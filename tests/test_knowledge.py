from dataclasses import replace

import pytest

from common.config import ROOT, settings
from common.db import connect
from services.knowledge import retrieve
from services.knowledge.extract import with_step_ids
from services.knowledge.main import ingest_text
from services.knowledge.store import approve
from services.knowledge.parse import hierarchy, read_pages, split_markdown

MANUAL = ROOT / "tests" / "fixtures" / "vg100.md"


def test_manual_has_ten_pages():
    assert len(read_pages(MANUAL)) == 10


def test_hierarchy_finds_chapters_and_steps():
    sections = hierarchy(read_pages(MANUAL))
    assert [s.section for s in sections] == ["1", "2", "3", "4", "5", "6", "7"]
    assembly = next(s for s in sections if s.section == "4")
    assert [leaf.section for leaf in assembly.leaves] == ["4", "4.1", "4.2", "4.3", "4.4", "4.5"]


def test_note_stays_with_its_step_and_page():
    sections = hierarchy(read_pages(MANUAL))
    step = next(leaf for s in sections for leaf in s.leaves if leaf.section == "4.1")
    assert "Note 4.1" in step.body and "skip step 4.1" in step.body
    assert step.page == 6


def test_section_spanning_pages_keeps_its_own_page():
    sections = hierarchy(read_pages(MANUAL))
    wiring = next(leaf for s in sections for leaf in s.leaves if leaf.section == "3.4")
    assert wiring.page == 5


def test_pdf_gives_the_same_structure_as_markdown():
    from_pdf = hierarchy(read_pages(ROOT / "tests" / "fixtures" / "vg100.pdf"))
    from_markdown = hierarchy(read_pages(MANUAL))
    assert len(read_pages(ROOT / "tests" / "fixtures" / "vg100.pdf")) == 10
    assert [s.section for s in from_pdf] == [s.section for s in from_markdown]
    pdf_step = next(leaf for s in from_pdf for leaf in s.leaves if leaf.section == "4.1")
    assert pdf_step.page == 6
    assert "skip step 4.1" in " ".join(pdf_step.body.split())


def test_extracted_steps_are_renumbered_with_their_dependencies():
    body = {
        "revision": "3",
        "steps": [
            {"id": "4.1", "section": "4.1", "title": "a", "bin": "A", "requires": [], "check": "c", "correction": "x"},
            {"id": "4.2", "section": "4.2", "title": "b", "bin": "B", "requires": ["4.1"], "check": "c", "correction": "y"},
        ],
    }
    procedure = with_step_ids(body)
    assert [s.id for s in procedure.steps] == ["S1", "S2"]
    assert procedure.steps[1].requires == ["S1"]


def test_unmarked_text_is_one_page():
    assert split_markdown("## 1 Scope\n### 1.1 Purpose\nText") == [(1, "## 1 Scope\n### 1.1 Purpose\nText")]


@pytest.mark.integration
def test_ingest_and_search_against_yugabyte(monkeypatch):
    monkeypatch.setattr("services.knowledge.embed.settings", replace(settings, gemini_api_key=""))
    monkeypatch.setattr("services.knowledge.extract.settings", replace(settings, gemini_api_key=""))
    doc_id, procedure_id, report = ingest_text(read_pages(MANUAL), "vg100-test")
    try:
        approve(procedure_id, "test")
        assert doc_id and procedure_id
        assert report["pages"] == 10 and report["steps"] == 5

        excerpts = retrieve.search("module installed before gasket", ["S1", "S2"])
        sections = {e.section: e for e in excerpts}
        assert {"4.1", "4.2"} <= set(sections)
        assert sections["4.1"].reason == "step"
        assert "Note 4.1" in sections["4.1"].body

        wiring = retrieve.search("cable notch B wiring path insulation damage")
        assert any(e.section in ("3.4", "4.3", "6.2") for e in wiring)
    finally:
        # Retrieval uses the newest document, so this test copy must not outlive the test.
        with connect() as db:
            db.execute("DELETE FROM procedures WHERE doc_id = %s", (doc_id,))
            db.execute("DELETE FROM chunks WHERE doc_id = %s", (doc_id,))
            db.execute("DELETE FROM documents WHERE id = %s", (doc_id,))
