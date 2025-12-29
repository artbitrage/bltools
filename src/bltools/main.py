import asyncio
from pathlib import Path
from typing import Optional

import structlog
import typer
from rich.console import Console

from bltools.core import download_manuscript
from bltools.settings import get_settings

app = typer.Typer(
    help="British Library Manuscript Downloader",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main() -> None:
    """British Library Manuscript Downloader CLI."""
    pass


@app.command()
def download(
    input_str: str = typer.Argument(
        ..., help="Manuscript ID (e.g., add_ms_19352) or IIIF Manifest URL"
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Directory to save downloads"
    ),
    range: Optional[str] = typer.Option(
        None, "--range", help="Page range to download (e.g., 1-10)"
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable debug logging"),
) -> None:
    """
    Download a manuscript from the British Library.

    Supports legacy Manuscript IDs (tiled downloads) and modern IIIF Manifest URLs
    (direct high-resolution downloads).

    Args:
        input_str: Manuscript ID or IIIF Manifest URL.
        output: Optional override for the output directory.
        range: Optional page range (e.g., 1-10).
        verbose: Enable debug-level logging.
    """
    settings = get_settings()

    if verbose:
        structlog.configure(wrapper_class=structlog.make_filtering_bound_logger(20))

    if output:
        settings.basedir = output

    try:
        asyncio.run(download_manuscript(input_str, settings, console, range))
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        if verbose:
            raise e
        raise typer.Exit(code=1) from None


if __name__ == "__main__":
    app()
