# bltools

**Modern Async Downloader for British Library Manuscripts**

`bltools` is a high-performance Python CLI tool designed to download manuscript images from the British Library's viewer. It utilizes `asyncio` and `httpx` for fast, parallel downloading and `Typer` for a robust command-line interface.

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
