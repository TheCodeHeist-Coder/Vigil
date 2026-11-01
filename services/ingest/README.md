# ingest

Receives camera video over WebRTC and writes JPEG frames to `frames.raw`.

| | |
| --- | --- |
| Run | `uv run python -m services.ingest.main` |
| Port | 8101 |
| Reads | WebRTC video track |
| Writes | `frames.raw` |

The browser posts its SDP offer to `POST /webrtc/offer`. Only the newest frame is kept, so a slow encode drops frames and never adds lag.

Set `WEBRTC_PORTS=40000-40099` to keep video on a fixed UDP range, so a server firewall stays narrow. To scale, run one instance per bench.
