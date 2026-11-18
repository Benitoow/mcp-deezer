"""Runtime configuration, resolved from the environment on each access.

Kept as functions (not module constants) so tests can monkeypatch the environment
without reloading the module, and so ``--help``-style imports stay side-effect free.
"""

from __future__ import annotations

import os

# Bounds shared by the JSON Schemas and the handlers: a schema that advertises
# ``maximum: 100`` but a handler that clamps at 50 is a lying contract.
DEFAULT_LIMIT = 20
MAX_LIMIT = 100
WRITE_BATCH = 50
READ_ONLY_ENV = "DEEZER_READ_ONLY"

_MISSING_ARL = (
    "DEEZER_ARL is not set. Get your ARL cookie:\n"
    "1. Log into deezer.com, press F12, open Application > Cookies > 'arl'\n"
    "2. Set DEEZER_ARL (or DEEZER_ARL_FILE=/path/to/arl) and restart the MCP client."
)


def missing_arl_message() -> str:
    return _MISSING_ARL


def env_flag(name: str) -> bool:
    """Truthy for 1/true/yes/on, falsy for anything else (including unset)."""
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes", "on"}


def read_only() -> bool:
    """When set, write tools are neither listed nor callable."""
    return env_flag(READ_ONLY_ENV)


def timeout_seconds() -> float:
    raw = os.environ.get("DEEZER_TIMEOUT", "").strip()
    try:
        value = float(raw) if raw else 30.0
    except ValueError:
        value = 30.0
    return value if 1.0 <= value <= 300.0 else 30.0


def log_level() -> str:
    raw = os.environ.get("DEEZER_LOG_LEVEL", "").strip().upper()
    return raw if raw in {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"} else "WARNING"


def clamp_limit(value: object, default: int = DEFAULT_LIMIT) -> int:
    """Coerce a caller-supplied limit into ``1..MAX_LIMIT``."""
    if isinstance(value, bool):
        return default
    if isinstance(value, int | float):
        number = int(value)
    elif isinstance(value, str):
        try:
            number = int(value.strip())
        except ValueError:
            return default
    else:
        return default
    return max(1, min(number, MAX_LIMIT))
