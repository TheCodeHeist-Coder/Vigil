import type { Live } from "../live";
import type { Procedure, Step } from "../types";
import { Icon } from "./Icon";

type Tone = "idle" | "now" | "stop" | "hold" | "good";

export type BannerView = {
  tone: Tone;
  eyebrow: string;
  title: string;
  detail?: string;
  checking?: boolean;
};

export function nextStep(procedure: Procedure | null, live: Live): Step | null {
  const state = live.state;
  if (!procedure || !state) return null;
  return procedure.steps.find((s) => !state.done.includes(s.id) && !state.waived.includes(s.id)) ?? null;
}

export function bannerFor(procedure: Procedure | null, live: Live): BannerView {
  const { state, alert, verdict } = live;
  if (!state) return { tone: "idle", eyebrow: "Ready", title: "Start a unit to begin", detail: "Vigil will guide each step and stop any mistake." };

  const total = procedure?.steps.length ?? 0;
  const finished = state.done.length + state.waived.length;
  if (state.finished) return { tone: "good", eyebrow: "Complete", title: `Unit ${state.serial} is finished`, detail: "Every step is done. Start the next unit when you are ready." };

  if (state.held && alert) {
    const decided = verdict?.flag_id === alert.flag_id ? verdict : null;
    if (decided?.status === "uncertain") return { tone: "hold", eyebrow: "Hold", title: "Stop and call a supervisor", detail: "Vigil could not confirm this from the manual." };
    if (decided?.status === "confirmed") return { tone: "stop", eyebrow: "Stop", title: alert.text.replace(/^Stop\.\s*/, ""), detail: decided.explanation };
    return { tone: "stop", eyebrow: "Stop", title: alert.text.replace(/^Stop\.\s*/, ""), detail: "Checking the manual", checking: true };
  }

  if (verdict?.reason === "step_check" && verdict.status === "confirmed" && !state.done.includes(verdict.step_id)) {
    return { tone: "stop", eyebrow: "Stop", title: verdict.spoken ?? "Redo this step", detail: verdict.explanation };
  }

  const step = nextStep(procedure, live);
  const position = `Step ${finished + 1} of ${total}`;
  const instruction = step ? `Take the part from Bin ${step.bin}.` : undefined;
  if (verdict?.reason === "out_of_sequence" && verdict.status === "cleared") {
    return { tone: "good", eyebrow: "Carry on", title: step?.title ?? "Carry on", detail: `The manual allows this on Rev ${state.revision}. ${instruction ?? ""}` };
  }
  return { tone: "now", eyebrow: position, title: step?.title ?? "", detail: instruction };
}

const ICONS = { idle: "bench", now: "arrow", stop: "stop", hold: "alert", good: "check" } as const;

export function Banner({ view, progress, onEnd }: { view: BannerView; progress: number | null; onEnd?: () => void }) {
  return (
    <section className={`banner ${view.tone}`} role={view.tone === "stop" || view.tone === "hold" ? "alert" : "status"}>
      <span className="banner-icon">
        <Icon name={ICONS[view.tone]} size={30} />
      </span>
      <div className="banner-text">
        <span className="eyebrow">{view.eyebrow}</span>
        <h1>{view.title}</h1>
        {view.detail && (
          <p>
            {view.checking && <span className="spinner" />}
            {view.detail}
          </p>
        )}
      </div>
      {onEnd && (
        <button className="ghost end-run" onClick={onEnd}>
          End run
        </button>
      )}
      {progress !== null && (
        <span className="progress" aria-hidden="true">
          <span style={{ width: `${progress * 100}%` }} />
        </span>
      )}
    </section>
  );
}
