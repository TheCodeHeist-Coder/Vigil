"""The messages every service agrees on. Tell the team before changing these."""

from typing import Literal

from pydantic import BaseModel, Field

Point = tuple[float, float]  # normalised 0..1


class Step(BaseModel):
    id: str  # "S3"
    section: str  # "4.3"
    title: str
    bin: str  # zone the part comes from
    part: str = ""  # short name of what is in that bin, shown on the video
    requires: list[str] = Field(default_factory=list)  # steps that must be done first
    check: str  # what a hands-clear frame must show
    correction: str  # "Stop. Connect the power wires first."
    clip: str = ""  # pre-rendered audio file, empty means use speech


class Procedure(BaseModel):
    id: int = 0
    doc_id: int = 0
    revision: str = "A"
    steps: list[Step]

    def step(self, step_id: str) -> Step | None:
        return next((s for s in self.steps if s.id == step_id), None)

    def step_for_bin(self, zone: str) -> Step | None:
        return next((s for s in self.steps if s.bin == zone), None)


class Zone(BaseModel):
    id: str
    label: str
    kind: Literal["bin", "tray"]
    polygon: list[Point]


class HandTrack(BaseModel):
    bench: str
    frame_offset: int
    hands: list[Point] = Field(default_factory=list)
    pinch: Point | None = None
    skeleton: list[Point] = Field(default_factory=list)  # wrists and elbows, for the overlay
    source: Literal["yolo", "mediapipe", "yolo+mediapipe", "none", "simulated"] = "none"
    times: dict[str, float] = Field(default_factory=dict)  # t_capture, t_ingest, t_edge


class BenchEvent(BaseModel):
    id: str
    bench: str
    run_id: str
    kind: Literal["pick", "place", "hands_clear"]
    zone: str
    frame_offset: int
    times: dict[str, float] = Field(default_factory=dict)


class ReflexAlert(BaseModel):
    id: str
    bench: str
    run_id: str
    flag_id: str
    step_id: str
    text: str
    clip: str = ""
    times: dict[str, float] = Field(default_factory=dict)


class Flag(BaseModel):
    id: str
    bench: str
    run_id: str
    event: BenchEvent
    reason: Literal["out_of_sequence", "step_check", "supervisor_release"]
    expected_step: str
    actual_step: str | None = None
    unit_revision: Literal["A", "B"] = "A"
    frame_offsets: list[int] = Field(default_factory=list)  # at most 4
    completed_steps: list[str] = Field(default_factory=list)


class Citation(BaseModel):
    section: str
    page: int
    quote: str


class Verdict(BaseModel):
    flag_id: str
    bench: str
    run_id: str
    step_id: str
    reason: str
    # confirmed means a real problem. cleared means carry on. uncertain holds for a supervisor.
    status: Literal["confirmed", "cleared", "uncertain"]
    explanation: str
    citations: list[Citation] = Field(default_factory=list)
    spoken: str | None = None
    model: str = ""
    latency_ms: int = 0
    source: Literal["live", "replay"] = "live"
    times: dict[str, float] = Field(default_factory=dict)


class Incident(BaseModel):
    id: str
    bench: str
    run_id: str
    step_id: str
    rework: list[str] = Field(default_factory=list)
    report: str
    occurrences: int = 1
    memory_backend: Literal["meko", "yugabyte"] = "yugabyte"


class RunControl(BaseModel):
    kind: Literal["start", "stop", "zones", "procedure", "recheck", "release"]
    bench: str
    run_id: str | None = None
    serial: str | None = None
    revision: Literal["A", "B"] = "A"
    photo_checks: bool = True  # off for a hand test, when the camera cannot see the unit
    zones: list[Zone] | None = None
    procedure: Procedure | None = None


class RunState(BaseModel):
    bench: str
    run_id: str
    serial: str = ""
    revision: Literal["A", "B"] = "A"
    done: list[str] = Field(default_factory=list)
    waived: list[str] = Field(default_factory=list)
    active: str | None = None
    held: bool = False
    finished: bool = False
