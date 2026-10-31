import type { Incident, Verdict } from "../types";

function heading(verdict: Verdict): string {
  if (verdict.reason === "step_check") {
    return { confirmed: "Step failed its photo check", cleared: "Step passed its photo check", uncertain: "Photo not checked" }[verdict.status];
  }
  return { confirmed: "Mistake confirmed", cleared: "Allowed by the manual", uncertain: "Needs a supervisor" }[verdict.status];
}

function checkedBy(verdict: Verdict): string {
  if (verdict.model === "none") return "No photo available";
  const who = verdict.model.startsWith("gemini") ? "Gemini" : "local rules";
  return `Checked by ${who} in ${(verdict.latency_ms / 1000).toFixed(1)} s`;
}

export function Decision({ verdict, incident }: { verdict: Verdict | null; incident: Incident | null }) {
  if (!verdict) {
    return (
      <section className="card">
        <h2>Latest decision</h2>
        <p className="muted decision-empty">Each check appears here, with the part of the manual behind it.</p>
      </section>
    );
  }
  return (
    <section className={`card decision ${verdict.status}`}>
      <span className="eyebrow">Latest decision</span>
      <h2>{heading(verdict)}</h2>
      <p>{verdict.explanation}</p>
      {verdict.citations.map((citation) => (
        <blockquote key={citation.section + citation.quote}>
          <span>{citation.quote}</span>
          <cite>
            Manual section {citation.section}, page {citation.page}
          </cite>
        </blockquote>
      ))}
      <footer>
        <span>{checkedBy(verdict)}</span>
        {verdict.source === "replay" && <span className="replay-tag">REPLAY</span>}
      </footer>
      {verdict.status === "confirmed" && !incident && (
        <p className="muted fix-wait">
          <span className="spinner" />
          Working out the fix
        </p>
      )}
      {incident && (
        <div className="fix">
          <h3>How to fix it</h3>
          <ol>
            {incident.rework.map((line) => (
              <li key={line}>{line.replace(/^Do S\d+: /, "").replace(/^Undo S\d+: /, "Undo: ")}</li>
            ))}
          </ol>
          {incident.occurrences > 1 && <p className="repeat">This step has failed {incident.occurrences} times.</p>}
        </div>
      )}
    </section>
  );
}
