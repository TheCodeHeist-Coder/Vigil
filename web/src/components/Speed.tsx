import type { Live } from "../live";

const seconds = (ms: number) => (ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`);

export function Speed({ live }: { live: Live }) {
  const { alertMs, verdict, track } = live;
  const v = verdict?.times ?? {};
  const t = track?.times ?? {};
  const check = v.t_ingest && v.t_reasoner ? (v.t_reasoner - v.t_ingest) * 1000 : null;
  const vision = t.t_ingest && t.t_edge ? (t.t_edge - t.t_ingest) * 1000 : null;
  return (
    <dl className="speed">
      <div title="From the camera frame reaching Vigil to the alert on this screen">
        <dt>Alert</dt>
        <dd>{alertMs === null ? "–" : seconds(alertMs)}</dd>
      </div>
      <div title="From the camera frame to a decision checked against the manual">
        <dt>Manual check</dt>
        <dd>{check === null ? "–" : seconds(check)}</dd>
      </div>
      <div title="Time to find the hands in one camera frame">
        <dt>Hand tracking</dt>
        <dd>{vision === null ? "–" : seconds(vision)}</dd>
      </div>
    </dl>
  );
}
