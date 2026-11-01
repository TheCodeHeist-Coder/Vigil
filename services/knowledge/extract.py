"""Reads the procedure out of the manual with Gemini. An engineer approves it before use."""

import json

from common.config import ROOT, settings
from contracts.models import Procedure

SYSTEM = """You turn an assembly manual into a machine-readable procedure.
Use only the manual text. Take each step from the numbered steps of the assembly chapter, in order.
section is the step's own number, such as 4.2, never its chapter number.
bin is the single bin letter named in the step or the parts list.
part is a one or two word name for what is in that bin, such as "OLED" or "Power wires".
requires holds the step that must come first. The first step has none.
check says what a photo of the finished step must show.
correction is a short spoken order naming this step's own action, said when an operator skipped this step.
For a display step that is "Stop. Seat the display first." For a wiring step it is "Stop. Connect the power wires first."
Never reuse the wording of another step.
Ignore notes about skipping steps: they are decided at run time."""

SCHEMA = {
    "type": "object",
    "properties": {
        "revision": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "section": {"type": "string"},
                    "title": {"type": "string"},
                    "bin": {"type": "string"},
                    "part": {"type": "string"},
                    "requires": {"type": "array", "items": {"type": "string"}},
                    "check": {"type": "string"},
                    "correction": {"type": "string"},
                },
                "required": ["id", "section", "title", "bin", "part", "requires", "check", "correction"],
            },
        },
    },
    "required": ["revision", "steps"],
}


def with_step_ids(body: dict) -> Procedure:
    """Numbers steps S1, S2 and so on in code, because the rest of the system relies on these ids."""
    new_ids = {step["id"]: f"S{i}" for i, step in enumerate(body["steps"], start=1)}
    for step in body["steps"]:
        step["id"] = new_ids[step["id"]]
        step["requires"] = [new_ids[r] for r in step["requires"] if r in new_ids]
    return Procedure(**body)


def baseline() -> Procedure:
    return Procedure(**json.loads((ROOT / "manual" / "procedure.json").read_text()))


def extract(manual: str) -> Procedure:
    if not settings.gemini_api_key:
        return baseline()

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=manual,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM,
            temperature=0,
            response_mime_type="application/json",
            response_json_schema=SCHEMA,
        ),
    )
    return with_step_ids(json.loads(response.text))
