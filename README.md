# bltools

**Modern Async Downloader# British Library Tools (bltools)

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://github.com/artbitrage/bltools/actions/workflows/ci.yml/badge.svg)](https://github.com/artbitrage/bltools/actions/workflows/ci.yml)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://img.shields.io/badge/mypy-checked-blue.svg)](http://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A modern, asynchronous CLI tool for downloading high-resolution manuscripts from the British Library. Now with full **IIIF (International Image Interoperability Framework)** support.

## Features
- **Modern Architecture**: Built with Typer, Pydantic (settings & models), and HTTPX.
- **IIIF Support**: Support for modern IIIF Collection/Manifest URLs.
- **Asynchronous**: Concurrent downloads with `asyncio` and `httpx`.
- **Robust**: Automatic retries with exponential backoff via `tenacity`.
- **Rich UI**: Interactive progress bars and beautiful logging via `rich` and `structlog`.
- **12-Factor Compliant**: Configuration via environment variables.

## Installation

```bash
uv tool install bltools
# or run directly
uv run bltools --help
```

### Using pip

```bash
pip install .
```

## Usage

The basic command to download a manuscript:

```bash
bltools download add_ms_19352
```

### Options

- `--config, -c`: Path to custom config file (default: `bl.conf`)
- `--output, -o`: Override output directory (default: current directory or config setting)
- `--range, -r`: Specify a page range (e.g., `1-10`)

### Examples

**Download pages 1 to 5 of a manuscript:**

```bash
bltools download add_ms_19352 --range 1-5
```

**Save to a specific directory:**

```bash
bltools download add_ms_19352 --output ./downloads
```

## Configuration

You can use a `bl.conf` YAML file to set defaults:

```yaml
sleeptime: 0.0
basedir: "."
rangebegin: 1
rangeend: 259
baseurl: "http://www.bl.uk/manuscripts/Proxy.ashx?view="
```

## Development

This project uses `hatchling` and `uv`.

1.  **Clone the repo**
2.  **Install dependencies**: `uv sync`
3.  **Run tests**: `uv run pytest`
4.  **Lint**: `uv run ruff check .`
