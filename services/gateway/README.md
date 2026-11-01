# gateway

The screens' only door into the system.

| | |
| --- | --- |
| Run | `uv run python -m services.gateway.main` |
| Port | 8100 |
| Reads | `alerts.reflex`, `verdicts`, `incidents`, `run.state`, `bench.events`, `hand.tracks`, `frames.raw` |
| Writes | `run.control`, YugabyteDB |

- `main.py` holds the HTTP routes.
- `live.py` reads Kafka on one thread and copies each message to every browser.
- `ask.py` answers supervisor questions from the manual, with a checked citation.

`WS /ws/live` carries live messages. `GET /frame.jpg` serves the newest frame, made small. Browsers fetch one at a time, so a slow connection lowers the frame rate and never adds delay. `POST /api/manual/upload` takes a PDF, Markdown or text manual. Uploads and edits are only proposed, and `POST /api/procedures/{id}/approve` needs an engineer's name before anything changes.

`/api/results` counts live Gemini verdicts only, so replay and local rules can never inflate the pitch numbers.
