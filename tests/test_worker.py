"""Test worker backoff calculation."""


from async_jobs.worker import calculate_backoff_seconds


def test_exponential_backoff():
    """Test exponential backoff calculation."""
    policy = {"type": "exponential", "base_delay_seconds": 60, "max_delay_seconds": 3600}

    assert calculate_backoff_seconds(policy, 1) == 60  # 60 * 2^0
    assert calculate_backoff_seconds(policy, 2) == 120  # 60 * 2^1
    assert calculate_backoff_seconds(policy, 3) == 240  # 60 * 2^2
    assert calculate_backoff_seconds(policy, 4) == 480  # 60 * 2^3
    assert calculate_backoff_seconds(policy, 5) == 960  # 60 * 2^4
    assert calculate_backoff_seconds(policy, 6) == 1920  # 60 * 2^5
    assert calculate_backoff_seconds(policy, 7) == 3600  # capped at max


def test_linear_backoff():
    """Test linear backoff calculation."""
    policy = {"type": "linear", "base_delay_seconds": 60, "max_delay_seconds": 300}

    assert calculate_backoff_seconds(policy, 1) == 60  # 60 * 1
    assert calculate_backoff_seconds(policy, 2) == 120  # 60 * 2
    assert calculate_backoff_seconds(policy, 3) == 180  # 60 * 3
    assert calculate_backoff_seconds(policy, 4) == 240  # 60 * 4
    assert calculate_backoff_seconds(policy, 5) == 300  # capped at max


def test_constant_backoff():
    """Test constant backoff calculation."""
    policy = {"type": "constant", "base_delay_seconds": 120, "max_delay_seconds": 3600}

    assert calculate_backoff_seconds(policy, 1) == 120
    assert calculate_backoff_seconds(policy, 2) == 120
    assert calculate_backoff_seconds(policy, 3) == 120
    assert calculate_backoff_seconds(policy, 10) == 120


def test_unknown_backoff_type():
    """Test unknown backoff type defaults to base delay."""
    policy = {"type": "unknown", "base_delay_seconds": 100, "max_delay_seconds": 1000}

    assert calculate_backoff_seconds(policy, 1) == 100
    assert calculate_backoff_seconds(policy, 5) == 100


def test_backoff_respects_max():
    """Test that backoff is capped at max_delay_seconds."""
    policy = {"type": "exponential", "base_delay_seconds": 10, "max_delay_seconds": 100}

    # 10 * 2^9 = 5120, but should be capped at 100
    assert calculate_backoff_seconds(policy, 10) == 100
