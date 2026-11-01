# Vigil problem and solution brief

Vigil watches a manual assembly bench and stops a wrong step as it happens, then checks that decision against the engineering manual and quotes the page. It catches mistakes in the process, which ordinary inspection cameras cannot see. Built for hackCBS 9.0, it runs on one laptop with no GPU, on a mock product and a 10 page manual.

## The problem

**In one line:** assembly mistakes happen in the process, and nothing on the line watches the process.

Electronics, aerospace and medical device makers still rely on skilled people assembling products by hand from long engineering manuals. A missed bolt or a step done out of order can leave no visible sign, and the product can look perfect when it ships.

**The real case.** In January 2024, a door plug blew out of Alaska Airlines Flight 1282 in flight. The [NTSB](https://www.ntsb.gov/investigations/Pages/DCA24MA063.aspx) reported that four bolts meant to secure the plug "were not located". It named the probable cause as Boeing's failure to give the training, guidance and oversight that staff needed to "consistently and correctly comply with its parts removal process". The FAA [grounded 171 Boeing 737 Max 9 planes](https://www.nbcwashington.com/news/business/money-report/boeing-pays-alaska-airlines-160-million-for-737-max-9-grounding/), and Boeing paid Alaska Airlines $160 million in that quarter alone.

**The pattern.** A [National Academies workshop report](https://www.nationalacademies.org/read/13020/chapter/9) found that manufacturing process errors caused 28.8% of the FDA 510(k) device recalls it studied, using data from 2003 to 2009. Employee error alone caused only 7.1%. The weakness is usually the process around the person, not the person.

**Full problem statement.** Technicians follow complex procedures by hand, and a single procedural error can become a recall or a safety failure. Existing vision systems judge one image at a time, so they cannot tell whether steps happened in the right order, or whether a variation is allowed for this unit. Manufacturers need a system that watches the work as it happens, understands the manual, and steps in before the mistake is sealed inside the product.

## Why today's tools fall short

Each existing check looks at a result, a single image or a signature, so none of them follows the procedure as it happens.

| Check | What it catches | What it misses |
| --- | --- | --- |
| Final inspection | Visible defects on the finished product | Faults sealed inside, and how they happened |
| Object detection cameras | A part that is missing or misplaced in one image | Step order, what happened earlier, allowed exceptions |
| Paper sign-offs | What people recorded | Steps nobody remembered to record |
| A supervisor watching | Almost anything, with good judgement | Every bench, all day |

A useful system needs two things together: memory of what has happened so far, and an understanding of the manual. A camera alone has neither.

## Our solution

**In one line:** Vigil is an AI supervisor for the assembly bench that knows the manual, watches each step, and speaks up the moment one goes wrong.

Here is how it works for the people using it:

1. **An engineer loads the manual.** Vigil reads the steps out of it, and the engineer approves them before anything reaches the bench.
2. **The operator is guided.** A screen always shows the next action, such as "Step 2 of 5, take the part from Bin B", and that bin glows on the live video.
3. **A mistake gets an instant stop.** If a hand reaches for the wrong part, the operator hears the correction and feels a vibration, with no wait for the cloud.
4. **The manual decides.** Gemini checks the event against the manual, then confirms the mistake or clears it, and quotes the exact section and page.
5. **The fix is written down.** A confirmed mistake creates an incident record with the rework steps, and that memory carries into later runs.

## How it works

The stop comes from a local rule straight away, and the manual check follows a few seconds later. Redraw this as the architecture slide.

```text
 Camera on the bench
    |  WebRTC video
    v
 ingest ----> Kafka (video frames)
                  |
                  v
              edge: YOLOv8-Pose + MediaPipe  (finds the hands)
                  |
                  v
              sequencer: bench zones + step rules
                  |
        +---------+----------------------+
        |                                |
   INSTANT PATH                    MANUAL CHECK PATH
   no network call                 a few seconds
        |                                |
        v                                v
   Voice, vibration                 reasoner + Gemini
   and red STOP on screen           reads the photos and the manual
                                         |
                                         +--> YugabyteDB: manual vectors, runs
                                         +--> Meko: agent memory and traces
                                         |
                                         v
                                    Confirm or clear, with a checked quote.
                                    The incident agent writes the fix.
```

## What makes Vigil different

Five ideas set Vigil apart, and each one is shown in the working product.

1. **Two speeds.** A local rule raises the alert with no network call, and that rule check takes about 2 ms. A slow or failed cloud call can never delay a stop.
2. **The rules come from the manual.** Change one line of the manual, approve it, and the bench behaves differently with no code change.
3. **Same motion, opposite verdict.** Picking the module first is a mistake on a Rev A unit. On a Rev B unit, Gemini clears it by quoting Note 4.1, because that unit ships with its gasket fitted.
4. **It cannot invent a rule.** Every quote is checked against the manual text, and the section and page come from where the quote was found. A quote that fails the check holds the unit for a person, and a photo check with no photo never passes.
5. **It remembers.** The verdict and incident agents share memory and decision traces through Meko, so a repeat fault across units is noticed. On the third fault at a step, the record applies manual section 6.4 and raises it to the process engineer.

## Technology

We built the full problem statement stack, changing the model only because Gemini 1.5 Flash is no longer available.

| Part of the problem | What we used | Why it matters |
| --- | --- | --- |
| Video in | WebRTC into Apache Kafka | Frames are kept, so evidence can be fetched by offset and a session can be replayed |
| Fast vision at the edge | YOLOv8-Pose with MediaPipe Hand Landmarker | YOLO finds the operator and wrists, and MediaPipe adds the 21 hand points YOLO lacks. Runs on a laptop CPU through OpenVINO. |
| Reasoning | Gemini 3.5 Flash-Lite, with 3.8 Flash as fallback | Reads photos and manual text together, with structured answers |
| Manual knowledge | YugabyteDB with pgvector and Gemini embeddings | Sections and chunks are stored as a hierarchy, and step text is fetched exactly |
| Agent context | Meko by Yugabyte | Shared memory, conversations and decision traces across runs |
| Stepping in | Voice and vibration on a phone browser | The operator never has to look away |
| Screens | React with a FastAPI gateway | Bench, Camera, Phone and Supervisor pages |

Six services each have their own folder, and the live pipeline talks through Kafka, so a service can be replaced or scaled alone.

## Proof

The whole pipeline runs on one laptop with no GPU, and these are measured results, not estimates.

| Measure | Result | How it was tested |
| --- | --- | --- |
| Video into Kafka | 1280 x 720 | Real Chrome over WebRTC, with a simulated camera |
| Pose model speed | 29 fps at 480 px | YOLOv8-Pose alone on the CPU |
| Hand tracking through Kafka | 11 to 13 fps, median 95 ms | Sample photo replayed as a video stream |
| Step rule check | About 2 ms | Live services, simulated hand |
| Gemini order check | 1.5 to 2.9 s | Live Gemini, simulated hand |
| Gemini order check, real camera | 4.2 s | One live run with the laptop camera |
| Gemini photo check | 9 of 9 correct | Drawn bench images, 3 times each |
| Injected note in the photo | Ignored 3 of 3 times | A note telling the model to pass the step |
| Manual search | Right section on 4 of 4 questions | Real embeddings, 10 page manual |
| Automated tests | 48 | Rules, citations, memory client, video path |

**Our 20 real runs.** Fill this in after testing on the bench. Do not present these as results until they are real.

| Runs | Mistakes caught | Mistakes missed | False alarms | Typical alert time | Typical manual check |
| --- | --- | --- | --- | --- | --- |
|  |  |  |  |  |  |

Quote the real-camera time alongside the simulated range. It comes from a single run, so treat it as an early reading until the 20 runs are done.

## The demo

Three moments prove the idea, and a judge can try the fourth themselves.

1. **Wrong order.** On a Rev A unit, reach for the module before the gasket. The screen turns red, the phone says "Stop. Install the gasket first", and Gemini confirms it with a quote from the manual.
2. **Same motion, allowed.** Switch to a Rev B unit and repeat it. The stop fires, then the screen turns green and quotes Note 4.1, because the manual allows it. A basic detector cannot do this.
3. **Looks right, is wrong.** Route the cable through notch B. The hands look normal, so only the photo and the manual can catch it. This needs a camera that can see the tray.
4. **Hand a judge the manual.** They change one line, an engineer approves it, and the same motion gets a new verdict with no code change.

Record a backup video first, and show a clear REPLAY label if a fallback is ever used.

## Who it is for

The buyer is the quality head at a plant with manual assembly, in electronics, aerospace or medical devices.

- **Fewer escapes.** A mistake is caught at the step, before it is sealed inside the product and while the fix is still cheap.
- **A record for every unit.** Each check is stored with its reason, its manual citation and its rework, which answers "what happened on this unit?"
- **Fast to set up.** A new product needs its manual and its bench zones. The vision models are general, so there is no per-product model to train.
- **Better instructions.** Repeat faults at one step point to a weak instruction, which gives engineers something to fix.
- **Built to scale.** Each bench gets its own Kafka key, and the vision service can move to a GPU machine without touching the rest.

We have not validated pricing or tested this with a customer. The next step is a pilot on one real line.

## Limits

Say these before a judge asks, because stating them plainly builds trust.

| Limit | What to say |
| --- | --- |
| Mock product | The unit and 10 page manual are ours, written for this demo. |
| Not zero delay | The stop comes first, and the manual check follows in a few seconds. We show the real times on screen. |
| 300 pages untested | Vector search took about 5 ms on 1,000 test rows, so speed looks fine. Retrieval quality at that size is untested. |
| Camera position | YOLOv8-Pose needs to see the operator's body, so the camera sits high and in front. |
| Vibration | It needs Chrome on Android, and we have not tested it on a real phone yet. |
| Worker trust | The camera frames the bench, and runs store a unit serial, not a worker's identity. A real plant needs worker consent. |
| Licensing | Ultralytics is AGPL-3.0, so a commercial product would need to review that. |
| Competition | Vendors sell guided assembly systems, and we have not done a market scan. Do not say "no competitors". |

## Slide plan

Ten slides carry the story, with the live demo as the centre of the pitch.

| Slide | Title | One message | What to show |
| --- | --- | --- | --- |
| 1 | Vigil | An AI supervisor for the assembly bench | Name, one line, team |
| 2 | Four bolts | One assembly process failure grounded 171 planes | NTSB finding, $160 million paid to Alaska Airlines |
| 3 | The process is the gap | 28.8% of recalls in one study came from manufacturing process errors | The figure, with its study and years |
| 4 | Why cameras are not enough | Today's checks judge results, not procedures | The four-row table from this brief |
| 5 | Meet Vigil | It knows the manual, watches each step, and speaks up | The five numbered steps |
| 6 | How it works | The stop is instant, and the manual check follows | The diagram from this brief |
| 7 | Live demo | Same motion, opposite verdict | The real bench |
| 8 | Why it can be trusted | It quotes the manual or it holds for a person | Five differences, with quote checking in focus |
| 9 | Proof and limits | Real numbers, stated plainly | Your 20-run table and the main limits |
| 10 | Where it goes next | One real line first | Buyer, value, pilot plan |

## Sources

- [NTSB investigation DCA24MA063](https://www.ntsb.gov/investigations/Pages/DCA24MA063.aspx): probable cause and the missing bolts
- [NBC Washington on Boeing's payment to Alaska Airlines](https://www.nbcwashington.com/news/business/money-report/boeing-pays-alaska-airlines-160-million-for-737-max-9-grounding/): 171 planes grounded and $160 million paid
- [National Academies workshop report on the FDA 510(k) process](https://www.nationalacademies.org/read/13020/chapter/9): recall causes, 2003 to 2009 data
- [Gemini API deprecations](https://ai.google.dev/gemini-api/docs/deprecations): current models, with 1.5 Flash no longer listed
- [MediaPipe Hand Landmarker](https://developers.google.com/edge/mediapipe/solutions/vision/hand_landmarker/web_js): 21 hand landmarks
- [Ultralytics COCO8-Pose](https://docs.ultralytics.com/datasets/pose/coco8-pose): 17 body keypoints and the AGPL-3.0 license
- [YugabyteDB pgvector](https://docs.yugabyte.com/stable/additional-features/pg-extensions/extension-pgvector): vector search
- [Meko MCP server reference](https://docs.mekodata.ai/reference/mcp-server): agent memory tools

All measurements come from our own tests on 1 November 2026.
