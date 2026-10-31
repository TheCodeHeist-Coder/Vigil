# Vigil build plan

We build the full PS stack on one bench laptop: WebRTC video into Kafka, YOLOv8-Pose on the edge, Gemini with a YugabyteDB vector store, and voice plus haptics on a phone. The demo is a small mock product with a 10 to 12 page manual and 5 steps, not a real factory. The freeze is 09:30 IST on 1 November, about 6 hours away, so no gate can slip far.

Only one PS item changes. Gemini 1.5 Flash no longer exists, so we use a current Gemini model.

## Status at 04:05 IST

The whole application is built and running. Every service, all four screens, and real WebRTC from Chrome through Kafka work end to end. The team's remaining work is the physical bench, the two keys and the demo.

| Measured on the demo laptop | Result |
| --- | --- |
| WebRTC to Kafka, from real Chrome | 1280x720, no dropped frames |
| YOLOv8-Pose alone, 480 px, CPU | 29 fps |
| Hand tracking through Kafka | 11 to 13 fps, median 95 ms from ingest |
| Sequencer rule check | 2 ms |
| Frame to alert on screen, simulated | 14 ms, not counting vision and camera time |
| Four evidence frames from Kafka | 87 ms |
| Vector search, 1,000 rows | 5 ms |

**Not tested yet:** live Gemini verdicts, live Meko, and tracking on real hands at a real bench. Gemini and Meko need keys. Real hands need the bench.

## Do these next

1. Put `GEMINI_API_KEY` and `MEKO_API_KEY` in `.env`. Get them from aistudio.google.com and cloud.mekodata.ai, then run the three commands in the README's Keys section.
2. Build the bench below, stream the camera, draw the zones and run all three errors with real hands.
3. Tune `DWELL_SECONDS` and `CLEAR_SECONDS` in `services/sequencer/zones.py` if picks are missed or false.
4. Record clips into `clips/`, do the 20 test runs, and record the backup video.
5. Ask the organisers whether a phone hotspot counts as a second connection. The site allows at most one connection per team.

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

Meko holds agent context: conversations, memory and decision traces in the `vigil-bench` datapack, shared by the verdict and incident agents. Manual search stays in YugabyteDB for speed.

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
| Why Meko and YugabyteDB? | YugabyteDB holds the manual vectors and run records. Meko gives both agents shared memory and decision traces across runs. |
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

## Still untested

Live Gemini verdicts, live Meko calls, the camera angle, tracking on real hands, phone HTTPS and vibration on a real phone are all untested.

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
- [Meko MCP server reference](https://docs.mekodata.ai/reference/mcp-server) and [API keys](https://docs.mekodata.ai/reference/api-keys): tools and auth
- [yugabyte/canned-agents](https://github.com/yugabyte/canned-agents): reference Meko client
