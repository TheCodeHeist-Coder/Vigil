import type { Live } from "../live";
import type { Procedure } from "../types";
import { Icon } from "./Icon";

const PHOTO = { cleared: "Photo check passed", confirmed: "Photo check failed", uncertain: "Photo not checked" };

export function Steps({ procedure, live, nowId }: { procedure: Procedure | null; live: Live; nowId: string | null }) {
  const state = live.state;
  return (
    <section className="card">
      <h2>Assembly steps</h2>
      <ol className="steps">
        {procedure?.steps.map((step, i) => {
          const done = state?.done.includes(step.id);
          const waived = state?.waived.includes(step.id);
          const now = nowId === step.id;
          const check = live.checks[step.id];
          return (
            <li key={step.id} className={done ? "done" : waived ? "waived" : now ? "now" : ""} aria-current={now ? "step" : undefined}>
              <span className="marker">{done ? <Icon name="check" size={15} /> : i + 1}</span>
              <div>
                <b>{step.title}</b>
                <small>
                  {waived ? "Not needed on this unit" : `Bin ${step.bin}`}
                  {check && <em className={check}> · {PHOTO[check]}</em>}
                </small>
              </div>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
