CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS documents (
  id bigserial PRIMARY KEY,
  title text NOT NULL,
  revision text NOT NULL,
  pages int,
  sha256 text NOT NULL,
  created_at timestamptz DEFAULT now()
);

-- level is 'section' or 'leaf'. A leaf's parent_id points at its section.
CREATE TABLE IF NOT EXISTS chunks (
  id bigserial PRIMARY KEY,
  doc_id bigint REFERENCES documents,
  level text NOT NULL,
  parent_id bigint,
  path text[] NOT NULL,
  section text NOT NULL,
  page int NOT NULL,
  step_id text,
  body text NOT NULL,
  embedding vector(768)
);
CREATE INDEX NONCONCURRENTLY IF NOT EXISTS chunks_hnsw ON chunks USING ybhnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS procedures (
  id bigserial PRIMARY KEY,
  doc_id bigint REFERENCES documents,
  body jsonb NOT NULL,
  approved_by text,
  approved_at timestamptz
);

CREATE TABLE IF NOT EXISTS runs (
  id uuid PRIMARY KEY,
  serial text NOT NULL,
  revision text NOT NULL,
  status text NOT NULL DEFAULT 'running',
  started_at timestamptz DEFAULT now(),
  ended_at timestamptz
);

CREATE TABLE IF NOT EXISTS verdicts (
  flag_id uuid PRIMARY KEY,
  run_id uuid REFERENCES runs,
  step_id text,
  reason text,
  status text NOT NULL,
  explanation text,
  citations jsonb,
  model text,
  latency_ms int,
  hops jsonb,
  source text,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS incidents (
  id uuid PRIMARY KEY,
  run_id uuid REFERENCES runs,
  step_id text,
  rework text[],
  report text,
  created_at timestamptz DEFAULT now()
);

-- Agent memory when no Meko key is set.
CREATE TABLE IF NOT EXISTS agent_memory (
  id bigserial PRIMARY KEY,
  step_id text,
  note text NOT NULL,
  created_at timestamptz DEFAULT now()
);
