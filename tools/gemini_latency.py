"""Measures real verdict speed with images, and prints which model to use.

  python -m tools.gemini_latency
"""

import statistics
import time

import cv2
import numpy as np

from common.config import ROOT, settings
from contracts.models import Procedure
from services.knowledge.parse import hierarchy, read_pages
from services.reasoner.judge import SCHEMA, SYSTEM

MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite"]
CALLS = 5


def bench_photo() -> bytes:
    image = np.full((360, 640, 3), 70, np.uint8)
    cv2.rectangle(image, (200, 120), (440, 320), (160, 150, 120), -1)
    return cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])[1].tobytes()


def main() -> None:
    from google import genai
    from google.genai import types

    if not settings.gemini_api_key:
        raise SystemExit("Set GEMINI_API_KEY in .env first.")

    client = genai.Client(api_key=settings.gemini_api_key)
    manual = "\n".join(leaf.body for s in hierarchy(read_pages(ROOT / "manual" / "vdn1.md"))[3:5] for leaf in s.leaves)
    photo = bench_photo()
    results: dict[str, float] = {}

    for model in MODELS:
        times: list[float] = []
        for call in range(CALLS):
            prompt = f"Unit revision: A. Call {call}. Is the display on the breadboard?\nManual excerpts:\n{manual}"
            parts = [types.Part.from_text(text=prompt)] + [types.Part.from_bytes(data=photo, mime_type="image/jpeg") for _ in range(4)]
            started = time.perf_counter()
            try:
                client.models.generate_content(
                    model=model,
                    contents=parts,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM,
                        temperature=0,
                        response_mime_type="application/json",
                        response_json_schema=SCHEMA,
                        thinking_config=types.ThinkingConfig(thinking_level="low"),
                    ),
                )
            except Exception as error:
                print(f"{model}: {str(error)[:160]}")
                break
            times.append(time.perf_counter() - started)
        if times:
            results[model] = statistics.median(times)
            print(f"{model}: median {results[model]:.2f}s, max {max(times):.2f}s over {len(times)} calls")

    if results:
        print(f"Use GEMINI_MODEL={min(results, key=results.get)}")


if __name__ == "__main__":
    main()
