from __future__ import annotations

import pytest

from meraki_client.retry import RetryPolicy


class Error(Exception):
    def __init__(self, status_code):
        self.status_code = status_code


def test_retries_transient_error():
    attempts = 0
    sleeps = []

    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Error(429)
        return "ok"

    policy = RetryPolicy(
        max_retries=3,
        base_seconds=1,
        sleeper=sleeps.append,
        random_value=lambda: 0,
    )
    assert policy.run(operation) == "ok"
    assert attempts == 3
    assert sleeps == [1, 2]


def test_does_not_retry_permanent_error():
    policy = RetryPolicy(max_retries=3, sleeper=lambda _: None)
    with pytest.raises(Error):
        policy.run(lambda: (_ for _ in ()).throw(Error(400)))

