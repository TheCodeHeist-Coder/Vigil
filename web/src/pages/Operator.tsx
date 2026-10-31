import { useEffect, useState } from "react";
import { get, post } from "../api";
import { Stage } from "../components/Stage";
import { Steps } from "../components/Steps";
import { Timers } from "../components/Timers";
import { VerdictPanel } from "../components/VerdictPanel";
import { useLive } from "../live";
import { beep, say, unlockSound } from "../sound";
import type { Procedure, Status, Verdict, Zone } from "../types";

function speakVerdict(verdict: Verdict) {
  if (verdict.status === "confirmed" && verdict.reason === "step_check") {
    beep();
    say(verdict.spoken ?? "Stop. Check this step.");
  } else if (verdict.status === "cleared" && verdict.reason === "out_of_sequence") {
    say("Cleared. The manual allows this. Carry on.");
  }
}

export function Operator() {
  const [procedure, setProcedure] = useState<Procedure | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [status, setStatus] = useState<Status | null>(null);
  const [serial, setSerial] = useState("VG100-0001");
  const [revision, setRevision] = useState<"A" | "B">("A");

  const live = useLive({
    onAlert: (alert) => {
      beep();
      say(alert.text, alert.clip);
    },
    onVerdict: speakVerdict,
  });

  useEffect(() => {
    void get<Procedure>("/api/procedure").then(setProcedure);
    void get<Zone[]>("/api/zones").then(setZones);
    const refresh = () => void get<Status>("/api/status").then(setStatus);
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, []);

  async function start() {
    unlockSound();
    await post("/api/runs", { serial, revision });
    void get<Procedure>("/api/procedure").then(setProcedure);
  }

  const { state, alert, alertMs, verdict, track, incident } = live;
  const held = state?.held && alert;
  const expectedBin = procedure?.steps.find((s) => !state?.done.includes(s.id) && !state?.waived.includes(s.id))?.bin ?? null;

  return (
    <main className="operator">
      <header className="bar">
        <h1>Vigil</h1>
        <span className={`chip ${status?.camera_live ? "good" : "bad"}`}>{status?.camera_live ? "Camera live" : "No camera"}</span>
        <span className="chip">{status?.model ?? "..."}</span>
        <span className={`chip ${status?.meko.state === "connected" ? "good" : ""}`}>Memory: {status?.meko.state === "connected" ? "Meko" : "YugabyteDB"}</span>
        {status?.replay && <span className="chip bad">REPLAY MODE</span>}
        <div className="run">
          <input value={serial} onChange={(e) => setSerial(e.target.value)} aria-label="Unit serial" />
          <select value={revision} onChange={(e) => setRevision(e.target.value as "A" | "B")} aria-label="Unit revision">
            <option value="A">Rev A</option>
            <option value="B">Rev B</option>
          </select>
          <button onClick={start}>Start run</button>
        </div>
      </header>

      <div className={`hold ${held ? "show" : ""}`} role="alert">
        {held ? alert.text : ""}
      </div>

      <div className="columns">
        <div>
          <Stage zones={zones} onZones={setZones} track={track} expectedBin={state ? expectedBin : null} />
          <Timers reflexMs={alertMs} verdict={verdict} track={track} />
        </div>
        <aside>
          {state?.finished && <section className="card finished">Unit {state.serial} complete</section>}
          <Steps procedure={procedure} state={state} />
          <VerdictPanel verdict={verdict} incident={incident} />
        </aside>
      </div>
    </main>
  );
}
