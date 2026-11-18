from __future__ import annotations

import asyncio

from deezer_python_gql import GQLResponse, GraphQLClientAuthError, GraphQLClientHttpError

from mcp_deezer import client as client_module
from mcp_deezer import config
from mcp_deezer.errors import ToolError, error_text, redact


def test_redact_removes_the_configured_arl(monkeypatch):
    secret = "f" * 192
    monkeypatch.setenv("DEEZER_ARL", secret)

    assert secret not in redact(f"boom {secret} boom")


def test_redact_removes_hex_shaped_secrets_and_bearer_tokens():
    hexish = "0123456789abcdef" * 10

    text = redact(f"cookie={hexish} Authorization: Bearer abc.def.ghi")

    assert hexish not in text
    assert "abc.def.ghi" not in text
    assert text.count("[REDACTED]") == 2


def test_redact_handles_an_arl_in_a_url_parameter():
    assert "secret" not in redact("GET /login?arl=secret&jo=p")


def test_auth_error_explains_how_to_refresh_the_arl():
    message = error_text(GraphQLClientAuthError("ARL authentication rejected (HTTP 401)"))

    assert "ARL" in message
    assert "deezer.com" in message


def test_rate_limit_and_server_errors_get_distinct_hints():
    rate_limited = GraphQLClientHttpError(
        status_code=429, response=GQLResponse(status=429, data=b"", is_success=False)
    )
    unavailable = GraphQLClientHttpError(
        status_code=503, response=GQLResponse(status=503, data=b"", is_success=False)
    )
    forbidden = GraphQLClientHttpError(
        status_code=403, response=GQLResponse(status=403, data=b"", is_success=False)
    )

    assert "rate limit" in error_text(rate_limited).lower()
    assert "unavailable" in error_text(unavailable).lower()
    assert "refused" in error_text(forbidden).lower()


def test_unknown_errors_keep_their_type():
    assert error_text(ValueError("boom")).startswith("ValueError: boom")


def test_reads_retry_transient_failures(monkeypatch):
    monkeypatch.setattr(client_module, "BASE_DELAY", 0.0)
    monkeypatch.setattr(client_module.random, "uniform", lambda _a, _b: 0.0)
    attempts: list[int] = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise _HttpError(429)
        return "ok"

    assert asyncio.run(client_module.call(flaky)) == "ok"
    assert len(attempts) == 3


def test_writes_are_not_retried_on_server_errors(monkeypatch):
    monkeypatch.setattr(client_module, "BASE_DELAY", 0.0)
    attempts: list[int] = []

    async def failing():
        attempts.append(1)
        raise _HttpError(500)

    try:
        asyncio.run(client_module.call(failing, write=True))
    except _HttpError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected the failure to propagate")

    assert len(attempts) == 1


def test_writes_retry_rate_limits(monkeypatch):
    monkeypatch.setattr(client_module, "BASE_DELAY", 0.0)
    monkeypatch.setattr(client_module.random, "uniform", lambda _a, _b: 0.0)
    attempts: list[int] = []

    async def rate_limited_then_ok():
        attempts.append(1)
        if len(attempts) < 2:
            raise _HttpError(429)
        return "ok"

    assert asyncio.run(client_module.call(rate_limited_then_ok, write=True)) == "ok"
    assert len(attempts) == 2


def test_tool_errors_are_never_retried():
    attempts: list[int] = []

    async def failing():
        attempts.append(1)
        raise ToolError("nope")

    try:
        asyncio.run(client_module.call(failing))
    except ToolError:
        pass
    else:  # pragma: no cover
        raise AssertionError("expected ToolError")

    assert len(attempts) == 1


def test_resolve_arl_prefers_the_environment(monkeypatch):
    monkeypatch.setenv("DEEZER_ARL", "env-arl")

    assert client_module.resolve_arl() == "env-arl"


def test_resolve_arl_reads_the_file(monkeypatch, tmp_path):
    cookie = tmp_path / "arl"
    cookie.write_text("file-arl\n", encoding="utf-8")
    monkeypatch.delenv("DEEZER_ARL", raising=False)
    monkeypatch.setenv("DEEZER_ARL_FILE", str(cookie))

    assert client_module.resolve_arl() == "file-arl"


def test_resolve_arl_explains_how_to_get_one(monkeypatch):
    monkeypatch.delenv("DEEZER_ARL", raising=False)

    try:
        client_module.resolve_arl()
    except ToolError as exc:
        assert "DEEZER_ARL" in str(exc)
        assert "deezer.com" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ToolError")


def test_close_client_is_idempotent():
    asyncio.run(client_module.close_client())
    asyncio.run(client_module.close_client())


def test_clamp_limit_bounds_values():
    assert config.clamp_limit(0) == 1
    assert config.clamp_limit(-5) == 1
    assert config.clamp_limit(999) == config.MAX_LIMIT
    assert config.clamp_limit(None) == config.DEFAULT_LIMIT
    assert config.clamp_limit("7") == 7
    assert config.clamp_limit("abc") == config.DEFAULT_LIMIT


def test_timeout_and_flags_are_validated(monkeypatch):
    monkeypatch.setenv("DEEZER_TIMEOUT", "5")
    assert config.timeout_seconds() == 5.0

    monkeypatch.setenv("DEEZER_TIMEOUT", "nonsense")
    assert config.timeout_seconds() == 30.0

    monkeypatch.setenv("DEEZER_TIMEOUT", "99999")
    assert config.timeout_seconds() == 30.0

    monkeypatch.setenv("DEEZER_LOG_LEVEL", "debug")
    assert config.log_level() == "DEBUG"

    monkeypatch.setenv("DEEZER_LOG_LEVEL", "chatty")
    assert config.log_level() == "WARNING"


def test_read_only_flag_accepts_common_truthy_values(monkeypatch):
    for value in ("1", "true", "YES", "on"):
        monkeypatch.setenv("DEEZER_READ_ONLY", value)
        assert config.read_only() is True

    monkeypatch.setenv("DEEZER_READ_ONLY", "0")
    assert config.read_only() is False


class _HttpError(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(f"HTTP {status}")
        self.status_code = status
