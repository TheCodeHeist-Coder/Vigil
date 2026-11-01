# knowledge

Loads a manual into YugabyteDB as hierarchical embeddings, and proposes a procedure from it.

| | |
| --- | --- |
| Run | `uv run python -m services.knowledge.main manual/vdn1.md` |
| Reads | A Markdown or PDF manual |
| Writes | `documents`, `chunks`, `procedures` |

- `parse.py` splits the manual into sections and leaves by numbered headings.
- `embed.py` embeds text and caches results in `data/embeddings/`.
- `store.py` writes both levels with a `ybhnsw` vector index.
- `retrieve.py` finds the top sections, then the best leaves inside them, and fetches step text by exact tag.
- `extract.py` reads the procedure with Gemini. An engineer approves it before it is used.

With no `GEMINI_API_KEY`, embeddings fall back to word hashing, which matches words and not meaning, and the procedure comes from `manual/procedure.json`.
