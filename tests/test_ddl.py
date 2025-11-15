"""Test DDL."""

from async_jobs.ddl import get_ddl


def test_get_ddl():
    """Test getting DDL returns valid SQL."""
    ddl = get_ddl()
    assert ddl is not None
    assert isinstance(ddl, str)
    assert "CREATE TABLE IF NOT EXISTS jobs" in ddl
    assert "id" in ddl
    assert "tenant_id" in ddl
    assert "use_case" in ddl
    assert "status" in ddl
    assert "payload" in ddl
    assert "deadline_at" in ddl


def test_ddl_has_indexes():
    """Test DDL includes necessary indexes."""
    ddl = get_ddl()
    assert "idx_jobs_pending_deadline" in ddl
    assert "idx_jobs_tenant_status" in ddl
    assert "idx_jobs_use_case_status" in ddl
    assert "idx_jobs_dedupe_key" in ddl


def test_ddl_has_all_fields():
    """Test DDL includes all required fields."""
    ddl = get_ddl()
    required_fields = [
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
    for field in required_fields:
        assert field in ddl, f"Field {field} not found in DDL"
