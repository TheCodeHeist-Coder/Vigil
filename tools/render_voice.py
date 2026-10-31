"""Pre-renders each step's spoken correction, so alerts play with no network delay.

Writes web/public/voice/*.wav and sets `clip` in manual/procedure.json. With no clip,
the screens fall back to the browser's own speech.
"""

import json
import wave

from common.config import ROOT, settings

MODEL = "gemini-3.8-flash-tts"
VOICE_DIR = ROOT / "web" / "public" / "voice"
PROCEDURE = ROOT / "manual" / "procedure.json"
SAMPLE_RATE = 24000


def main() -> None:
    from google import genai
    from google.genai import types

    if not settings.gemini_api_key:
        raise SystemExit("Set GEMINI_API_KEY in .env first.")

    client = genai.Client(api_key=settings.gemini_api_key)
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    procedure = json.loads(PROCEDURE.read_text())
    for step in procedure["steps"]:
        name = f"{step['id']}.wav"
        if (VOICE_DIR / name).exists():
            step["clip"] = name
            continue
        try:
            response = client.models.generate_content(
                model=MODEL,
                contents=f"Say firmly and clearly: {step['correction']}",
                config=types.GenerateContentConfig(response_modalities=["AUDIO"]),
            )
            pcm = response.candidates[0].content.parts[0].inline_data.data
        except Exception as error:  # a step with no clip uses speech, so keep going
            print(f"skipped {name}: {str(error)[:120]}")
            continue
        with wave.open(str(VOICE_DIR / name), "wb") as audio:
            audio.setnchannels(1)
            audio.setsampwidth(2)
            audio.setframerate(SAMPLE_RATE)
            audio.writeframes(pcm)
        step["clip"] = name
        print(f"rendered {name}")
    PROCEDURE.write_text(json.dumps(procedure, indent=2))


if __name__ == "__main__":
    main()
