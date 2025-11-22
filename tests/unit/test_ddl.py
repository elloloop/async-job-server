"""Unit tests for DDL module."""

from async_jobs.ddl import JOBS_TABLE_DDL


def test_jobs_table_ddl_exists():
    """Test that JOBS_TABLE_DDL is defined."""
    assert JOBS_TABLE_DDL is not None
    assert isinstance(JOBS_TABLE_DDL, str)
    assert len(JOBS_TABLE_DDL) > 0


def test_jobs_table_ddl_contains_create_table():
    """Test that DDL contains CREATE TABLE statement."""
    assert "CREATE TABLE jobs" in JOBS_TABLE_DDL


def test_jobs_table_ddl_contains_required_columns():
    """Test that DDL contains all required columns."""
    required_columns = [
        "id",
        "tenant_id",
        "use_case",
        "type",
        "queue",
        "status",
        "payload",
        "run_at",
        "delay_tolerance",
        "deadline_at",
        "priority",
        "attempts",
        "max_attempts",
        "backoff_policy",
        "lease_expires_at",
        "last_error",
        "dedupe_key",
        "enqueue_failed",
        "created_at",
        "updated_at",
    ]

    for column in required_columns:
        assert column in JOBS_TABLE_DDL, f"Column {column} not found in DDL"


def test_jobs_table_ddl_contains_indexes():
    """Test that DDL contains index definitions."""
    assert "CREATE INDEX idx_jobs_pending_deadline" in JOBS_TABLE_DDL
    assert "CREATE INDEX idx_jobs_tenant_status" in JOBS_TABLE_DDL
    assert "CREATE INDEX idx_jobs_use_case_status" in JOBS_TABLE_DDL


def test_jobs_table_ddl_types():
    """Test that DDL contains correct data types."""
    assert "UUID" in JOBS_TABLE_DDL
    assert "TEXT" in JOBS_TABLE_DDL
    assert "JSONB" in JOBS_TABLE_DDL
    assert "TIMESTAMPTZ" in JOBS_TABLE_DDL
    assert "INTERVAL" in JOBS_TABLE_DDL
    assert "INT" in JOBS_TABLE_DDL
    assert "BOOLEAN" in JOBS_TABLE_DDL
