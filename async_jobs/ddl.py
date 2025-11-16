"""Database DDL for the jobs table."""

JOBS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS jobs (
  id               UUID PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  use_case         TEXT NOT NULL,
  type             TEXT NOT NULL,
  queue            TEXT NOT NULL,

  status           TEXT NOT NULL,      -- "pending", "running", "succeeded", "dead", "cancelled"
  payload          JSONB NOT NULL,

  run_at           TIMESTAMPTZ NOT NULL,
  delay_tolerance  INTERVAL NOT NULL,
  deadline_at      TIMESTAMPTZ NOT NULL,

  priority         INT NOT NULL DEFAULT 0,

  attempts         INT NOT NULL DEFAULT 0,
  max_attempts     INT NOT NULL,
  backoff_policy   JSONB NOT NULL,

  lease_expires_at TIMESTAMPTZ,
  last_error       JSONB,
  dedupe_key       TEXT,

  enqueue_failed   BOOLEAN NOT NULL DEFAULT FALSE,

  created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_pending_deadline
ON jobs (deadline_at)
WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status
ON jobs (tenant_id, status);

CREATE INDEX IF NOT EXISTS idx_jobs_use_case_status
ON jobs (use_case, status);
"""
