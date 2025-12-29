# Welcome to bltools

**Modern Async Downloader for British Library Manuscripts**

`bltools` is a high-performance Python CLI tool designed to download manuscript images from the British Library's viewer. It utilizes `asyncio` and `httpx` for fast, parallel downloading and `Typer` for a robust command-line interface.

## Key Features

- **Blazing Fast**: Uses `asyncio` + `httpx` to download tiles in parallel.
- **Robust**: Automatic retries with exponential backoff via `tenacity`.
- **Beautiful**: Rich terminal output with progress bars and spinners.
- **Developer Friendly**: Strictly typed, documented, and fully tested.

## Installation

Requires Python 3.9+.

### Using uv (Recommended)

```bash
uv tool install bltools
# or run directly
uv run bltools --help
```

### Using pip

```bash
pip install bltools
```

## Quick Start

Download pages 1 to 5 of a manuscript:

```bash
bltools download add_ms_19352 --range 1-5
```

Save to a specific directory:

```bash
bltools download add_ms_19352 --output ./downloads
```
