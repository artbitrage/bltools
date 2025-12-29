import httpx
import asyncio
from pathlib import Path
from PIL import Image
from io import BytesIO
import xmltodict
from rich.progress import Progress, TaskID, SpinnerColumn, BarColumn, TextColumn
from rich.console import Console
from bltools.config import BLConfig
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)
import structlog

logger = structlog.get_logger()


async def get_file_info(
    client: httpx.AsyncClient, base_url: str, manuscript_id: str, filename: str
) -> tuple[int, int, int]:
    """
    Fetch the XML metadata for a page to determine dimensions and tile size.
    """
    info_url = f"{base_url}{manuscript_id}_{filename.split('.')[0]}.xml"
    log = logger.bind(manuscript_id=manuscript_id, filename=filename, url=info_url)

    log.debug("fetching_metadata")
    response = await client.get(info_url)
    response.raise_for_status()

    info_dict = xmltodict.parse(response.content)
    try:
        w = int(info_dict["Image"]["Size"]["@Width"]) - 1
        h = int(info_dict["Image"]["Size"]["@Height"]) - 1
        t = int(info_dict["Image"]["@TileSize"])
        log.debug("metadata_parsed", width=w, height=h, tile_size=t)
        return w, h, t
    except (KeyError, ValueError) as e:
        log.error("metadata_parse_failed", error=str(e))
        raise ValueError(f"Failed to parse XML for {filename}: {e}")


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
)
async def download_tile(
    client: httpx.AsyncClient, url: str, row: int, col: int, sem: asyncio.Semaphore
) -> tuple[int, int, bytes]:
    """
    Download a single tile with retries.
    """
    async with sem:
        # We don't log every tile download success to avoid spam, only failures/retries via tenacity if configured
        response = await client.get(url)
        response.raise_for_status()
        return row, col, response.content


async def process_page(
    client: httpx.AsyncClient,
    manuscript_id: str,
    page_num: int,
    side: str,
    config: BLConfig,
    target_dir: Path,
    progress: Progress,
    task_id: TaskID,
) -> None:
    """
    Process a single page: fetch metadata, download all tiles, stitch, and save.
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
            client, config.baseurl, manuscript_id, filename
        )
    except Exception as e:
        # Already logged in get_file_info
        progress.console.print(f"[red]Error fetching info for {filename}: {e}[/red]")
        progress.update(task_id, advance=1)
        return

    rows = (width // tile_size) + 1
    cols = (height // tile_size) + 1
    zoom_level = 13

    tile_url_template = f"{config.baseurl}{manuscript_id}_{filename.split('.')[0]}_files/{zoom_level}/{{}}_{{}}.jpg"

    # Create blank image
    page_image = Image.new("RGB", (width, height))

    # Prepare tile tasks
    sem = asyncio.Semaphore(10)  # Concurrency limit for tiles per page
    tasks = []

    log.debug("starting_tile_downloads", total_tiles=rows * cols)
    for r in range(rows):
        for c in range(cols):
            url = tile_url_template.format(r, c)
            tasks.append(download_tile(client, url, r, c, sem))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    failed_tiles = 0
    for res in results:
        if isinstance(res, Exception):
            log.warning("tile_download_failed", error=str(res))
            failed_tiles += 1
            continue

        r, c, content = res
        try:
            tile = Image.open(BytesIO(content))
            box = (r * tile_size, c * tile_size)
            page_image.paste(tile, box)
        except Exception as e:
            log.error("tile_processing_failed", error=str(e))
            failed_tiles += 1

    if failed_tiles > 0:
        log.warning("page_downloaded_with_errors", failed_tiles=failed_tiles)
    else:
        log.info("page_downloaded_success")

    page_image.save(file_path)
    progress.update(
        task_id, advance=1, description=f"[green]Downloaded {filename}[/green]"
    )


async def download_manuscript(
    manuscript_id: str, start: int, end: int, config: BLConfig, console: Console
) -> None:
    """
    Main orchestrator for downloading a manuscript.
    """
    log = logger.bind(manuscript_id=manuscript_id)
    target_dir = config.basedir / manuscript_id
    target_dir.mkdir(parents=True, exist_ok=True)

    log.info(
        "starting_manuscript_download",
        start_page=start,
        end_page=end,
        target_dir=str(target_dir),
    )

    pages = []
    for i in range(start, end + 1):
        pages.append((i, "r"))
        pages.append((i, "v"))

    async with httpx.AsyncClient(
        headers={"User-Agent": "Mozilla/5.0"}, timeout=30.0
    ) as client:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            console=console,
        ) as progress:
            total_files = len(pages)
            main_task = progress.add_task(
                "[cyan]Downloading pages...", total=total_files
            )

            chunk_size = 5  # Download 5 pages in parallel

            for i in range(0, len(pages), chunk_size):
                chunk = pages[i : i + chunk_size]
                batch_tasks = [
                    process_page(
                        client,
                        manuscript_id,
                        p_num,
                        p_side,
                        config,
                        target_dir,
                        progress,
                        main_task,
                    )
                    for p_num, p_side in chunk
                ]
                await asyncio.gather(*batch_tasks)

    log.info("manuscript_download_complete")
