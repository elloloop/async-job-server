"""Database schema DDL for async jobs."""

JOBS_TABLE_DDL = """
CREATE TABLE jobs (
  id               UUID PRIMARY KEY,
  tenant_id        TEXT NOT NULL,
  use_case         TEXT NOT NULL,
  type             TEXT NOT NULL,
  queue            TEXT NOT NULL,

  status           TEXT NOT NULL CHECK (status IN ('pending', 'running', 'succeeded', 'dead', 'cancelled')),
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

CREATE INDEX idx_jobs_pending_deadline
ON jobs (deadline_at)
WHERE status = 'pending';

CREATE INDEX idx_jobs_tenant_status
ON jobs (tenant_id, status);

CREATE INDEX idx_jobs_use_case_status
ON jobs (use_case, status);

-- Composite index for quota queries
CREATE INDEX idx_jobs_tenant_use_case_status
ON jobs (tenant_id, use_case, status);

-- Index for lease reaper to find expired leases efficiently
CREATE INDEX idx_jobs_expired_leases
ON jobs (lease_expires_at)
WHERE status = 'running' AND lease_expires_at IS NOT NULL;
"""
