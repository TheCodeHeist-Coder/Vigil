# Vigil

Vigil watches an assembly bench and stops a wrong step as it happens. A local rule raises the alert straight away, then Gemini confirms or clears it with a citation from the manual.

Built for hackCBS 9.0. The demo uses a mock product and a 10 to 12 page manual, not a real factory.

## Services

Each service lives in its own folder under `services/` and talks to the others only through Kafka topics, so any one of them can be read, replaced or scaled alone.

| Service | Job |
| --- | --- |
| `services/ingest` | Takes WebRTC camera video and writes JPEG frames to Kafka |
| `services/edge` | Finds hands with YOLOv8-Pose and MediaPipe |
| `services/sequencer` | Turns hand positions into events and checks them against the procedure |
| `services/reasoner` | Checks flagged events with Gemini and the manual, and runs the incident agent |
| `services/knowledge` | Loads the manual into YugabyteDB as hierarchical embeddings |
| `services/gateway` | Serves the screens over WebSockets and HTTP |

`contracts/` holds the shared message types and topic names. `common/` holds shared helpers. `web/` holds the screens.

See `PLAN.md` for the build plan.
