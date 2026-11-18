from __future__ import annotations

import pytest

from mcp_deezer import tools_read, tools_write  # noqa: F401  (importing them fills the registry)
from tests.fakes import FakeClient


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """Every test starts without behaviour flags, but with a plausible ARL."""
    for name in (
        "DEEZER_ARL",
        "DEEZER_ARL_FILE",
        "DEEZER_READ_ONLY",
        "DEEZER_TIMEOUT",
        "DEEZER_LOG_LEVEL",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("DEEZER_ARL", "0" * 192)
    yield


@pytest.fixture
def fake_client() -> FakeClient:
    return FakeClient()
