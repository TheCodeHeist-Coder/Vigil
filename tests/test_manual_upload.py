from fastapi.testclient import TestClient

from contracts.models import Procedure, Step
from services.gateway import main as gateway


def post(name: str, data: bytes, monkeypatch, ingested: list):
    def fake_ingest(pages, title):
        ingested.append((pages, title))
        return 1, 2, {"pages": len(pages), "sections": 1, "leaves": 1, "steps": 1, "embedder": "x", "procedure": {"steps": []}}

    monkeypatch.setattr(gateway, "ingest_text", fake_ingest)
    client = TestClient(gateway.app, client=("127.0.0.1", 5000))  # this laptop needs no key
    return client.post("/api/manual/upload", files={"file": (name, data)})


def test_wrong_file_type_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(gateway, "MANUAL", tmp_path / "m.md")
    ingested = []
    assert post("manual.docx", b"x", monkeypatch, ingested).status_code == 400
    assert ingested == []


def test_empty_file_is_refused_with_a_reason(monkeypatch, tmp_path):
    monkeypatch.setattr(gateway, "MANUAL", tmp_path / "m.md")
    response = post("manual.txt", b"   ", monkeypatch, [])
    assert response.status_code == 400 and "readable text" in response.json()["detail"]


def test_text_with_no_numbered_sections_is_refused(monkeypatch, tmp_path):
    monkeypatch.setattr(gateway, "MANUAL", tmp_path / "m.md")
    response = post("manual.txt", b"Just some words about a product.", monkeypatch, [])
    assert response.status_code == 400 and "numbered sections" in response.json()["detail"]


def test_good_manual_is_read_and_proposed(monkeypatch, tmp_path):
    saved = tmp_path / "m.md"
    monkeypatch.setattr(gateway, "MANUAL", saved)
    ingested = []
    text = b"## 4 Assembly\n### 4.1 Fit the board\nTake the board from bin A.\n"
    response = post("my-manual.md", text, monkeypatch, ingested)
    assert response.status_code == 200 and response.json()["procedure_id"] == 2
    assert ingested[0][1] == "my-manual"
    assert "4.1 Fit the board" in saved.read_text()


def test_approving_a_manual_renames_bins_and_keeps_their_positions():
    box = [[0.1, 0.1], [0.2, 0.1], [0.2, 0.2], [0.1, 0.2]]
    zones = [
        {"id": "A", "label": "Bin A · STM32", "kind": "bin", "polygon": box},
        {"id": "F", "label": "Bin F · Old", "kind": "bin", "polygon": box},
        {"id": "TRAY", "label": "Breadboard", "kind": "tray", "polygon": box},
    ]
    step = Step(id="S1", section="4.1", title="t", bin="A", part="Arduino", check="c", correction="x")
    named = gateway.zones_for(Procedure(steps=[step]), zones)
    assert [z.label for z in named] == ["Bin A · Arduino", "Bin F", "Breadboard"]
    assert named[0].polygon == [tuple(p) for p in box]
