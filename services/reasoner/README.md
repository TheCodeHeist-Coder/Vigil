# reasoner

Decides each flagged event with the manual and Gemini, then writes the incident record.

| | |
| --- | --- |
| Run | `uv run python -m services.reasoner.main` |
| Reads | `flags`, `run.control`, `frames.raw` by offset |
| Writes | `verdicts`, `incidents`, YugabyteDB |

- `judge.py` asks Gemini, then checks every quote against the manual text. A quote that is not there turns the verdict into `uncertain`, which keeps the hold on.
- `agent.py` is the incident agent. It uses function calling for run history, manual search and past incidents. Rework steps are computed in code from the procedure, not by the model.
- `context.py` is agent memory. See below.
- `meko.py` is the Meko MCP client.

## Agent context

With `MEKO_API_KEY` set, Meko holds conversations, memory and decision traces in the `vigil-bench` datapack, shared by the `vigil-verdict` and `vigil-incident` agents. Meko calls run on their own thread and verdicts read notes fetched ahead of time, so a slow connection can never delay a verdict.

With no key, memory stays in the YugabyteDB `agent_memory` table. YugabyteDB also keeps a copy when Meko is on, so an outage loses nothing.

## With no Gemini

With no key, or when a call fails, `local-rules` reads the manual's notes for sequence errors and returns `uncertain` for photo checks. The model name appears on screen, so this is never mistaken for Gemini.

`REPLAY=1` serves verdicts saved from earlier real runs, marked `replay`. It is a stage fallback only.
