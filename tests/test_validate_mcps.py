import pytest
from scripts.validate_mcps import validate


def raises(exc):
    def _raise():
        raise exc
    return _raise


def test_validate_returns_ok_when_both_succeed():
    result = validate(
        dt_checker=lambda: None,
        gl_checker=lambda: None,
    )
    assert result == {"dynatrace": "ok", "gitlab": "ok"}


def test_validate_captures_dynatrace_error():
    result = validate(
        dt_checker=raises(ConnectionError("timeout")),
        gl_checker=lambda: None,
    )
    assert result["dynatrace"] == "timeout"
    assert result["gitlab"] == "ok"


def test_validate_captures_gitlab_error():
    result = validate(
        dt_checker=lambda: None,
        gl_checker=raises(ConnectionError("401 Unauthorized")),
    )
    assert result["dynatrace"] == "ok"
    assert result["gitlab"] == "401 Unauthorized"


def test_validate_both_errors_are_independent():
    result = validate(
        dt_checker=raises(Exception("dt error")),
        gl_checker=raises(Exception("gl error")),
    )
    assert result["dynatrace"] == "dt error"
    assert result["gitlab"] == "gl error"
