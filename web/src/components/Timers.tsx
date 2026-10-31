import type { HandTrack, Verdict } from "../types";

const ms = (from?: number, to?: number) => (from && to ? `${Math.round((to - from) * 1000)} ms` : "-");

type Props = { reflexMs: number | null; verdict: Verdict | null; track: HandTrack | null };

export function Timers({ reflexMs, verdict, track }: Props) {
  const times = track?.times ?? {};
  const v = verdict?.times ?? {};
  return (
    <section className="timers">
      <div>
        <b>{reflexMs === null ? "-" : `${reflexMs} ms`}</b>
        <span>Frame to alert</span>
      </div>
      <div>
        <b>{ms(v.t_ingest, v.t_reasoner)}</b>
        <span>Frame to verdict</span>
      </div>
      <div>
        <b>{ms(times.t_ingest, times.t_edge)}</b>
        <span>Vision hop</span>
      </div>
      <div>
        <b>{verdict ? `${verdict.latency_ms} ms` : "-"}</b>
        <span>Reasoning</span>
      </div>
    </section>
  );
}
