import { useEffect, useState } from "react";
import { get, post, put } from "../api";
import type { Citation, Incident, Status, Step } from "../types";

type Row = { at: string; serial: string; revision: string; step: string; reason: string; status: string; explanation: string; citations: Citation[]; model: string; latency_ms: number; source: string };
type Log = { verdicts: Row[]; incidents: (Incident & { at: string; serial: string; step: string })[] };
type Results = { runs: number; verdicts: number; by_status: Record<string, number>; median_verdict_ms: number | null };
type Proposal = { procedure_id: number; pages: number; sections: number; leaves: number; embedder: string; procedure: { steps: Step[] } };
type Answer = { answer: string; citation: Citation | null };

export function Supervisor() {
  const [status, setStatus] = useState<Status | null>(null);
  const [log, setLog] = useState<Log>({ verdicts: [], incidents: [] });
  const [results, setResults] = useState<Results | null>(null);
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [manual, setManual] = useState("");
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [engineer, setEngineer] = useState("");
  const [busy, setBusy] = useState("");

  useEffect(() => {
    void get<{ text: string }>("/api/manual").then((m) => setManual(m.text));
    const refresh = () => {
      void get<Status>("/api/status").then(setStatus);
      void get<Log>("/api/log").then(setLog);
      void get<Results>("/api/results").then(setResults);
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, []);

  async function ask() {
    setBusy("Searching the manual");
    setAnswer(await post<Answer>("/api/ask", { question }));
    setBusy("");
  }

  async function ingest() {
    setBusy("Reading the manual");
    setProposal(await put<Proposal>("/api/manual", { text: manual }));
    setBusy("");
  }

  async function approve() {
    await post(`/api/procedures/${proposal!.procedure_id}/approve`, { engineer });
    setProposal(null);
  }

  return (
    <main className="supervisor">
      <h1>Supervisor</h1>
      <div className="stats">
        <div>
          <b>{results?.runs ?? "-"}</b>
          <span>Runs</span>
        </div>
        <div>
          <b>{results?.verdicts ?? "-"}</b>
          <span>Gemini verdicts</span>
        </div>
        <div>
          <b>{results?.by_status.confirmed ?? 0}</b>
          <span>Faults confirmed</span>
        </div>
        <div>
          <b>{results?.median_verdict_ms ? `${results.median_verdict_ms} ms` : "-"}</b>
          <span>Median verdict</span>
        </div>
        <div>
          <b>{status?.meko.state === "connected" ? "Meko" : "YugabyteDB"}</b>
          <span title={status?.meko.detail}>Agent memory</span>
        </div>
      </div>

      <div className="grid">
        <section className="card">
          <h2>Ask the manual</h2>
          <form
            className="row"
            onSubmit={(e) => {
              e.preventDefault();
              void ask();
            }}
          >
            <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="What torque for the M3 cover screw?" aria-label="Question" />
            <button disabled={!question}>Ask</button>
          </form>
          {answer && (
            <div className="answer">
              <p>{answer.answer}</p>
              {answer.citation && (
                <cite>
                  Section {answer.citation.section}, page {answer.citation.page}
                </cite>
              )}
            </div>
          )}

          <h2>Incidents</h2>
          {log.incidents.length === 0 && <p className="quiet">No incidents yet.</p>}
          {log.incidents.map((incident) => (
            <article key={incident.at} className="incident">
              <h3>
                {incident.serial}, {incident.step}
              </h3>
              <p>{incident.report}</p>
            </article>
          ))}
        </section>

        <section className="card">
          <h2>Manual</h2>
          <textarea value={manual} onChange={(e) => setManual(e.target.value)} aria-label="Manual text" />
          <button onClick={ingest}>Re-ingest manual</button>
          {busy && <p className="quiet">{busy}</p>}
          {proposal && (
            <div className="proposal">
              <p>
                Proposed from {proposal.pages} pages, {proposal.sections} sections, {proposal.leaves} chunks. Nothing changes until an engineer approves.
              </p>
              <ol>
                {proposal.procedure.steps.map((step) => (
                  <li key={step.id}>
                    {step.id}: {step.title} (bin {step.bin})
                  </li>
                ))}
              </ol>
              <div className="row">
                <input value={engineer} onChange={(e) => setEngineer(e.target.value)} placeholder="Engineer name" aria-label="Engineer name" />
                <button disabled={!engineer.trim()} onClick={approve}>
                  Approve
                </button>
              </div>
            </div>
          )}
        </section>
      </div>

      <section className="card">
        <h2>Verdict log</h2>
        <div className="table">
          <table>
            <thead>
              <tr>
                <th>Unit</th>
                <th>Rev</th>
                <th>Step</th>
                <th>Type</th>
                <th>Result</th>
                <th>Why</th>
                <th>Source</th>
                <th>Time</th>
              </tr>
            </thead>
            <tbody>
              {log.verdicts.map((row) => (
                <tr key={row.at + row.step}>
                  <td>{row.serial}</td>
                  <td>{row.revision}</td>
                  <td>{row.step}</td>
                  <td>{row.reason === "out_of_sequence" ? "Sequence" : "Photo check"}</td>
                  <td className={row.status}>{row.status}</td>
                  <td>{row.explanation}</td>
                  <td>{row.source === "replay" ? "REPLAY" : row.model}</td>
                  <td>{row.latency_ms} ms</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
