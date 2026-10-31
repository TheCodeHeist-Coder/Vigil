export type Point = [number, number];

export type Zone = { id: string; label: string; kind: "bin" | "tray"; polygon: Point[] };

export type Step = { id: string; section: string; title: string; bin: string; requires: string[]; check: string; correction: string; clip: string };

export type Procedure = { id: number; doc_id: number; revision: string; steps: Step[] };

export type Times = Record<string, number>;

export type HandTrack = { bench: string; hands: Point[]; pinch: Point | null; skeleton: Point[]; source: string; times: Times };

export type ReflexAlert = { id: string; flag_id: string; step_id: string; text: string; clip: string; times: Times };

export type Citation = { section: string; page: number; quote: string };

export type Verdict = {
  flag_id: string;
  step_id: string;
  reason: string;
  status: "confirmed" | "cleared" | "uncertain";
  explanation: string;
  citations: Citation[];
  spoken: string | null;
  model: string;
  latency_ms: number;
  source: "live" | "replay";
  times: Times;
};

export type Incident = { id: string; step_id: string; rework: string[]; report: string; occurrences: number; memory_backend: string };

export type RunState = { run_id: string; serial: string; revision: "A" | "B"; done: string[]; waived: string[]; active: string | null; held: boolean; finished: boolean };

export type Status = {
  model: string;
  embedder: string;
  database: string;
  documents: number;
  meko: { state: string; detail: string };
  replay: boolean;
  camera_live: boolean;
};
