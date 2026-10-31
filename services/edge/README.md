# edge

Finds hands in the newest frame and publishes them to `hand.tracks`.

| | |
| --- | --- |
| Run | `uv run python -m services.edge.main` |
| Setup | `uv run python -m tools.fetch_models` |
| Reads | `frames.raw` |
| Writes | `hand.tracks` |

YOLOv8-Pose finds the person and wrists. MediaPipe then finds fingers in a crop around each hand, and searches the whole frame if YOLO sees nobody.

Stale frames are skipped, so a slow CPU lowers the frame rate and never adds lag. Set `YOLO_IMGSZ` to 640 or 480. To scale, run one instance per bench, or move it to a GPU machine.
