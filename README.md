# Vigil

Electronics, aerospace and medical device makers still rely on skilled people assembling
products by hand from long engineering manuals. A missed bolt or a step done out of
order can leave no visible sign, and the product can look perfect when it ships.

## Full problem statement.
Technicians follow complex procedures by hand, and a single
procedural error can become a recall or a safety failure. Existing vision systems judge one
image at a time, so they cannot tell whether steps happened in the right order, or whether
a variation is allowed for this unit. Manufacturers need a system that watches the work as
it happens, understands the manual, and steps in before the mistake is sealed inside the
product

## Solution :-

Vigil is an AI supervisor for the assembly bench that knows the manual, watches each step, and speaks up the moment one goes wrong.

Here is how it works for the people using it:
1. An engineer loads the manual. Vigil reads the steps out of it, and the engineer approves them before anything reaches the bench.
2. The operator is guided. A screen always shows the next action, such as "Step 2 of 5, take the part from Bin B", and that bin glows on the live video.
3. A mistake gets an instant stop. If a hand reaches for the wrong part, the operator hears the correction and feels a vibration, with no wait for the cloud.
4. The manual decides. Gemini checks the event against the manual, then confirms the mistake or clears it, and quotes the exact section and page.
5. The fix is written down. A confirmed mistake creates an incident record with the rework steps, and that memory carries into later runs


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

## How we use YugabyteDB, Meko and the Gemini API

Each has one clear job, and all three work together on every flagged event.

| Technology | Its job in Vigil |
| --- | --- |
| **YugabyteDB** | Stores the manual as searchable vectors, plus every run, verdict and incident |
| **Gemini API** | Reads the manual, looks at bench photos, makes decisions and writes incident reports |
| **Meko** | Gives the AI agents shared memory and a record of their reasoning across runs |

### What happens when a mistake is flagged

1. A hand enters the wrong bin. The sequencer raises the stop straight away and sends a flag.
2. The reasoner fetches up to 4 evidence frames from Kafka.
3. **YugabyteDB** returns the manual text for the steps involved.
4. Notes from earlier runs, already fetched from **Meko**, are added as background.
5. **Gemini** reads the frames, manual text and notes, then answers with a status, a reason and an exact quote.
6. Code checks that answer. The quote must exist in the manual, and clearing an order mistake needs a rule that names this unit's revision.
7. The verdict is saved in **YugabyteDB**, the reasoning goes to **Meko**, and the screens update.
8. If the mistake is confirmed, the incident agent uses **Gemini** to write the report, and the lesson is saved to **Meko** for later runs.

### YugabyteDB

YugabyteDB is our one database. It speaks the PostgreSQL protocol, so services connect with a normal PostgreSQL driver, and pgvector adds vector search in the same place as our records.

| Table | What it holds |
| --- | --- |
| `documents` | Each manual that has been loaded |
| `chunks` | Manual text and its 768-dimension embeddings, with a `ybhnsw` cosine index |
| `procedures` | The steps read from each manual, and who approved them |
| `runs` | Each unit assembled, with its serial and revision |
| `verdicts` | Every decision, with its reason, citations, model and time |
| `incidents` | Each confirmed fault, with its rework steps and report |
| `agent_memory` | A copy of agent notes, used if Meko is off or unreachable |

**How manual search works.** A manual is stored at two levels: sections, and smaller leaf chunks inside them.

1. Text for the steps involved is fetched exactly by its step tag, so it never depends on search quality.
2. A vector search finds the 3 closest sections.
3. A second vector search finds the 5 closest leaf chunks inside those sections.

Agents only search the approved manual, so an unapproved upload or edit changes nothing on the bench. See [`services/knowledge/retrieve.py`](services/knowledge/retrieve.py) and [`db/schema.sql`](db/schema.sql).

### Gemini API

Gemini handles everything that needs understanding, and the instant stop never waits for it.

| Use | Model | Gemini receives | Gemini returns |
| --- | --- | --- | --- |
| Reading a manual | `gemini-3.5-flash-lite` | Manual text | The steps, as structured JSON |
| Embeddings | `gemini-embedding-2` | Manual text and search queries | 768-dimension vectors |
| Order check | `gemini-3.5-flash-lite` | Up to 4 frames, manual text, notes | Status, reason and quote |
| Photo check | `gemini-3.5-flash-lite` | One photo with hands clear, up to 1024 px, plus the step's rule | Status, reason and quote |
| Incident report | `gemini-3.5-flash-lite` | The fault, with function calling | A short written report |
| Ask the manual | `gemini-3.5-flash-lite` | A question and manual text | An answer with a quote |
| Voice clips, optional | `gemini-3.8-flash-tts` | Each spoken correction | Audio files |

If the main decision model is busy, `gemini-3.8-flash` takes over.

The incident agent has three tools it can call by itself: `get_run` for what happened, `search_manual` for the rules, and `past_incidents` for the step's history. Rework steps are worked out in code from the procedure, never by the model.

**How we keep Gemini honest**

- Answers use temperature 0 and a fixed JSON schema.
- Every quote is checked against the manual text. A quote that is not there cannot pass.
- The section and page come from where the quote was found, not from the model.
- An order mistake can only be cleared by a rule naming this unit's revision, so a Rev B note can never clear a Rev A unit.
- A photo check with no photo never reaches the model.
- Text seen inside a photo is treated as evidence, never as an instruction.
- If Gemini is unavailable, `local-rules` decides order checks from the manual and photo checks return `uncertain`. The screen always shows which one decided.

See [`services/reasoner/judge.py`](services/reasoner/judge.py).

### Meko

[Meko](https://mekodata.ai) is Yugabyte's context engine for AI agents. Vigil connects to its MCP endpoint at `https://mcp.mekodata.ai/mcp` using a `mko_tkn_` key, and keeps everything in one datapack, `vigil-bench`.

Two agents share that datapack: `vigil-verdict` decides each event, and `vigil-incident` investigates confirmed faults. What one learns, the other can use.

| Meko tool | When we call it | Why |
| --- | --- | --- |
| `datapack_search`, `datapack_create` | At the first run | Finds or creates `vigil-bench` |
| `conversation_create` | Once per run | Groups everything that happens on one unit |
| `memory_search` | At the start of each run | Fetches notes on past faults, grouped by step |
| `memory_add` | After a confirmed fault | Saves the lesson, tagged with its step |
| `conversation_add_message` | After every verdict and incident | Records the decision and the reasoning behind it |

**Meko can never slow down the bench.** A memory search takes about 10 seconds, so calls run on their own thread, and verdicts read notes that were fetched ahead of time. YugabyteDB keeps its own copy of every note, so losing Meko loses nothing.

**Why this memory matters.** When a step keeps failing, agents can see that across units. On the third fault at a step, the incident record applies manual section 6.4 and raises it to the process engineer, because repeat faults point to the instruction, not the operator.

See [`services/reasoner/context.py`](services/reasoner/context.py) and [`services/reasoner/meko.py`](services/reasoner/meko.py).

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
uv run python -m services.knowledge.main manual/vdn1.md
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
uv run python -m services.knowledge.main manual/vdn1.md   # real embeddings
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
