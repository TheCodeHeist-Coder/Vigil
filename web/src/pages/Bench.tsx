import { useEffect, useState } from "react";
import { get, post } from "../api";
import { Banner, bannerFor, nextStep } from "../components/Banner";
import { Decision } from "../components/Decision";
import { Speed } from "../components/Speed";
import { Stage } from "../components/Stage";
import { StartCard } from "../components/StartCard";
import { Steps } from "../components/Steps";
import { useLive } from "../live";
import { beep, say, unlockSound } from "../sound";
import type { Procedure, Status, Verdict, Zone } from "../types";

function speakVerdict(verdict: Verdict) {
  if (verdict.status === "confirmed" && verdict.reason === "step_check") {
    beep();
    say(verdict.spoken ?? "Stop. Check this step.");
  } else if (verdict.status === "cleared" && verdict.reason === "out_of_sequence") {
    say("Cleared. The manual allows this. Carry on.");
  } else if (verdict.status === "uncertain" && verdict.reason === "out_of_sequence") {
    say("Hold. Call your supervisor.");
  }
}

const LOOK_TIMEOUT_MS = 12000;

function nextSerial(serial: string): string {
  return serial.replace(/(\d+)$/, (digits) => String(Number(digits) + 1).padStart(digits.length, "0"));
}

export function Bench({ status }: { status: Status | null }) {
  const [procedure, setProcedure] = useState<Procedure | null>(null);
  const [zones, setZones] = useState<Zone[]>([]);
  const [setup, setSetup] = useState(false);
  const [looking, setLooking] = useState(false);

  const live = useLive({
    onAlert: (alert) => {
      beep();
      say(alert.text, alert.clip);
    },
    onVerdict: (verdict) => {
      setLooking(false);
      speakVerdict(verdict);
    },
  });

  useEffect(() => {
    void get<Procedure>("/api/procedure").then(setProcedure);
    void get<Zone[]>("/api/zones").then(setZones);
  }, []);

  function checkAgain() {
    setLooking(true);
    void post("/api/runs/recheck", {});
    setTimeout(() => setLooking(false), LOOK_TIMEOUT_MS); // never leave the button stuck
  }

  async function start(serial: string, revision: "A" | "B", photoChecks: boolean) {
    unlockSound();
    await post("/api/runs", { serial, revision, photo_checks: photoChecks });
    void get<Procedure>("/api/procedure").then(setProcedure);
  }

  const { state, alert } = live;
  const running = Boolean(state && !state.finished);
  const view = bannerFor(procedure, live);
  const step = nextStep(procedure, live);
  const held = state?.held && alert ? alert.step_id : null;
  const nowId = held ?? step?.id ?? null;
  const targetBin = running ? (procedure?.steps.find((s) => s.id === nowId)?.bin ?? null) : null;
  const total = procedure?.steps.length ?? 0;
  // During a fault, the fix matters more than the step list, so it moves to the top.
  const fault = live.verdict?.status === "confirmed" || live.verdict?.status === "uncertain";
  const progress = state && total ? (state.done.length + state.waived.length) / total : null;

  return (
    <main className="bench">
      <Banner
        view={view}
        progress={progress}
        looking={looking}
        onEnd={running ? () => void post("/api/runs/stop", {}) : undefined}
        onCheck={running ? checkAgain : undefined}
        onRelease={running ? () => void post("/api/runs/release", {}) : undefined}
      />
      <div className="bench-grid">
        <div className="bench-main">
          <Stage zones={zones} bins={procedure?.steps.map((s) => s.bin) ?? []} onZones={setZones} track={live.track} targetBin={targetBin} cameraLive={status?.camera_live ?? false} setup={setup} onSetup={setSetup} />
          {running && <Speed live={live} />}
        </div>
        <aside className="bench-side">
          {running ? (
            <>
              {fault && <Decision verdict={live.verdict} incident={live.incident} />}
              <Steps procedure={procedure} live={live} nowId={nowId} />
              {!fault && <Decision verdict={live.verdict} incident={live.incident} />}
            </>
          ) : (
            <StartCard key={state?.run_id ?? "first"} cameraLive={status?.camera_live ?? false} onSetup={() => setSetup(true)} onStart={start} suggested={state ? nextSerial(state.serial) : "VG100-0001"} returning={Boolean(state)} />
          )}
        </aside>
      </div>
    </main>
  );
}
