"""Deezer client lifecycle and the retry policy.

The client is created lazily (so ``tools/list`` answers without credentials) and
closed by the server lifespan. All upstream calls go through :func:`call`, which
adds bounded retries for transient failures and never retries a write that might
have been applied.
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any, TypeVar

from .config import missing_arl_message, timeout_seconds
from .errors import ToolError

logger = logging.getLogger("mcp_deezer.client")

T = TypeVar("T")

_client: Any = None
_session: Any = None
_lock = asyncio.Lock()

READ_ATTEMPTS = 3
WRITE_ATTEMPTS = 2  # only 429 is retried for writes: the request was not processed
BASE_DELAY = 0.4


def resolve_arl() -> str:
    """Read the ARL from ``DEEZER_ARL`` or from the file named by ``DEEZER_ARL_FILE``."""
    arl = os.environ.get("DEEZER_ARL", "").strip()
    if not arl:
        path = os.environ.get("DEEZER_ARL_FILE", "").strip()
        if path:
            cookie_file = Path(path).expanduser()
            try:
                arl = cookie_file.read_text(encoding="utf-8").strip()
            except OSError as exc:
                raise ToolError(f"Cannot read DEEZER_ARL_FILE ({cookie_file}): {exc}") from exc
            if os.name == "posix" and cookie_file.stat().st_mode & 0o077:
                logger.warning("%s is readable by other users; chmod 600 it", cookie_file)
    if not arl:
        raise ToolError(missing_arl_message())
    return arl


def _build_session(timeout: float) -> Any:
    """Create the HTTP session we own (and therefore must close)."""
    import aiohttp

    return aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=timeout),
        connector=aiohttp.TCPConnector(limit=4),
    )


async def get_client() -> Any:
    """Return the shared client, creating it once even under concurrent calls."""
    global _client, _session
    if _client is not None:
        return _client
    async with _lock:
        if _client is None:
            from deezer_python_gql import DeezerGQLClient

            arl = resolve_arl()
            _session = _build_session(timeout_seconds())
            _client = DeezerGQLClient(arl=arl, session=_session)
            logger.debug("Deezer client created (timeout=%ss)", timeout_seconds())
    return _client


async def close_client() -> None:
    """Close the HTTP session; safe to call twice and when nothing was created."""
    global _client, _session
    client, _client = _client, None
    session, _session = _session, None
    if client is not None:
        try:
            await client.close()  # no-op for an external session, kept for future versions
        except Exception:  # pragma: no cover - best effort on shutdown
            logger.debug("client.close() failed", exc_info=True)
    if session is not None:
        try:
            await session.close()
        except Exception:  # pragma: no cover
            logger.debug("session.close() failed", exc_info=True)


def _status_of(exc: BaseException) -> int | None:
    status = getattr(exc, "status_code", None)
    return status if isinstance(status, int) else None


def _is_transient(exc: BaseException, *, attempt: int, attempts: int, write: bool) -> bool:
    if attempt >= attempts or isinstance(exc, ToolError):
        return False
    status = _status_of(exc)
    if status is not None:
        if status == 429:
            return True
        # A write may already have been applied: only retry when we know it was rejected.
        return not write and 500 <= status < 600
    try:
        import aiohttp
    except Exception:  # pragma: no cover
        return False
    return not write and isinstance(exc, (aiohttp.ClientError, asyncio.TimeoutError))


async def call[T](
    fn: Callable[..., Awaitable[T]],
    /,
    *args: Any,
    write: bool = False,
    **kwargs: Any,
) -> T:
    """Await ``fn`` with bounded exponential backoff on transient failures."""
    attempts = WRITE_ATTEMPTS if write else READ_ATTEMPTS
    for attempt in range(1, attempts + 1):
        try:
            return await fn(*args, **kwargs)
        except Exception as exc:
            if not _is_transient(exc, attempt=attempt, attempts=attempts, write=write):
                raise
            delay = BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, BASE_DELAY)
            logger.warning(
                "transient Deezer failure (%s), retry %d/%d in %.1fs",
                type(exc).__name__,
                attempt,
                attempts - 1,
                delay,
            )
            await asyncio.sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
