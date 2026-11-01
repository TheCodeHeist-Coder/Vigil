"""The screens' only door into the system: HTTP for actions, WebSocket and MJPEG for live data."""

import asyncio
import json
import statistics
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from common.bus import producer, publish
from common.config import ROOT, settings
from common.db import connect
from contracts.models import Procedure, RunControl, Zone
from contracts.topics import RUN_CONTROL
from services.gateway.access import AccessKey
from services.gateway.ask import ask
from services.gateway.live import hub
from services.knowledge.main import ingest_text
from services.knowledge.parse import split_markdown
from services.knowledge.store import approve
from services.reasoner.meko import MekoClient

MANUAL = ROOT / "manual" / "vg100.md"
PROCEDURE = ROOT / "manual" / "procedure.json"
ZONES = ROOT / "manual" / "zones.json"
WEB_BUILD = ROOT / "web" / "dist"
VIDEO_FPS = 15

kafka = producer()
meko_status = (
    {"state": "checking", "detail": "Connecting to Meko."}
    if settings.meko_api_key
    else {"state": "off", "detail": "No MEKO_API_KEY set. Memory is in YugabyteDB."}
)


def check_meko() -> None:
    if not settings.meko_api_key:
        return
    client = MekoClient(settings.meko_mcp_url, settings.meko_api_key)
    try:
        tools = client.tools()
        meko_status.update(state="connected", detail=f"{len(tools)} tools available")
    except Exception as error:
        meko_status.update(state="error", detail=str(error)[:160])
    finally:
        client.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    hub.start(asyncio.get_running_loop())
    asyncio.get_running_loop().run_in_executor(None, check_meko)
    yield


app = FastAPI(title="vigil-gateway", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.add_middleware(AccessKey, key=settings.access_key)


class NewRun(BaseModel):
    serial: str
    revision: str = "A"
    photo_checks: bool = True
    bench: str = settings.bench_id


class ManualEdit(BaseModel):
    text: str


class Approval(BaseModel):
    engineer: str


class Question(BaseModel):
    question: str


def control(message: RunControl) -> None:
    publish(kafka, RUN_CONTROL, message, message.bench)
    kafka.flush(2)


@app.websocket("/ws/live")
async def live(socket: WebSocket) -> None:
    await hub.join(socket)
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        hub.leave(socket)


@app.post("/webrtc/offer")
async def webrtc_offer(request: Request) -> Response:
    """Lets one public address carry everything. Video itself still travels peer to peer."""
    async with httpx.AsyncClient(timeout=20) as client:
        upstream = await client.post(
            f"{settings.ingest_url}/webrtc/offer",
            content=await request.body(),
            headers={"Content-Type": "application/json"},
        )
    return Response(upstream.content, upstream.status_code, media_type="application/json")


@app.get("/video")
async def video() -> StreamingResponse:
    async def stream():
        seen = 0
        while True:
            if hub.jpeg and hub.frame_count != seen:
                seen = hub.frame_count
                yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + hub.jpeg + b"\r\n"
            await asyncio.sleep(1 / VIDEO_FPS)

    return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/status")
def status() -> dict:
    try:
        with connect() as db:
            db.execute("SELECT 1")
            documents = db.execute("SELECT count(*) FROM documents").fetchone()[0]
        database = "connected"
    except Exception:
        database, documents = "error", 0
    return {
        "model": settings.gemini_model if settings.gemini_api_key else "local-rules",
        "embedder": settings.gemini_embed_model if settings.gemini_api_key else "local-hash",
        "database": database,
        "documents": documents,
        "meko": meko_status,
        "replay": settings.replay,
        "camera_live": time.time() - hub.last_frame_at < 2,
    }


@app.post("/api/runs")
def start_run(body: NewRun) -> dict:
    run_id = str(uuid.uuid4())
    with connect() as db:
        db.execute("INSERT INTO runs (id, serial, revision) VALUES (%s, %s, %s)", (run_id, body.serial, body.revision))
    control(RunControl(kind="start", bench=body.bench, run_id=run_id, serial=body.serial, revision=body.revision, photo_checks=body.photo_checks))
    return {"run_id": run_id}


@app.post("/api/runs/stop")
async def stop_run(bench: str = settings.bench_id) -> dict:
    control(RunControl(kind="stop", bench=bench))
    hub.last_state = None
    await hub.announce("run.ended", {})
    return {"ok": True}


@app.get("/api/procedure")
def get_procedure() -> dict:
    return json.loads(PROCEDURE.read_text())


@app.get("/api/zones")
def get_zones() -> list:
    return json.loads(ZONES.read_text())


@app.put("/api/zones")
def put_zones(zones: list[Zone], bench: str = settings.bench_id) -> dict:
    ZONES.write_text(json.dumps([z.model_dump() for z in zones], indent=2))
    control(RunControl(kind="zones", bench=bench, zones=zones))
    return {"ok": True}


@app.get("/api/manual")
def get_manual() -> dict:
    return {"text": MANUAL.read_text()}


@app.put("/api/manual")
def put_manual(body: ManualEdit) -> dict:
    """Re-ingests the manual and proposes a procedure. Nothing changes until an engineer approves."""
    MANUAL.write_text(body.text)
    doc_id, procedure_id, report = ingest_text(split_markdown(body.text), Path(MANUAL).stem)
    return {"doc_id": doc_id, "procedure_id": procedure_id, **report}


@app.post("/api/procedures/{procedure_id}/approve")
def approve_procedure(procedure_id: int, body: Approval, bench: str = settings.bench_id) -> Procedure:
    if not body.engineer.strip():
        raise HTTPException(400, "An engineer's name is required.")
    procedure = approve(procedure_id, body.engineer)
    PROCEDURE.write_text(json.dumps(procedure.model_dump(), indent=2))
    control(RunControl(kind="procedure", bench=bench, procedure=procedure))
    return procedure


@app.post("/api/ask")
def ask_manual(body: Question) -> dict:
    return ask(body.question)


@app.get("/api/log")
def log() -> dict:
    with connect() as db:
        verdicts = db.execute(
            """SELECT v.created_at, r.serial, v.revision, v.step_id, v.reason, v.status, v.explanation,
                      v.citations, v.model, v.latency_ms, v.source
               FROM verdicts v JOIN runs r ON r.id = v.run_id ORDER BY v.created_at DESC LIMIT 40"""
        ).fetchall()
        incidents = db.execute(
            """SELECT i.created_at, r.serial, i.step_id, i.rework, i.report
               FROM incidents i JOIN runs r ON r.id = i.run_id ORDER BY i.created_at DESC LIMIT 20"""
        ).fetchall()
    return {
        "verdicts": [
            dict(zip(("at", "serial", "revision", "step", "reason", "status", "explanation", "citations", "model", "latency_ms", "source"), row))
            for row in verdicts
        ],
        "incidents": [dict(zip(("at", "serial", "step", "rework", "report"), row)) for row in incidents],
    }


@app.get("/api/results")
def results() -> dict:
    """The numbers for the pitch: live verdicts only, so replay can never inflate them."""
    with connect() as db:
        rows = db.execute("SELECT status, reason, latency_ms, model FROM verdicts WHERE source = 'live' AND model <> 'local-rules'").fetchall()
        runs = db.execute("SELECT count(*) FROM runs").fetchone()[0]
    latencies = [row[2] for row in rows if row[2]]
    counts: dict[str, int] = {}
    for status_name, *_ in rows:
        counts[status_name] = counts.get(status_name, 0) + 1
    return {
        "runs": runs,
        "verdicts": len(rows),
        "by_status": counts,
        "median_verdict_ms": int(statistics.median(latencies)) if latencies else None,
    }


# Last, so every route above wins. dev.sh builds this folder before starting the gateway.
if WEB_BUILD.exists():
    app.mount("/", StaticFiles(directory=WEB_BUILD, html=True))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.bind_host, port=settings.gateway_port, log_level="warning", timeout_graceful_shutdown=1)
