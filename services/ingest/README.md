# ingest

Receives camera video over WebRTC and writes JPEG frames to `frames.raw`.

| | |
| --- | --- |
| Run | `uv run python -m services.ingest.main` |
| Port | 8101 |
| Reads | WebRTC video track |
| Writes | `frames.raw` |

The browser posts its SDP offer to `POST /webrtc/offer`. Only the newest frame is kept, so a slow encode drops frames and never adds lag.

No ICE servers are configured, because the camera and this service share a LAN. To scale, run one instance per bench.
