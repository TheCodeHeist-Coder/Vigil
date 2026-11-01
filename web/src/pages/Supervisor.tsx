import { useEffect, useState } from "react";
import { get, post, put, upload } from "../api";
import { Icon, type IconName } from "../components/Icon";
import type { Citation, Procedure, Status, Step } from "../types";

type Row = { at: string; serial: string; revision: string; step: string; reason: string; status: "confirmed" | "cleared" | "uncertain"; explanation: string; citations: Citation[]; model: string; latency_ms: number; source: string };
type IncidentRow = { at: string; serial: string; step: string; rework: string[]; report: string };
type Log = { verdicts: Row[]; incidents: IncidentRow[] };
type Results = { runs: number; verdicts: number; by_status: Record<string, number>; median_verdict_ms: number | null };
type Proposal = { procedure_id: number; pages: number; sections: number; leaves: number; procedure: { steps: Step[] } };
type Answer = { answer: string; citation: Citation | null };
type Tab = "results" | "ask" | "manual";

const TABS: { id: Tab; label: string; icon: IconName }[] = [
  { id: "results", label: "Results", icon: "supervisor" },
  { id: "ask", label: "Ask the manual", icon: "search" },
  { id: "manual", label: "Edit the manual", icon: "book" },
];

const RESULT = {
  confirmed: "Mistake",
  cleared: "Passed",
  uncertain: "Unsure",
};

const EXAMPLES = ["Which STM32 pin does SCL connect to?", "When can I plug in the USB cable?", "What if the same fault keeps happening?"];

function ResultsTab({ results, log }: { results: Results | null; log: Log }) {
  const cards = [
    { label: "Units run", value: results?.runs ?? 0 },
    { label: "Mistakes caught", value: results?.by_status.confirmed ?? 0 },
    { label: "Checks passed", value: results?.by_status.cleared ?? 0 },
    { label: "Needed a person", value: results?.by_status.uncertain ?? 0 },
    { label: "Typical check time", value: results?.median_verdict_ms ? `${(results.median_verdict_ms / 1000).toFixed(1)} s` : "–" },
  ];
  return (
    <>
      <div className="stats">
        {cards.map((card) => (
          <div key={card.label}>
            <b>{card.value}</b>
            <span>{card.label}</span>
          </div>
        ))}
      </div>
      <p className="muted note">Counts live Gemini checks only. Replays and local rules are left out.</p>

      {log.incidents.length > 0 && (
        <section className="card">
          <h2>Incidents</h2>
          <div className="incidents">
            {log.incidents.map((incident) => (
              <article key={incident.at}>
                <header>
                  <b>{incident.serial}</b>
                  <span className="pill">{incident.step}</span>
                </header>
                <p>{incident.report}</p>
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="card">
        <h2>Every check</h2>
        {log.verdicts.length === 0 ? (
          <p className="muted decision-empty">No checks yet. Run a unit on the Bench page and they will appear here.</p>
        ) : (
          <div className="table">
            <table>
              <thead>
                <tr>
                  <th>Unit</th>
                  <th>Step</th>
                  <th>Check</th>
                  <th>Result</th>
                  <th>Why</th>
                  <th>Time</th>
                </tr>
              </thead>
              <tbody>
                {log.verdicts.map((row) => (
                  <tr key={row.at + row.step}>
                    <td>
                      <b>{row.serial}</b>
                      <small>Rev {row.revision}</small>
                    </td>
                    <td>{row.step}</td>
                    <td>{row.reason === "out_of_sequence" ? "Order" : row.reason === "supervisor_release" ? "Release" : "Photo"}</td>
                    <td>
                      <span className={`pill ${row.status}`}>{RESULT[row.status]}</span>
                      {row.source === "replay" && <span className="replay-tag">REPLAY</span>}
                    </td>
                    <td>{row.explanation}</td>
                    <td>{row.latency_ms ? `${(row.latency_ms / 1000).toFixed(1)} s` : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

function AskTab() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [busy, setBusy] = useState(false);

  async function ask(text: string) {
    setQuestion(text);
    setBusy(true);
    setAnswer(null);
    try {
      setAnswer(await post<Answer>("/api/ask", { question: text }));
    } catch {
      setAnswer({ answer: "Vigil could not reach the manual. Try again.", citation: null });
    }
    setBusy(false);
  }

  return (
    <section className="card ask">
      <h2>Ask anything about the VDN-1 manual</h2>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void ask(question);
        }}
      >
        <input value={question} onChange={(e) => setQuestion(e.target.value)} placeholder="Type a question" aria-label="Question" />
        <button disabled={!question.trim() || busy}>Ask</button>
      </form>
      <div className="examples">
        {EXAMPLES.map((example) => (
          <button key={example} className="chip" onClick={() => void ask(example)}>
            {example}
          </button>
        ))}
      </div>
      {busy && (
        <p className="muted">
          <span className="spinner" />
          Searching the manual
        </p>
      )}
      {answer && (
        <div className="answer">
          <p>{answer.answer}</p>
          {answer.citation && (
            <blockquote>
              {answer.citation.quote && <span>{answer.citation.quote}</span>}
              <cite>
                Manual section {answer.citation.section}, page {answer.citation.page}
              </cite>
            </blockquote>
          )}
        </div>
      )}
    </section>
  );
}

function ManualTab() {
  const [manual, setManual] = useState("");
  const [current, setCurrent] = useState<Procedure | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [engineer, setEngineer] = useState("");
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [problem, setProblem] = useState("");

  const load = () => void get<Procedure>("/api/procedure").then(setCurrent);

  useEffect(() => {
    void get<{ text: string }>("/api/manual").then((m) => setManual(m.text));
    load();
  }, []);

  async function read() {
    setBusy(true);
    setNotice("");
    setProblem("");
    try {
      setProposal(await put<Proposal>("/api/manual", { text: manual }));
    } catch {
      setProblem("Vigil could not read the manual. Check it and try again.");
    }
    setBusy(false);
  }

  async function uploadFile(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setNotice("");
    setProblem("");
    setProposal(null);
    try {
      setProposal(await upload<Proposal>("/api/manual/upload", file));
      void get<{ text: string }>("/api/manual").then((m) => setManual(m.text));
    } catch (error) {
      setProblem(error instanceof Error ? error.message : "Vigil could not read that file.");
    }
    setBusy(false);
  }

  async function approve() {
    await post(`/api/procedures/${proposal!.procedure_id}/approve`, { engineer });
    setProposal(null);
    setNotice(`Approved by ${engineer}. New runs follow this procedure.`);
    load();
  }

  const changed = (step: Step) => {
    const before = current?.steps.find((s) => s.id === step.id);
    return !before || before.title !== step.title || before.bin !== step.bin || before.requires.join() !== step.requires.join();
  };

  return (
    <div className="manual-grid">
      <section className="card manual-edit">
        <h2>1. Give Vigil the manual</h2>
        <p className="muted">Upload a file, or edit the text below. Nothing changes on the bench until an engineer approves it.</p>
        <label className={`upload ${busy ? "busy" : ""}`}>
          <input type="file" accept=".pdf,.md,.txt" disabled={busy} onChange={(e) => void uploadFile(e.target.files?.[0])} />
          <Icon name="book" size={18} />
          <span>{busy ? "Reading the manual" : "Upload a PDF, Markdown or text file"}</span>
        </label>
        {problem && <p className="notice bad">{problem}</p>}
        <textarea value={manual} onChange={(e) => setManual(e.target.value)} aria-label="Manual text" />
        <button className="ghost" onClick={read} disabled={busy}>
          {busy ? "Reading the manual" : "Read the edited text"}
        </button>
      </section>

      <section className="card manual-review">
        <h2>2. Review and approve</h2>
        {notice && <p className="notice">{notice}</p>}
        {!proposal ? (
          <p className="muted">After Vigil reads a manual, its steps appear here for an engineer to approve.</p>
        ) : (
          <>
            <p className="muted">
              Vigil read {proposal.pages} pages. Changed steps are marked.
            </p>
            <ol className="proposal">
              {proposal.procedure.steps.map((step, i) => (
                <li key={step.id} className={changed(step) ? "changed" : ""}>
                  <span className="marker">{i + 1}</span>
                  <div>
                    <b>{step.title}</b>
                    <small>Bin {step.bin}</small>
                  </div>
                  {changed(step) && <span className="pill uncertain">Changed</span>}
                </li>
              ))}
            </ol>
            <label className="field">
              <span>Approving engineer</span>
              <input value={engineer} onChange={(e) => setEngineer(e.target.value)} placeholder="Full name" />
            </label>
            <button className="primary" disabled={!engineer.trim()} onClick={approve}>
              Approve for the bench
            </button>
          </>
        )}
      </section>
    </div>
  );
}

export function Supervisor(_: { status: Status | null }) {
  const [tab, setTab] = useState<Tab>("results");
  const [log, setLog] = useState<Log>({ verdicts: [], incidents: [] });
  const [results, setResults] = useState<Results | null>(null);

  useEffect(() => {
    const refresh = () => {
      void get<Log>("/api/log").then(setLog);
      void get<Results>("/api/results").then(setResults);
    };
    refresh();
    const timer = setInterval(refresh, 3000);
    return () => clearInterval(timer);
  }, []);

  return (
    <main className="page supervisor">
      <header className="page-head">
        <h1>Supervisor</h1>
        <p>See how the line is doing, look up the manual, and approve changes.</p>
      </header>

      <div className="tabs" role="tablist">
        {TABS.map((item) => (
          <button key={item.id} role="tab" aria-selected={tab === item.id} className={tab === item.id ? "on" : ""} onClick={() => setTab(item.id)}>
            <Icon name={item.icon} size={18} />
            {item.label}
          </button>
        ))}
      </div>

      {tab === "results" && <ResultsTab results={results} log={log} />}
      {tab === "ask" && <AskTab />}
      {tab === "manual" && <ManualTab />}
    </main>
  );
}
