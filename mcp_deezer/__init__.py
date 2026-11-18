"""Unofficial MCP server for Deezer, authenticated with an ARL session cookie."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:  # installed distribution: single source of truth is pyproject.toml
    __version__ = version("mcp-deezer")
except PackageNotFoundError:  # running from a source tree without installation
    __version__ = "2.0.0"

__all__ = ["__version__"]
