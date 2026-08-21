# Changelog

All notable changes to this project will be documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Changed

- Migrated the server to the MCP Python SDK 2.x low-level handler API.
- Added explicit JSON Schema validation and structured tool results.
- Added automated tests on Python 3.12 and 3.13 for Windows and Linux.
- Added verified wheel and source-distribution builds for releases.

### Fixed

- Prevented fresh installations from crashing after the MCP Python SDK 2.0 release.
- Redacted the Deezer ARL cookie if an upstream exception includes it.
- Fixed nested list navigation used by response formatters.
- Made the discovery smoke test safe for legacy Windows console encodings.
