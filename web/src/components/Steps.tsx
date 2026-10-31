import type { Procedure, RunState } from "../types";

export function Steps({ procedure, state }: { procedure: Procedure | null; state: RunState | null }) {
  return (
    <ol className="steps">
      {procedure?.steps.map((step) => {
        const done = state?.done.includes(step.id);
        const waived = state?.waived.includes(step.id);
        const active = state?.active === step.id;
        const label = done ? "done" : waived ? "not needed" : active ? "now" : "";
        return (
          <li key={step.id} className={done ? "done" : waived ? "waived" : active ? "active" : ""}>
            <b>{step.id}</b>
            <span>
              {step.title}
              <small>
                Bin {step.bin}, section {step.section}
              </small>
            </span>
            <em>{label}</em>
          </li>
        );
      })}
    </ol>
  );
}
