"""Text embeddings. Results are cached on disk, so a re-ingest costs no API calls."""

import hashlib
import json
import math
import re

from common.config import ROOT, settings

DIMENSIONS = 768
BATCH = 50
CACHE = ROOT / "data" / "embeddings"


def backend() -> str:
    return settings.gemini_embed_model if settings.gemini_api_key else "local-hash"


def local_embedding(text: str) -> list[float]:
    """Word hashing, used only with no API key. It matches words, not meaning."""
    vector = [0.0] * DIMENSIONS
    for word in re.findall(r"[a-z0-9.]+", text.lower()):
        digest = hashlib.sha256(word.encode()).digest()
        index = int.from_bytes(digest[:4], "big") % DIMENSIONS
        vector[index] += 1.0 if digest[4] % 2 else -1.0
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _gemini(texts: list[str]) -> list[list[float]]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    vectors: list[list[float]] = []
    for start in range(0, len(texts), BATCH):
        result = client.models.embed_content(
            model=settings.gemini_embed_model,
            contents=texts[start : start + BATCH],
            config=types.EmbedContentConfig(output_dimensionality=DIMENSIONS),
        )
        vectors += [list(e.values) for e in result.embeddings]
    return vectors


def embed(texts: list[str]) -> list[list[float]]:
    name = backend()
    CACHE.mkdir(parents=True, exist_ok=True)
    keys = [hashlib.sha256(f"{name}\n{t}".encode()).hexdigest() for t in texts]
    results: dict[str, list[float]] = {}
    missing: list[tuple[str, str]] = []
    for key, text in zip(keys, texts):
        path = CACHE / f"{key}.json"
        if path.exists():
            results[key] = json.loads(path.read_text())
        else:
            missing.append((key, text))

    if missing:
        fresh = _gemini([t for _, t in missing]) if settings.gemini_api_key else [local_embedding(t) for _, t in missing]
        for (key, _), values in zip(missing, fresh):
            results[key] = values
            (CACHE / f"{key}.json").write_text(json.dumps(values))
    return [results[key] for key in keys]
