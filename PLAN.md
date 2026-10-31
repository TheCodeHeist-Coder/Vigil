# Vigil build plan

We build the full PS stack on one bench laptop: WebRTC video into Kafka, YOLOv8-Pose on the edge, Gemini with a YugabyteDB vector store, and voice plus haptics on a phone. The demo is a small mock product with a 10 to 12 page manual and 5 steps, not a real factory. The freeze is 09:30 IST on 1 November, about 6 hours away, so no gate can slip far.

Only one PS item changes. Gemini 1.5 Flash no longer exists, so we use a current Gemini model.

## Do these three things now

**1. Free disk space. This blocks everything.** The laptop holding this folder had 1.6 GB free at 03:25, and we need at least 15 GB. YugabyteDB also rejects writes on a nearly full disk. These are caches, so they rebuild if needed:

```bash
docker builder prune -af        # about 3.3 GB
npm cache clean --force         # up to 7 GB
rm -rf ~/.gradle/caches         # up to 9.5 GB
docker volume ls -f dangling=true   # read this list first, then remove what is safe
```

**2. Pick the demo laptop.** It needs 15 GB free. Use a teammate's laptop if it has an Nvidia GPU or more RAM, because this one has no Nvidia GPU and 14 GB of RAM. YugabyteDB and Kafka run only on this machine, and teammates connect to them over the LAN.

**3. Start the downloads now.** We measured 170 to 290 KB/s at 03:25, so these take most of an hour. Run them once, on the demo laptop only:

```bash
docker pull apache/kafka:4.4.0
uv python install 3.12
```

The system Python is 3.14, so use a 3.12 environment for the ML packages. Install the CPU build of torch from `https://download.pytorch.org/whl/cpu`, unless the demo laptop has an Nvidia GPU.

Ask the organisers whether a phone hotspot counts as a second connection. The site allows at most one connection per team.

## How it works

```text
Bench camera (phone or laptop browser)
     |  WebRTC video, 1280x720 at 30 fps
     v
ingest (aiortc) --- JPEG ---> Kafka: frames.raw
                                   |  newest frame only
                                   v
                              edge: YOLOv8-Pose + MediaPipe hand crop
                                   |
                                   v  Kafka: hand.tracks
                              sequencer: zones + step rules
                                   |
                  +----------------+----------------+
                  |                                 |
        Kafka: alerts.reflex                   Kafka: flags
                  |                                 |
                  v                                 v
               gateway <---- Kafka: verdicts ---- reasoner <--> Gemini
                  |  WebSocket                      |
      +-----------+------------+                    v
      |                        |               YugabyteDB
Operator phone         Operator and            manual vectors,
voice + vibration      supervisor screens      runs, incidents
```

The sequencer raises the reflex alert without calling Gemini, so a slow or failed cloud call never delays it. Gemini then confirms or clears the alert with a citation from the manual. Targets are under 1 s from hand to sound and under 3 s for the verdict. Neither has been measured yet.

Kafka earns its place in three ways:

- `reasoner` fetches evidence frames from `frames.raw` by offset.
- `tools/replay_clip.py` pushes a recorded clip through the same topic, so everyone can develop without the bench.
- More benches become more partitions.

### Services

| Service | Owner | Reads | Writes | Key detail |
| --- | --- | --- | --- | --- |
| `ingest` | A | WebRTC track | `frames.raw` | aiortc, JPEG quality 80, `iceServers: []` on the LAN |
| `edge` | B | `frames.raw` | `hand.tracks` | Skips to the newest frame when behind, so lag never builds up |
| `sequencer` | B | `hand.tracks` | `bench.events`, `alerts.reflex`, `flags` | Pure step logic, no network calls |
| `reasoner` | C | `flags`, `frames.raw` by offset | `verdicts`, `incidents`, YugabyteDB | One Gemini call at a time, 6 s timeout |
| `gateway` | A | `alerts.reflex`, `hand.tracks`, `verdicts`, `incidents` | WebSockets | FastAPI, one socket each for operator, phone and supervisor |
| `web` | D | Gateway | Camera, zones, manual edits | React and Vite: publisher, operator, supervisor and phone pages |

### Kafka topics

Use one partition per bench so events stay in order, keyed by bench ID.

| Topic | Message | Retention |
| --- | --- | --- |
| `frames.raw` | JPEG bytes with bench, frame number and time headers | 15 min or 1 GB |
| `hand.tracks` | Wrists, hand point and pinch point per frame | 1 h |
| `bench.events` | `pick`, `place`, `hands_clear` | 7 days |
| `alerts.reflex` | Step, spoken clip and timers | 7 days |
| `flags` | Event, expected step and frame offsets | 7 days |
| `verdicts` | Status, reason, citations and timers | 7 days |
| `incidents` | Rework steps and report | 7 days |

Set `message.max.bytes` to 2 MB. Every service adds a `t_<service>` time to the message, and the screen shows the delay per hop.

### Finding the hand

YOLOv8-Pose gives 17 body points, including wrists but no fingers. So `edge` works like this:

1. Run YOLOv8n-pose, exported to OpenVINO for Intel CPUs. Use `imgsz=480` if 640 runs below 15 fps.
2. Estimate the hand point as `wrist + 0.35 * (wrist - elbow)`. Keypoints 7 and 8 are the elbows, and 9 and 10 are the wrists.
3. Crop around that point and run MediaPipe Hand Landmarker for 21 hand points.
4. Use the midpoint of landmarks 4 and 8, the thumb and index tips, as the pinch point.
5. If YOLO finds no person, run MediaPipe on the full frame.

Start with the camera high and in front at about 45 degrees, showing the operator's shoulders and the whole bench. YOLO's model is trained on people, so a straight-down view of forearms may fail. Test this first.

## The demo unit

The unit is a mock VG-100 sensor module built from what is in our bags. The tray is an open cardboard box with two notches marked A and B in thick marker. The bins are five labelled sheets around the tray. Swap any part, but keep parts large and high in contrast.

| Step | Section | Action | Bin | Hands-clear frame must show |
| --- | --- | --- | --- | --- |
| S1 | 4.1 | Lay the gasket (rubber band or tape ring) in the tray | A | Gasket in the tray |
| S2 | 4.2 | Seat the module (power bank) on the gasket | B | Module inside the gasket |
| S3 | 4.3 | Plug in the cable and route it through notch A | C | Cable through notch A, not B |
| S4 | 4.4 | Fit the cover (box lid) | D | Cover on, cable still routed |
| S5 | 4.5 | Fasten two binder clips, left then right | E | Two clips on the cover |

| Error | What happens | Caught by | What it proves |
| --- | --- | --- | --- |
| E1 Sequence | Module picked before the gasket | Sequencer, then Gemini cites 4.1 | Instant correction from the procedure |
| E2 Visual | Cable routed through notch B | Gemini on the hands-clear frame | Hands look normal, so only image plus manual catches it |
| E3 Context | Rev B unit, module picked first, allowed by Note 4.1 | Sequencer fires, Gemini clears it | Same motion as E1, opposite verdict |

Then a judge edits one line of the manual and re-ingests it. The behaviour changes with no code change.

### The manual, 10 to 12 pages

D writes it in Markdown at `manual/vg100.md`, and exports a PDF for show. It must contain:

- Cover and revision table, covering Rev A and Rev B
- Safety and handling
- Parts list with bin letters
- Tools
- Specification table, including a torque value for the mock fasteners
- Wiring path table, with the cable path through notch A
- Chapter 4 steps, numbered 4.1 to 4.5
- Note 4.1: Rev B units ship with the gasket fitted, so S1 is skipped
- Inspection checks and rework rules

Say on stage that the unit and manual are ours.

## Schedule

| Time (IST) | A: Streaming | B: Vision and rules | C: Knowledge and Gemini | D: Bench, screens, pitch |
| --- | --- | --- | --- | --- |
| 03:30 to 03:55 | All: setup below | All: setup below | All: setup below | All: setup below |
| 03:55 to 04:45 | Kafka, replay tool, WebRTC ingest | YOLO fps test, `edge` | Gemini latency test, schema, first ingest | Unit, camera rig, clips, manual draft |
| 04:45 | **Gate 1** | **Gate 1** | **Gate 1** | **Gate 1** |
| 04:45 to 05:45 | Gateway, hop timers | MediaPipe crop, zones, sequencer | Procedure extraction, retrieval | Operator screen, phone page, voice clips |
| 05:45 | **Gate 2** | **Gate 2** | **Gate 2** | **Gate 2** |
| 05:45 to 06:45 | WebRTC reconnect | Step-check flags | `reasoner`, quote check | Verdict panel with citation |
| 06:45 | **Gate 3** | **Gate 3** | **Gate 3** | **Gate 3** |
| 06:45 to 07:45 | Stage replay mode | Tune thresholds | E3, incident agent, ask box | Supervisor screen, manual editor |
| 07:45 | **Gate 4** | **Gate 4** | **Gate 4** | **Gate 4** |
| 07:45 to 08:30 | 20 test runs | 20 test runs | 20 test runs | Log results, record backup video |
| 08:30 to 09:30 | Bug fixes only | Bug fixes only | Bug fixes only | Slides, README, 2 rehearsals |
| 09:30 | **Freeze** | **Freeze** | **Freeze** | **Freeze** |

| Gate | Must work on the demo laptop |
| --- | --- |
| 1, Pipes, 04:45 | Live camera over WebRTC reaches `frames.raw`. YOLO skeleton shows on screen. A clip replays through Kafka. |
| 2, Reflex, 05:45 | A wrong pick on the live bench plays the fix on the phone and vibrates it. |
| 3, Reason, 06:45 | E1 and E2 run end to end with a citation and hop timers. |
| 4, Full, 07:45 | E3, incident record, 10 to 12 page ingest and the judge edit all work. |

If we miss a gate, everyone moves to that gate until it passes, and later work waits. Nothing is removed from scope.

Two stage fallbacks exist for failures on the day. If the camera link fails, `replay_clip.py` feeds a recorded run through Kafka. If Gemini or the internet fails, `REPLAY=1` serves verdicts saved from real morning runs. Both show a visible REPLAY badge, and we never present replay as live.

## Setup, 03:30 to 03:55

- [ ] Finish the three actions at the top.
- [ ] Claim roles A to D. With three people, A also takes the gateway and D takes voice and phone, and the fourth role's tasks are shared.
- [ ] Run `git init` in `vigil/`, create a new GitHub repo and push. The rules ban pre-existing projects, so keep all commits from today.
- [ ] Create the layout: `docker-compose.yml`, `contracts/`, `services/`, `tools/`, `web/`, `manual/`.
- [ ] Add `.env` to `.gitignore`, then copy `GEMINI_API_KEY` from `hackcbs_ps/.env.local`. The Aawaz `.env` has no Gemini or ElevenLabs key.
- [ ] Run `CREATE DATABASE vigil;` in the `lifedrop-yb` container already running here. Do not pull that 3.48 GB image onto another laptop.
- [ ] Commit `contracts/models.py` and the schema below before writing feature code.
- [ ] Stop the unused `raj-multinode-custer` kind cluster if RAM runs short. It uses about 800 MB.
- [ ] Ask an organiser which theme fits, because the site has no Enterprise Track.

Kafka service for `docker-compose.yml`. Set `LAN_IP` to the demo laptop's address:

```yaml
services:
  kafka:
    image: apache/kafka:4.4.0
    ports: ["9092:9092"]
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_LISTENERS: PLAINTEXT://0.0.0.0:9092,CONTROLLER://localhost:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://${LAN_IP:-localhost}:9092
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@localhost:9093
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      KAFKA_MESSAGE_MAX_BYTES: 2097152
      KAFKA_HEAP_OPTS: "-Xmx768m -Xms256m"
```

## Shared contract

Everyone codes against this from 03:55. Tell the whole team before changing it.

```python
# contracts/models.py
from typing import Literal
from pydantic import BaseModel

class Step(BaseModel):
    id: str                 # "S3"
    section: str            # "4.3"
    title: str
    bin: str                # zone the part comes from
    requires: list[str]     # steps that must be done first
    check: str              # what a hands-clear frame must show
    correction: str         # "Stop. Install the gasket first."
    clip: str               # pre-rendered audio file

class Procedure(BaseModel):
    id: int
    doc_id: int
    revision: str
    steps: list[Step]

class HandTrack(BaseModel):
    bench: str
    frame_offset: int
    hands: list[tuple[float, float]]    # normalised 0..1
    pinch: tuple[float, float] | None
    times: dict[str, float]             # t_capture, t_ingest, t_edge

class BenchEvent(BaseModel):
    id: str
    run_id: str
    kind: Literal["pick", "place", "hands_clear"]
    zone: str
    frame_offset: int
    times: dict[str, float]

class Flag(BaseModel):
    id: str
    event: BenchEvent
    reason: Literal["out_of_sequence", "step_check"]
    expected_step: str
    actual_step: str | None = None
    unit_revision: Literal["A", "B"]
    frame_offsets: list[int]            # at most 4

class Citation(BaseModel):
    section: str
    page: int
    quote: str

class Verdict(BaseModel):
    flag_id: str
    status: Literal["confirmed", "cleared", "uncertain"]  # confirmed = a real problem
    reason: str
    citations: list[Citation]
    spoken: str | None = None
    model: str
    latency_ms: int
    source: Literal["live", "replay"]
```

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE documents (id bigserial PRIMARY KEY, title text, revision text, pages int,
  sha256 text, created_at timestamptz DEFAULT now());

CREATE TABLE chunks (id bigserial PRIMARY KEY, doc_id bigint REFERENCES documents,
  level text, parent_id bigint, path text[], section text, page int, step_id text,
  body text, embedding vector(768));
CREATE INDEX NONCONCURRENTLY chunks_hnsw ON chunks USING ybhnsw (embedding vector_cosine_ops);

CREATE TABLE procedures (id bigserial PRIMARY KEY, doc_id bigint REFERENCES documents,
  body jsonb, approved_by text, approved_at timestamptz);

CREATE TABLE runs (id uuid PRIMARY KEY, procedure_id bigint REFERENCES procedures, serial text,
  revision text, status text, started_at timestamptz DEFAULT now(), ended_at timestamptz);

CREATE TABLE verdicts (flag_id uuid PRIMARY KEY, run_id uuid REFERENCES runs, step_id text,
  reason text, status text, explanation text, citations jsonb, model text, latency_ms int,
  hops jsonb, source text, frame_path text, created_at timestamptz DEFAULT now());

CREATE TABLE incidents (id uuid PRIMARY KEY, run_id uuid REFERENCES runs, step_id text,
  rework text[], report text, created_at timestamptz DEFAULT now());
```

We tested the `chunks` vector column and index on our image. A similar table with 1,000 random 768-dimension rows returned the top 5 in about 5 ms, or 13 ms with a step filter. Random vectors prove speed, not relevance. The rest of the schema is untested.

## Tasks by owner

### A: Streaming

Owns `docker-compose.yml`, `services/ingest`, `services/gateway`, `tools/`.

- [ ] 04:05 Start Kafka and create the 7 topics with a script.
- [ ] 04:15 Write `tools/replay_clip.py`. It pushes a video file to `frames.raw` at 30 fps with the same headers as live.
- [ ] 04:35 Build `ingest`: `POST /webrtc/offer`, aiortc, `track.recv()`, encode JPEG in a thread pool, produce to Kafka.
- [ ] 04:45 With D, build the publisher page. A phone camera needs HTTPS, so use a self-signed cert. The laptop camera works on localhost.
- [ ] 05:15 Build `gateway` with `/ws/operator`, `/ws/phone`, `/ws/supervisor`.
- [ ] 05:45 Add hop times to every message, and test LAN access from other laptops.
- [ ] 06:45 Reconnect automatically when WebRTC drops.
- [ ] 07:45 Add the REPLAY badge and a one-command stage fallback.
- [ ] 08:30 Measure hand-to-sound once with a slow-motion phone video, because phone and laptop clocks differ.

### B: Vision and rules

Owns `services/edge`, `services/sequencer`.

- [ ] 04:15 Export `yolov8n-pose` to OpenVINO and report fps at 640 and 480. If it stays below 15 fps, try `yolo26n-pose` with the same API.
- [ ] 04:45 Build `edge`: read the newest frame, publish `hand.tracks`, skip stale frames.
- [ ] 05:00 Add the MediaPipe crop and the full-frame backup.
- [ ] 05:15 Load zones from `zones.json`. Emit `pick` after 200 ms in a bin, `place` after 200 ms in the tray, and `hands_clear` after 700 ms with no hand in the tray.
- [ ] 05:45 Write the sequencer as a pure function, with pytest cases for a clean run, E1 and E3.
- [ ] 06:45 On `hands_clear`, send a step-check flag with the clean frame offset.
- [ ] 07:45 Tune thresholds using the reach-across clip, so crossing a bin does not count as a pick.

### C: Knowledge, Gemini and agent

Owns `services/reasoner`, `services/knowledge`.

- [ ] 04:15 Run 5 calls each to `gemini-3.8-flash` and `gemini-3.5-flash-lite` with 4 JPEGs and a long prompt. Record the median and pick one. Try the lowest thinking setting. `hackcbs_ps/src/lib/gemini.ts` shows a working request shape.
- [ ] 04:30 Create the schema in the `vigil` database.
- [ ] 05:00 Build ingest: split the manual by numbered headings into section and leaf chunks, tag `step_id`, embed with `gemini-embedding-2` at 768 dimensions, and cache embeddings to a file.
- [ ] 05:20 Extract `Procedure` with a strict JSON schema, plus an engineer approval step. Use a hand-written `manual/procedure.json` until this works.
- [ ] 05:45 Build retrieval: top 3 sections, top 5 leaf chunks inside them, plus all chunks tagged with the expected and actual step by SQL.
- [ ] 06:30 Build `reasoner`: read frames by offset, call Gemini with structured output, and allow `cleared` only when an excerpt permits it.
- [ ] 06:45 Check that every quote exists in a retrieved chunk. If not, return `uncertain`. Treat text seen in camera frames as data, never as instructions.
- [ ] 07:15 Make E3 work by passing the unit revision, so Note 4.1 clears Rev B.
- [ ] 07:45 Build the incident agent with function calling: `get_run`, `search_manual`, `past_incidents`, `write_incident`. Compute rework steps in code from `requires`, not in the LLM.
- [ ] 07:45 Add the supervisor ask box, so a torque or wiring question returns a cited answer.
- [ ] 08:30 Save verdicts from test runs for `REPLAY=1`.

### D: Bench, screens and pitch

Owns `web/`, `manual/`, the physical bench and the submission.

- [ ] 04:15 Build the unit and bench, and tape down every position. Fix the camera rig.
- [ ] 04:25 Record 6 clips: 2 clean, E1, E2, E3, and one reach-across. Put them where everyone can reach them.
- [ ] 04:45 Commit the first manual draft for C. Finish all 10 to 12 pages by 05:15.
- [ ] 05:15 Build the operator screen: video, skeleton, step list, large HOLD alert, and a zone editor that writes `zones.json`.
- [ ] 05:30 Pre-render one correction clip per step with `gemini-3.8-flash-tts`, or ElevenLabs if someone has a key. Record your own voice if neither works by 05:30.
- [ ] 05:45 Build the phone page: one tap to arm, then play the clip and call `navigator.vibrate`. Use Android Chrome, and test it early.
- [ ] 06:45 Add the verdict panel: reason, section, quote and hop timers.
- [ ] 07:45 Add the supervisor screen: run log, incident record, ask box and manual editor.
- [ ] 08:30 Log the 20 test runs into a results table, and record a full live run as the backup video.
- [ ] 09:15 Write 4 slides: story, architecture, test results, limits. Then the README and screenshots.
- [ ] 09:30 Rehearse twice with a timer.

## Test runs, 07:45 to 08:30

Do 20 live runs: 8 clean, then 4 each of E1, E2 and E3. Use a person who did not build the feature, if possible. Record errors caught, false alarms, and median reflex and verdict times. Those results are our only accuracy claim, and we report them as 20 runs on one mock bench.

## Demo script, 3 minutes

| Time | On screen | Say or do |
| --- | --- | --- |
| 0:00 to 0:25 | NTSB finding | "Four bolts. The NTSB blamed Boeing's failure to ensure staff could comply with its parts removal process. Vigil watches the process." |
| 0:25 to 0:50 | Clean S1 and S2 | Steps tick off, each with a stored evidence frame. Show live Kafka and hop timers. |
| 0:50 to 1:15 | E1 | Pick the module first. Phone says "Stop. Install the gasket first." and vibrates. Point to the timers and citation. |
| 1:15 to 1:40 | E2 | Route the cable through notch B. "The hands looked normal. Image plus manual caught it." |
| 1:40 to 2:05 | E3 | Switch to Rev B and repeat E1's motion. The reflex fires, then Gemini clears it by quoting Note 4.1. |
| 2:05 to 2:30 | Judge edit | A judge changes one manual line. Re-ingest, approve, and the same motion gets a new verdict. |
| 2:30 to 3:00 | Incident and results | Show the incident record. "A mock unit, one bench, 20 runs. We do not claim production accuracy." |

Do not say "zero delay", "production ready" or "no competitors". Say "tested on a 10 to 12 page manual", not "300 pages".

## Judge questions

| Question | Answer |
| --- | --- |
| Why Kafka for one bench? | It gives evidence frames by offset, full session replay and independent consumers. More benches become more partitions. |
| Why YOLO and MediaPipe together? | YOLOv8-Pose finds the person and wrists. MediaPipe adds the fingers that YOLO's COCO model lacks. |
| Is YOLOv8 licensed for this? | Ultralytics is AGPL-3.0. Our repo is public, and a commercial product would need to review that license. |
| What is your accuracy? | Only our 20-run table, on one mock bench. No field accuracy exists. |
| What if Gemini is wrong or down? | The reflex still fires. A quote not found in the manual becomes `uncertain` and holds the unit for a supervisor. A missed visual error remains a real risk. |
| Would this handle 300 pages? | Vector search took about 5 ms on 1,000 test rows, so speed looks fine. Retrieval quality at that size is untested. |
| Does this already exist? | Yes, vendors sell guided assembly systems, and we have not done a market scan. Our demo reads its rules from the manual, with engineer approval. |
| Is this worker surveillance? | The camera frames the bench, stored frames follow flagged events, and runs store a unit serial, not a worker's identity. A real plant needs worker consent. |

## Submission

Submit at 10:00, not 12:00. Use Artificial Intelligence and Internet of Things, unless an organiser says otherwise. If shortlisted, pitching is 16:00 to 17:00.

| Prize | Reward | What judges must see |
| --- | --- | --- |
| Main | Rs 50,000, 35,000, 25,000 | The live demo |
| YugabyteDB Outstanding AI Agent Innovation | Rs 50,000, gadgets for second | Vector retrieval, run memory and the incident agent in one database |
| MLH Best Use of Gemini API | Kreo mechanical keyboards | Vision verdicts, structured output, embeddings, function calling |

We have not seen whether prizes stack, or the YugabyteDB and Gemini entry rules, so ask at the venue.

- [ ] Public GitHub repo with commits from today only
- [ ] README: what it does, architecture, how to run, limits
- [ ] Backup demo video
- [ ] Description states that the unit and manual are mock, with 20 test runs on one bench
- [ ] Themes and prize entries selected
- [ ] Bench packed so it moves as one tray, with tape marks kept
- [ ] Redo zones and test the camera in the pitch room, because lighting will change

## Not tested yet

The Kafka config, WebRTC ingest, YOLO fps, the camera angle, Gemini latency with images, phone HTTPS and browser vibration are all untested. The YOLO and Gemini tests come first for this reason.

## Sources

Opened on 1 November 2026, unless noted:

- [Gemini API deprecations](https://ai.google.dev/gemini-api/docs/deprecations): model list and recommended models
- [Gemini image understanding](https://ai.google.dev/gemini-api/docs/image-understanding): inline images and the 20 MB request limit
- [MediaPipe Hand Landmarker for web](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/web_js): 21 hand landmarks
- [Ultralytics COCO8-Pose](https://docs.ultralytics.com/datasets/pose/coco8-pose): 17 keypoints and AGPL-3.0 header
- [Ultralytics pose models](https://docs.ultralytics.com/tasks/pose/): YOLO26n-pose speed table
- [Apache Kafka quickstart](https://kafka.apache.org/quickstart): version 4.4.0 and the Docker image
- [YugabyteDB pgvector](https://docs.yugabyte.com/stable/additional-features/pg-extensions/extension-pgvector): `ybhnsw` index
- [NTSB investigation DCA24MA063](https://www.ntsb.gov/investigations/Pages/DCA24MA063.aspx): Alaska 1282 probable cause
- hackCBS site copy, saved 31 October: schedule, themes, prizes and rules
- `hackcbs9/reports/India deep pain problems for hackCBS.md`: event constraints
- Our Gemini model list, pulled 31 October
