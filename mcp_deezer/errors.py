"""Error surface: expected failures and safe, actionable messages.

Two rules:
* never leak the Deezer session cookie, whatever the upstream exception says;
* tell the agent what to *do* (refresh the ARL, retry later), not just what broke.
"""

from __future__ import annotations

import asyncio
import os
import re

# A Deezer ARL is a long hex string; redact by shape as well as by value so a
# future config (file, keyring) cannot leak through an exception we did not foresee.
_HEX_SECRET = re.compile(r"\b[0-9a-f]{96,}\b", re.IGNORECASE)
_BEARER = re.compile(r"(?i)(authorization:?\s*bearer\s+)\S+")
_ARL_PARAM = re.compile(r"(?i)\barl=([^\s&;\"']+)")


class ToolError(Exception):
    """An expected failure reported to the caller as a tool error (not a crash)."""


def redact(text: str) -> str:
    """Remove the ARL and anything shaped like a session credential."""
    arl = os.environ.get("DEEZER_ARL", "").strip()
    if arl:
        text = text.replace(arl, "[REDACTED]")
    text = _BEARER.sub(r"\1[REDACTED]", text)
    text = _ARL_PARAM.sub("arl=[REDACTED]", text)
    return _HEX_SECRET.sub("[REDACTED]", text)


def _hint(exc: BaseException) -> str | None:
    """Map known upstream failures to a next step the agent can act on."""
    # Imported lazily: keeps `tools/list` snappy and tolerates the client being absent.
    try:
        from deezer_python_gql import GraphQLClientAuthError, GraphQLClientHttpError
    except Exception:  # pragma: no cover - dependency is a hard requirement
        return None

    if isinstance(exc, GraphQLClientAuthError):
        return (
            "The Deezer session was rejected (ARL expired or invalid). Refresh it: "
            "deezer.com, F12, Application > Cookies, copy `arl`, update DEEZER_ARL, "
            "then restart the MCP client."
        )
    if isinstance(exc, GraphQLClientHttpError):
        status = getattr(exc, "status_code", 0)
        if status == 429:
            return "Deezer rate limit reached. Wait a few seconds before retrying."
        if status in (401, 403):
            return (
                "Deezer refused the request: the ARL is likely expired "
                "or this account lacks access."
            )
        if 500 <= status < 600:
            return f"Deezer API is unavailable (HTTP {status}). Retry in a moment."
    if isinstance(exc, asyncio.TimeoutError | TimeoutError):
        return "Deezer did not answer in time. Retry, or lower the batch size."
    return None


def error_text(exc: BaseException) -> str:
    """Format an exception for the MCP result body, redacted and with a next step."""
    message = redact(str(exc)).strip()
    hint = _hint(exc)
    if hint and message:
        return f"{message}\n\n{hint}"
    if hint:
        return hint
    return f"{type(exc).__name__}: {message}" if message else type(exc).__name__
