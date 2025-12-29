import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from bltools.core import download_manuscript
from bltools.logging_config import configure_logging
from bltools.settings import get_settings

app = typer.Typer(
    help="British Library Manuscript Downloader",
    no_args_is_help=True,
    invoke_without_command=True,
)
console = Console()


@app.callback()
def main() -> None:
    """British Library Manuscript Downloader CLI."""
    pass


@app.command()
def download(
    manuscript_id: str = typer.Argument(
        ..., help="The manuscript ID (e.g., add_ms_19352)"
    ),
    config_path: Optional[Path] = typer.Option(
        None,
        "--config",
        "-c",
        help="(Deprecated) Path to config file. Use .env instead.",
    ),
    output_dir: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Override output directory"
    ),
    page_range: Optional[str] = typer.Option(
        None, "--range", "-r", help="Page range (e.g., 1-10)"
    ),
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging"
    ),
) -> None:
    """
    Download a manuscript from the British Library.
    """
    configure_logging(verbose=verbose)

    settings = get_settings()

    if config_path:
        console.print(
            "[yellow]Warning: --config is deprecated. Please use .env file or environment variables.[/yellow]"
        )

    # Overrides
    if output_dir:
        settings.basedir = output_dir

    start, end = settings.rangebegin, settings.rangeend
    if page_range:
        try:
            s, e = page_range.split("-")
            start, end = int(s), int(e)
        except ValueError:
            console.print("[red]Invalid range format. Use start-end (e.g., 1-10)[/red]")
            raise typer.Exit(code=1) from None

    console.print(f"[bold green]Starting download for {manuscript_id}[/bold green]")
    console.print(f"Pages: {start} to {end}")

    asyncio.run(download_manuscript(manuscript_id, start, end, settings, console))


if __name__ == "__main__":
    app()
