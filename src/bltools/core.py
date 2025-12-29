import asyncio
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx
import structlog
import xmltodict
from PIL import Image
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskID, TextColumn
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from bltools.models import IIIFCanvas, IIIFManifest
from bltools.settings import Settings

logger = structlog.get_logger()


async def fetch_manifest(url: str) -> IIIFManifest:
    """
    Fetch and parse a IIIF manifest from a URL.

    Args:
        url: The URL of the IIIF manifest.

    Returns:
        IIIFManifest: The parsed manifest object.
    """
    async with httpx.AsyncClient(follow_redirects=True) as client:
        res = await client.get(url)
        res.raise_for_status()
        return IIIFManifest.model_validate(res.json())


async def get_file_info(
    client: httpx.AsyncClient, manuscript_id: str, filename: str, settings: Settings
) -> tuple[int, int, int]:
    """
    Fetch the XML metadata for a page to determine dimensions and tile size.

    Args:
        client: The HTTP client to use.
        manuscript_id: The ID of the manuscript.
        filename: The specific filename (e.g., f001r.jpg).
        settings: Application settings.

    Returns:
        tuple[int, int, int]: Width, height, and tile size.

    Raises:
        ValueError: If metadata cannot be parsed.
    """
    info_url = f"{settings.baseurl}{manuscript_id}_{filename.split('.')[0]}.xml"
    log = logger.bind(manuscript_id=manuscript_id, filename=filename, url=info_url)

    log.debug("fetching_metadata")
    response = await client.get(info_url)
    response.raise_for_status()

    try:
        info_dict = xmltodict.parse(response.content)
        w = int(info_dict["Image"]["Size"]["@Width"]) - 1
        h = int(info_dict["Image"]["Size"]["@Height"]) - 1
        t = int(info_dict["Image"]["@TileSize"])
        log.debug("metadata_parsed", width=w, height=h, tile_size=t)
        return w, h, t
    except (KeyError, ValueError, Exception) as e:
        log.error("metadata_parse_failed", error=str(e))
        raise ValueError(f"Failed to parse XML for {filename}: {e}") from e


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
)
async def download_image(client: httpx.AsyncClient, url: str) -> bytes:
    """
    Download an image with exponential backoff retries.

    Args:
        client: The HTTP client to use.
        url: URL of the image.

    Returns:
        bytes: The image content.
    """
    response = await client.get(url)
    response.raise_for_status()
    return response.content


async def process_iiif_canvas(
    client: httpx.AsyncClient,
    canvas: IIIFCanvas,
    index: int,
    settings: Settings,
    target_dir: Path,
    progress: Progress,
    task_id: TaskID,
) -> None:
    """
    Download a single IIIF canvas (page).

    Args:
        client: The HTTP client to use.
        canvas: The IIIF canvas object.
        index: The page index.
        settings: Application settings.
        target_dir: Directory to save the image.
        progress: Progress bar object.
        task_id: Progress task ID.
    """
    label = (
        canvas.label
        if isinstance(canvas.label, str)
        else canvas.label.get("en", [str(index)])[0]
    )
    filename = f"{index:04d}_{label.replace(' ', '_')}.jpg"
    file_path = target_dir / filename
    log = logger.bind(canvas_id=canvas.id, filename=filename)

    if file_path.exists():
        progress.update(
            task_id, advance=1, description=f"[dim]Skipped {filename}[/dim]"
        )
        log.info("canvas_skipped_exists")
        return

    url = canvas.get_image_url()
    if not url:
        log.error("no_image_url_found")
        progress.update(task_id, advance=1)
        return

    try:
        content = await download_image(client, url)
        with open(file_path, "wb") as f:
            f.write(content)
        log.info("canvas_downloaded_success")
    except Exception as e:
        log.error("canvas_download_failed", error=str(e))
        progress.console.print(f"[red]Error downloading {filename}: {e}[/red]")

    progress.update(
        task_id, advance=1, description=f"[green]Downloaded {filename}[/green]"
    )


async def process_legacy_page(
    client: httpx.AsyncClient,
    manuscript_id: str,
    page_num: int,
    side: str,
    settings: Settings,
    target_dir: Path,
    progress: Progress,
    task_id: TaskID,
) -> None:
    """
    Process and stitch a legacy Deep Zoom page.

    Args:
        client: The HTTP client to use.
        manuscript_id: The ID of the manuscript.
        page_num: The page number.
        side: The side (r/v).
        settings: Application settings.
        target_dir: Directory to save the image.
        progress: Progress bar object.
        task_id: Progress task ID.
    """
    filename = f"f{page_num:03d}{side}.jpg"
    file_path = target_dir / filename
    log = logger.bind(manuscript_id=manuscript_id, filename=filename)

    if file_path.exists():
        progress.update(
            task_id, advance=1, description=f"[dim]Skipped {filename}[/dim]"
        )
        log.info("page_skipped_exists")
        return

    try:
        width, height, tile_size = await get_file_info(
            client, manuscript_id, filename, settings
        )
    except Exception as e:
        progress.console.print(f"[red]Error fetching info for {filename}: {e}[/red]")
        progress.update(task_id, advance=1)
        return

    columns_count = (width // tile_size) + 1
    rows_count = (height // tile_size) + 1
    zoom_level = 13
    tile_url_template = f"{settings.baseurl}{manuscript_id}_{filename.split('.')[0]}_files/{zoom_level}/{{}}_{{}}.jpg"

    page_image = Image.new("RGB", (width, height))
    sem = asyncio.Semaphore(5)

    async def get_tile(u: str, col: int, row: int) -> tuple[int, int, bytes]:
        """Fetch a single tile."""
        async with sem:
            return col, row, await download_image(client, u)

    tasks = [
        get_tile(tile_url_template.format(c, r), c, r)
        for c in range(columns_count)
        for r in range(rows_count)
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed_tiles = 0
    for res in results:
        if isinstance(res, BaseException):
            failed_tiles += 1
            continue

        # res is now guaranteed to be tuple[int, int, bytes]
        col, row, content = res
        tile = Image.open(BytesIO(content))
        page_image.paste(tile, (col * tile_size, row * tile_size))

    if failed_tiles == 0:
        page_image.save(file_path)
        log.info("page_downloaded_success")
    else:
        log.warning("page_downloaded_with_errors", failed_tiles=failed_tiles)

    progress.update(
        task_id, advance=1, description=f"[green]Downloaded {filename}[/green]"
    )


async def download_manuscript(
    input_str: str,
    settings: Settings,
    console: Console,
    range_str: Optional[str] = None,
) -> None:
    """
    Download a manuscript given a IIIF Manifest URL or a legacy ID.

    Args:
        input_str: IIIF Manifest URL or legacy manuscript ID.
        settings: Application settings.
        console: Rich console object.
        range_str: Optional range string (e.g., 1-10).
    """
    is_url = input_str.startswith("http")
    log = logger.bind(input=input_str)

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=60.0, follow_redirects=True
    ) as client:
        if is_url:
            log.info("iiif_mode_detected")
            manifest = await fetch_manifest(input_str)
            # Use manuscript ID from manifest or URL if possible
            folder_name = input_str.split("/")[-1] or "download"
            target_dir = settings.basedir / folder_name
            target_dir.mkdir(parents=True, exist_ok=True)

            items = manifest.items
            if range_str:
                try:
                    start, end = map(int, range_str.split("-"))
                    items = items[start - 1 : end]
                except (ValueError, IndexError):
                    log.error("invalid_range_format", range=range_str)
                    raise ValueError(
                        f"Invalid range format: {range_str}. Use start-end (e.g., 1-10)"
                    ) from None

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task_id = progress.add_task(
                    f"Downloading {len(items)} items...", total=len(items)
                )
                tasks = [
                    process_iiif_canvas(
                        client, canvas, i + 1, settings, target_dir, progress, task_id
                    )
                    for i, canvas in enumerate(items)
                ]
                await asyncio.gather(*tasks)
        else:
            log.info("legacy_mode_detected")
            manuscript_id = input_str
            start, end = (settings.rangebegin, settings.rangeend)
            if range_str:
                try:
                    start, end = map(int, range_str.split("-"))
                except ValueError:
                    log.error("invalid_range_format", range=range_str)
                    raise ValueError(
                        f"Invalid range format: {range_str}. Use start-end (e.g., 1-10)"
                    ) from None

            target_dir = settings.basedir / manuscript_id
            target_dir.mkdir(parents=True, exist_ok=True)

            pages = []
            for i in range(start, end + 1):
                pages.append((i, "r"))
                pages.append((i, "v"))

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                console=console,
            ) as progress:
                task_id = progress.add_task(
                    f"Downloading {len(pages)} pages...", total=len(pages)
                )
                # Legacy mode uses smaller batches to avoid overwhelming the server
                chunk_size = 5
                for i in range(0, len(pages), chunk_size):
                    chunk = pages[i : i + chunk_size]
                    batch_tasks = [
                        process_legacy_page(
                            client,
                            manuscript_id,
                            p,
                            s,
                            settings,
                            target_dir,
                            progress,
                            task_id,
                        )
                        for p, s in chunk
                    ]
                    await asyncio.gather(*batch_tasks)

    log.info("download_complete")
