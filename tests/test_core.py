import pytest
import respx
import httpx
from bltools.core import get_file_info, download_manuscript
from bltools.config import BLConfig
from rich.console import Console
from PIL import Image
import io


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
    config = BLConfig(baseurl=base_url, basedir=tmp_path)
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

    await download_manuscript(manuscript_id, 1, 1, config, console)

    # Check if files were created
    target_dir = tmp_path / manuscript_id
    assert (target_dir / "f001r.jpg").exists()
    assert (target_dir / "f001v.jpg").exists()
