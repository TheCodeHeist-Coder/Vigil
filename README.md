# Vigil

Vigil watches an assembly bench and stops a wrong step as it happens. A local rule raises the alert straight away, then Gemini confirms or clears it with a citation from the manual.

Built for hackCBS 9.0. The demo uses a mock product and a 10 page manual, not a real factory.

## How it works

```text
Camera --WebRTC--> ingest --> Kafka frames.raw --> edge (YOLOv8-Pose + MediaPipe)
                                                     |
                                                     v  hand.tracks
                                                  sequencer (zones + step rules)
                                                     |
                           +-------------------------+----------------+
                           v                                          v
                     alerts.reflex                                  flags
                           |                                          |
                           v                                          v
Screens and phone <---- gateway <-------- verdicts, incidents ---- reasoner <--> Gemini
                                                                      |
                                                       YugabyteDB (manual vectors, runs)
                                                       Meko (agent memory and traces)
```

The sequencer raises the alert with no network call, so a slow or failed cloud call can never delay it. Gemini then checks the event against the manual. Every quote is checked against the manual text, and a verdict that fails this check stays on hold for a supervisor.

## Services

Each service has its own folder and README, and talks to the others only through Kafka. Any one of them can be read, replaced or scaled alone.

| Service | Job |
| --- | --- |
| [`services/ingest`](services/ingest) | Takes WebRTC camera video and writes JPEG frames to Kafka |
| [`services/edge`](services/edge) | Finds hands with YOLOv8-Pose and MediaPipe |
| [`services/sequencer`](services/sequencer) | Turns hand positions into events and checks them against the procedure |
| [`services/reasoner`](services/reasoner) | Checks flagged events with Gemini and runs the incident agent |
| [`services/knowledge`](services/knowledge) | Loads the manual into YugabyteDB as hierarchical embeddings |
| [`services/gateway`](services/gateway) | Serves the screens over WebSockets and HTTP |
| [`web`](web) | Bench, Camera, Phone and Supervisor screens |

`contracts/` holds the shared message types and topic names. `common/` holds shared helpers. `tools/` holds run-once scripts.

## Run it

You need Docker, [uv](https://docs.astral.sh/uv/) and pnpm.

```bash
uv sync
(cd web && pnpm install)
cp .env.example .env                       # add your keys
docker compose --profile db up -d          # Kafka and YugabyteDB
docker exec -i vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -c "CREATE DATABASE vigil;"'
docker exec -i vigil-yugabyte sh -c 'bin/ysqlsh -h $(hostname) -U yugabyte -d vigil' < db/schema.sql
uv run python -m tools.fetch_models        # about 15 MB
uv run python -m tools.topics
uv run python -m services.knowledge.main manual/vg100.md
./dev.sh                                   # stop with ./dev.sh stop
```

Open <http://localhost:5173> on this laptop. A phone uses `https://<laptop-ip>:5174`, and needs its certificate warning accepted once. Then:

1. On **Camera**, start the camera on a device that can see the bench.
2. On **Bench**, choose **Mark zones** and drag a box around each bin.
3. On a second Android phone, open **Phone** and turn on alerts.
4. On **Bench**, enter the serial, choose the revision, and press **Start assembly**.

To test with only a laptop camera, sit back so your head, shoulders and arms are in view, mark the zones as spots your hand can reach, and tick **Hand test**. That skips photo checks, which need a camera that can see the unit.

## Deploy to a server

`deploy/setup.sh` installs everything on an Ubuntu or Debian server, runs each service under systemd so it restarts by itself, and adds real HTTPS with Caddy. It stops without changing anything if another web server already uses port 80 or 443. See the top of the script for the steps.

Set `VIGIL_ACCESS_KEY` first. People then open the link once with `?key=...`, and it sets a cookie on that device.

## Keys

| Key | Used for | With no key |
| --- | --- | --- |
| `GEMINI_API_KEY` | Verdicts, photo checks, embeddings, the incident agent | Sequence errors use local rules from the manual. Photo checks return `uncertain`. Manual search matches words, not meaning. |
| `MEKO_API_KEY` | Agent memory, conversations and decision traces | Memory stays in YugabyteDB |

The model in use always shows on screen, so `local-rules` is never mistaken for Gemini.

After adding `GEMINI_API_KEY`, run these once:

```bash
uv run python -m tools.gemini_latency               # prints which model to use
uv run python -m tools.render_voice                 # optional voice clips
uv run python -m services.knowledge.main manual/vg100.md   # real embeddings
uv run python -m tools.reset_runs                   # clears test data before real runs
```

## Test without a bench

```bash
uv run python -m tools.simulate_run clean           # also: e1, e2
uv run python -m tools.simulate_run e3 --revision B
uv run python -m tools.replay_clip clips/run.mp4    # feed a recorded clip through Kafka
uv run pytest -m "not integration"                  # unit tests
uv run pytest                                       # needs Kafka and YugabyteDB
```

## Stage fallbacks

If the camera link fails, `replay_clip` feeds a recorded run through Kafka. If Gemini or the internet fails, set `REPLAY=1` to serve verdicts saved from earlier real runs. These show a REPLAY badge and never count towards `/api/results`.

## Limits

- The unit and manual are mock. Results come from one bench, and no field accuracy exists.
- YOLOv8-Pose needs to see the operator's body, so the camera works best high and in front, at about 45 degrees.
- Vibration needs Chrome on Android.
- Ultralytics is AGPL-3.0, so a commercial product would need to review that license.
