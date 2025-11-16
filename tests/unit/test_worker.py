"""Unit tests for worker backoff calculation."""


from async_jobs.worker import _calculate_backoff


def test_exponential_backoff():
    """Test exponential backoff calculation."""
    policy = {"type": "exponential", "base_seconds": 10}

    # 10 * 2^0 = 10
    assert _calculate_backoff(policy, 1) == 10
    # 10 * 2^1 = 20
    assert _calculate_backoff(policy, 2) == 20
    # 10 * 2^2 = 40
    assert _calculate_backoff(policy, 3) == 40
    # 10 * 2^3 = 80
    assert _calculate_backoff(policy, 4) == 80


def test_exponential_backoff_cap():
    """Test that exponential backoff is capped at 1 hour."""
    policy = {"type": "exponential", "base_seconds": 1000}

    # Should be capped at 3600
    assert _calculate_backoff(policy, 10) == 3600


def test_linear_backoff():
    """Test linear backoff calculation."""
    policy = {"type": "linear", "base_seconds": 30}

    assert _calculate_backoff(policy, 1) == 30
    assert _calculate_backoff(policy, 2) == 60
    assert _calculate_backoff(policy, 3) == 90
    assert _calculate_backoff(policy, 4) == 120


def test_linear_backoff_cap():
    """Test that linear backoff is capped at 1 hour."""
    policy = {"type": "linear", "base_seconds": 2000}

    assert _calculate_backoff(policy, 3) == 3600


def test_constant_backoff():
    """Test constant backoff."""
    policy = {"type": "constant", "base_seconds": 60}

    assert _calculate_backoff(policy, 1) == 60
    assert _calculate_backoff(policy, 2) == 60
    assert _calculate_backoff(policy, 5) == 60


def test_unknown_backoff_type_defaults_to_exponential():
    """Test that unknown backoff types default to exponential."""
    policy = {"type": "unknown", "base_seconds": 10}

    # Should use exponential as default
    assert _calculate_backoff(policy, 1) == 10
    assert _calculate_backoff(policy, 2) == 20


def test_default_base_seconds():
    """Test default base_seconds when not provided."""
    policy = {"type": "exponential"}

    # Default base_seconds is 10
    assert _calculate_backoff(policy, 1) == 10
