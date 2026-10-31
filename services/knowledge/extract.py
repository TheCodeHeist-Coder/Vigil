"""Reads the procedure out of the manual with Gemini. An engineer approves it before use."""

import json

from common.config import ROOT, settings
from contracts.models import Procedure

SYSTEM = """You turn an assembly manual into a machine-readable procedure.
Use only the manual text. Take each step from the numbered steps of the assembly chapter, in order.
bin is the single bin letter named in the step or the parts list.
requires holds the step that must come first. The first step has none.
check says what a photo of the finished step must show.
correction is a short spoken order for an operator who skipped this step, like "Stop. Install the gasket first."
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
                    "requires": {"type": "array", "items": {"type": "string"}},
                    "check": {"type": "string"},
                    "correction": {"type": "string"},
                },
                "required": ["id", "section", "title", "bin", "requires", "check", "correction"],
            },
        },
    },
    "required": ["revision", "steps"],
}


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
    return Procedure(**json.loads(response.text))
