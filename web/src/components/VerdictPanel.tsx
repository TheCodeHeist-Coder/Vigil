import type { Incident, Verdict } from "../types";

const TITLES = { confirmed: "Fault confirmed", cleared: "Cleared", uncertain: "Hold for supervisor" };

export function VerdictPanel({ verdict, incident }: { verdict: Verdict | null; incident: Incident | null }) {
  if (!verdict) return <section className="card verdict idle">Waiting for an event.</section>;
  return (
    <section className={`card verdict ${verdict.status}`}>
      <header>
        <h2>{TITLES[verdict.status]}</h2>
        {verdict.source === "replay" && <span className="badge replay">REPLAY</span>}
        <span className="badge">{verdict.model}</span>
      </header>
      <p>{verdict.explanation}</p>
      {verdict.citations.map((citation) => (
        <blockquote key={citation.section + citation.quote}>
          "{citation.quote}"
          <cite>
            Section {citation.section}, page {citation.page}
          </cite>
        </blockquote>
      ))}
      {incident && (
        <div className="incident">
          <h3>
            Incident, fault {incident.occurrences} at {incident.step_id}
          </h3>
          <ol>
            {incident.rework.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ol>
          <p>{incident.report}</p>
        </div>
      )}
    </section>
  );
}
