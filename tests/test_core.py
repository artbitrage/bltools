import pytest
import respx
import httpx
from bltools.core import get_file_info, download_manuscript, download_tile, process_page
from bltools.settings import Settings
from rich.console import Console
from rich.progress import Progress
from PIL import Image
import io
import asyncio


@pytest.mark.asyncio
async def test_get_file_info(respx_mock):
    base_url = "http://test.com/"
    manuscript_id = "ms1"
    filename = "f001r.jpg"

    xml_content = """
    <Image TileSize="256" Overlap="1" Format="jpg" ServerFormat="Default" xmlns="http://schemas.microsoft.com/deepzoom/2008">
        <Size Width="1000" Height="2000" />
    </Image>
    """

    route = respx_mock.get(f"{base_url}{manuscript_id}_f001r.xml").mock(
        return_value=httpx.Response(200, content=xml_content)
    )

    async with httpx.AsyncClient() as client:
        w, h, t = await get_file_info(client, base_url, manuscript_id, filename)

    assert w == 999
    assert h == 1999
    assert t == 256
    assert route.called


@pytest.mark.asyncio
async def test_download_manuscript_success(respx_mock, tmp_path):
    # Setup mocks
    base_url = "http://test.com/"
    manuscript_id = "ms1"
    settings = Settings(baseurl=base_url, basedir=tmp_path)
    console = Console(quiet=True)

    # 1. XML Metadata Mock
    xml_content = """
    <Image TileSize="100" Overlap="1" Format="jpg" ServerFormat="Default">
        <Size Width="100" Height="100" />
    </Image>
    """  # 1x1 grid
    respx_mock.get(f"{base_url}{manuscript_id}_f001r.xml").mock(
        return_value=httpx.Response(200, content=xml_content)
    )
    respx_mock.get(f"{base_url}{manuscript_id}_f001v.xml").mock(
        return_value=httpx.Response(200, content=xml_content)
    )

    # 2. Tile Mock (Create a valid minimal JPG)
    img = Image.new("RGB", (10, 10), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    img_content = img_bytes.getvalue()

    # Tile URL pattern: .../files/13/{row}_{col}.jpg
    respx_mock.get(url__regex=r".*_files/13/\d+_\d+\.jpg").mock(
        return_value=httpx.Response(200, content=img_content)
    )

    await download_manuscript(manuscript_id, 1, 1, settings, console)

    # Functionality Check:
    # 1. Directory created
    # 2. Files downloaded
    target_dir = tmp_path / manuscript_id
    assert target_dir.exists()
    assert (target_dir / "f001r.jpg").exists()
    assert (target_dir / "f001v.jpg").exists()


@pytest.mark.asyncio
async def test_download_tile_retry_success(respx_mock):
    url = "http://test.com/tile.jpg"
    # Fail 2 times then succeed
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(503),
            httpx.Response(200, content=b"tile"),
        ]
    )

    async with httpx.AsyncClient() as client:
        sem = asyncio.Semaphore(1)
        r, c, content = await download_tile(client, url, 0, 0, sem)

    assert content == b"tile"
    assert route.call_count == 3


@pytest.mark.asyncio
async def test_get_file_info_malformed_xml(respx_mock):
    base_url = "http://test.com/"
    # Valid XML but missing required keys
    respx_mock.get(f"{base_url}ms1_f001r.xml").mock(
        return_value=httpx.Response(200, content="<Image><BadKey/></Image>")
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError):
            await get_file_info(client, base_url, "ms1", "f001r.jpg")


@pytest.mark.asyncio
async def test_process_page_skips_existing(respx_mock, tmp_path):
    # Setup existing file
    target_dir = tmp_path / "ms1"
    target_dir.mkdir()
    (target_dir / "f001r.jpg").touch()

    # No requests should be made
    base_url = "http://test.com/"
    settings = Settings(baseurl=base_url)

    # Mock progress
    console = Console(quiet=True)
    with Progress(console=console) as progress:
        task_id = progress.add_task("test")

        async with httpx.AsyncClient() as client:
            await process_page(
                client, "ms1", 1, "r", settings, target_dir, progress, task_id
            )

    # If it skipped, no network calls
    assert len(respx_mock.calls) == 0


@pytest.mark.asyncio
async def test_process_page_handles_metadata_error(respx_mock, tmp_path):
    base_url = "http://test.com/"
    # Return 404 for metadata
    respx_mock.get(f"{base_url}ms1_f001r.xml").mock(return_value=httpx.Response(404))

    target_dir = tmp_path / "ms1"
    target_dir.mkdir()
    settings = Settings(baseurl=base_url)

    console = Console(quiet=True)
    with Progress(console=console) as progress:
        task_id = progress.add_task("test")
        async with httpx.AsyncClient() as client:
            # Should returns safely without raising, logging error
            await process_page(
                client, "ms1", 1, "r", settings, target_dir, progress, task_id
            )


@pytest.mark.asyncio
async def test_process_page_handles_tile_error(respx_mock, tmp_path):
    base_url = "http://test.com/"
    # Metadata success
    xml_content = """<Image TileSize="256"><Size Width="100" Height="100"/></Image>"""
    respx_mock.get(f"{base_url}ms1_f001r.xml").mock(
        return_value=httpx.Response(200, content=xml_content)
    )
    # Tile failure (all attempts fail)
    respx_mock.get(f"{base_url}ms1_f001r_files/13/0_0.jpg").mock(
        return_value=httpx.Response(500)
    )

    target_dir = tmp_path / "ms1"
    target_dir.mkdir()
    settings = Settings(baseurl=base_url)

    console = Console(quiet=True)
    with Progress(console=console) as progress:
        task_id = progress.add_task("test")
        async with httpx.AsyncClient() as client:
            # Should handle failure gracefully (log warning)
            await process_page(
                client, "ms1", 1, "r", settings, target_dir, progress, task_id
            )

    # File should verify partially or fail (in our code it saves partial or blanks)
    assert (target_dir / "f001r.jpg").exists()
