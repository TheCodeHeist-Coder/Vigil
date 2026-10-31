# sequencer

Turns hand positions into bench events, and checks each one against the procedure.

| | |
| --- | --- |
| Run | `uv run python -m services.sequencer.main` |
| Reads | `hand.tracks`, `run.control`, `verdicts` |
| Writes | `bench.events`, `alerts.reflex`, `flags`, `run.state` |

- `zones.py` decides when a hand has picked, placed or cleared the tray.
- `logic.py` holds the step rules as pure functions, so they test without Kafka.
- `main.py` connects them to Kafka and keeps one state per bench.

The reflex alert comes from here and never waits on a network call. Gemini's verdict then clears the hold or confirms it.

Change `DWELL_SECONDS` and `CLEAR_SECONDS` in `zones.py` to tune detection. One instance handles many benches, because all state is keyed by bench.
