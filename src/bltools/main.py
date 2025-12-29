import typer
import asyncio
from typing import Optional

try:
    from typing import Annotated
except ImportError:
    from typing_extensions import (
        Annotated,
    )  # Support older python if needed, though we set >=3.9

from pathlib import Path
from bltools.config import BLConfig
from bltools.core import download_manuscript
from rich.console import Console

app = typer.Typer(help="British Library Manuscript Downloader")
console = Console()


@app.command()
def download(
    manuscript_id: Annotated[
        str, typer.Argument(help="The manuscript ID (e.g., add_ms_19352)")
    ],
    config_path: Annotated[
        Path, typer.Option("--config", "-c", help="Path to config file")
    ] = Path("bl.conf"),
    output_dir: Annotated[
        Optional[Path], typer.Option("--output", "-o", help="Override output directory")
    ] = None,
    page_range: Annotated[
        Optional[str], typer.Option("--range", "-r", help="Page range (e.g., 1-10)")
    ] = None,
) -> None:
    """
    Download a manuscript from the British Library.
    """
    config = BLConfig.load_from_file(config_path)

    # Overrides
    if output_dir:
        config.basedir = output_dir

    start, end = config.rangebegin, config.rangeend
    if page_range:
        try:
            s, e = page_range.split("-")
            start, end = int(s), int(e)
        except ValueError:
            console.print("[red]Invalid range format. Use start-end (e.g., 1-10)[/red]")
            raise typer.Exit(code=1)

    console.print(f"[bold green]Starting download for {manuscript_id}[/bold green]")
    console.print(f"Pages: {start} to {end}")

    asyncio.run(download_manuscript(manuscript_id, start, end, config, console))


if __name__ == "__main__":
    app()
