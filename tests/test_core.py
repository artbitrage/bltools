import io

import httpx
import pytest
from PIL import Image
from rich.console import Console
from rich.progress import Progress

from bltools.core import (
    IIIFCanvas,
    IIIFManifest,
    download_image,
    download_manuscript,
    fetch_manifest,
    get_file_info,
    process_iiif_canvas,
    process_legacy_page,
)
from bltools.settings import Settings


@pytest.mark.asyncio
async def test_fetch_manifest(respx_mock):
    url = "http://test.com/manifest.json"
    manifest_data = {
        "id": url,
        "type": "Manifest",
        "label": {"en": ["Test"]},
        "items": [
            {
                "id": "canvas1",
                "type": "Canvas",
                "label": "Canvas 1",
                "width": 100,
                "height": 100,
                "items": [
                    {
                        "id": "page1",
                        "type": "AnnotationPage",
                        "items": [
                            {
                                "id": "anno1",
                                "type": "Annotation",
                                "motivation": "painting",
                                "body": {
                                    "id": "image1",
                                    "type": "Image",
                                    "format": "image/jpeg",
                                    "width": 100,
                                    "height": 100,
                                    "service": [
                                        {
                                            "id": "http://test.com/image_service",
                                            "type": "ImageService3",
                                            "profile": "level2",
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
    respx_mock.get(url).mock(return_value=httpx.Response(200, json=manifest_data))

    manifest = await fetch_manifest(url)
    assert isinstance(manifest, IIIFManifest)
    assert manifest.label["en"][0] == "Test"
    assert len(manifest.items) == 1
    assert (
        manifest.items[0].get_image_url()
        == "http://test.com/image_service/full/max/0/default.jpg"
    )


@pytest.mark.asyncio
async def test_get_file_info_legacy(respx_mock):
    settings = Settings(baseurl="http://test.com/")
    manuscript_id = "ms1"
    filename = "f001r.jpg"

    xml_content = """
    <Image TileSize="256" xmlns="http://schemas.microsoft.com/deepzoom/2008">
        <Size Width="1000" Height="2000" />
    </Image>
    """
    respx_mock.get(f"{settings.baseurl}{manuscript_id}_f001r.xml").mock(
        return_value=httpx.Response(200, content=xml_content)
    )

    async with httpx.AsyncClient() as client:
        w, h, t = await get_file_info(client, manuscript_id, filename, settings)

    assert w == 999
    assert h == 1999
    assert t == 256


@pytest.mark.asyncio
async def test_download_image_retry(respx_mock):
    url = "http://test.com/img.jpg"
    route = respx_mock.get(url).mock(
        side_effect=[
            httpx.Response(500),
            httpx.Response(200, content=b"fake_image"),
        ]
    )

    async with httpx.AsyncClient() as client:
        content = await download_image(client, url)

    assert content == b"fake_image"
    assert route.call_count == 2


@pytest.mark.asyncio
async def test_download_manuscript_iiif(respx_mock, tmp_path):
    manifest_url = "http://test.com/manifest"
    settings = Settings(basedir=tmp_path)
    console = Console(quiet=True)

    manifest_data = {
        "id": manifest_url,
        "type": "Manifest",
        "label": "Test",
        "items": [
            {
                "id": "c1",
                "type": "Canvas",
                "label": "Page 1",
                "width": 10,
                "height": 10,
                "items": [
                    {
                        "id": "p1",
                        "type": "AnnotationPage",
                        "items": [
                            {
                                "id": "a1",
                                "type": "Annotation",
                                "motivation": "painting",
                                "body": {
                                    "id": "i1",
                                    "type": "Image",
                                    "format": "image/jpeg",
                                    "width": 10,
                                    "height": 10,
                                    "service": [
                                        {
                                            "id": "http://test.com/svc",
                                            "type": "ImageService2",
                                            "profile": "level2",
                                        }
                                    ],
                                },
                            }
                        ],
                    }
                ],
            }
        ],
    }
    respx_mock.get(manifest_url).mock(
        return_value=httpx.Response(200, json=manifest_data)
    )
    respx_mock.get("http://test.com/svc/full/full/0/default.jpg").mock(
        return_value=httpx.Response(200, content=b"img_content")
    )

    await download_manuscript(manifest_url, settings, console)

    target_file = tmp_path / "manifest" / "0001_Page_1.jpg"
    assert target_file.exists()
    assert target_file.read_bytes() == b"img_content"


@pytest.mark.asyncio
async def test_download_manuscript_legacy(respx_mock, tmp_path):
    ms_id = "ms1"
    settings = Settings(basedir=tmp_path, baseurl="http://test.com/")
    console = Console(quiet=True)

    # Metadata
    xml = '<Image TileSize="100"><Size Width="100" Height="100"/></Image>'
    respx_mock.get(url__regex=r".*\.xml").mock(
        return_value=httpx.Response(200, content=xml)
    )

    # Tiles
    img = Image.new("RGB", (10, 10), color="blue")
    img_bytes = io.BytesIO()
    img.save(img_bytes, format="JPEG")
    respx_mock.get(url__regex=r".*_files/.*").mock(
        return_value=httpx.Response(200, content=img_bytes.getvalue())
    )

    await download_manuscript(ms_id, settings, console, range_str="1-1")

    assert (tmp_path / ms_id / "f001r.jpg").exists()
    assert (tmp_path / ms_id / "f001v.jpg").exists()


@pytest.mark.asyncio
async def test_process_legacy_page_skip(respx_mock, tmp_path):
    target_dir = tmp_path / "ms1"
    target_dir.mkdir()
    (target_dir / "f001r.jpg").touch()

    settings = Settings()
    console = Console(quiet=True)
    with Progress(console=console) as progress:
        task_id = progress.add_task("test")
        async with httpx.AsyncClient() as client:
            await process_legacy_page(
                client, "ms1", 1, "r", settings, target_dir, progress, task_id
            )

    assert len(respx_mock.calls) == 0


@pytest.mark.asyncio
async def test_get_file_info_error(respx_mock):
    settings = Settings(baseurl="http://test.com/")
    respx_mock.get(url__regex=r".*\.xml").mock(return_value=httpx.Response(404))

    async with httpx.AsyncClient() as client:
        with pytest.raises(httpx.HTTPStatusError):
            await get_file_info(client, "ms1", "f001r.jpg", settings)


@pytest.mark.asyncio
async def test_get_file_info_malformed(respx_mock):
    settings = Settings(baseurl="http://test.com/")
    respx_mock.get(url__regex=r".*\.xml").mock(
        return_value=httpx.Response(200, content="<bad>")
    )

    async with httpx.AsyncClient() as client:
        with pytest.raises(ValueError, match="Failed to parse XML"):
            await get_file_info(client, "ms1", "f001r.jpg", settings)


@pytest.mark.asyncio
async def test_iiif_canvas_no_url():
    canvas = IIIFCanvas(
        id="c1", type="Canvas", label="Test", width=100, height=100, items=[]
    )
    assert canvas.get_image_url() == ""


@pytest.mark.asyncio
async def test_process_iiif_canvas_skip_existing(tmp_path):
    target_dir = tmp_path / "ms1"
    target_dir.mkdir()
    (target_dir / "0001_Test.jpg").touch()

    canvas = IIIFCanvas(
        id="c1", type="Canvas", label="Test", width=10, height=10, items=[]
    )
    settings = Settings()
    console = Console(quiet=True)

    with Progress(console=console) as progress:
        task_id = progress.add_task("test")
        async with httpx.AsyncClient() as client:
            await process_iiif_canvas(
                client, canvas, 1, settings, target_dir, progress, task_id
            )

    assert (target_dir / "0001_Test.jpg").stat().st_size == 0


@pytest.mark.asyncio
async def test_process_iiif_canvas_no_url(tmp_path):
    canvas = IIIFCanvas(
        id="c1", type="Canvas", label="Test", width=10, height=10, items=[]
    )
    target_dir = tmp_path / "ms1"
    target_dir.mkdir()
    settings = Settings()
    console = Console(quiet=True)

    with Progress(console=console) as progress:
        task_id = progress.add_task("test")
        async with httpx.AsyncClient() as client:
            await process_iiif_canvas(
                client, canvas, 1, settings, target_dir, progress, task_id
            )

    assert not (target_dir / "0001_Test.jpg").exists()


@pytest.mark.asyncio
async def test_process_iiif_canvas_download_error(respx_mock, tmp_path):
    manifest_data = {
        "id": "c1",
        "type": "Canvas",
        "label": "Test",
        "width": 10,
        "height": 10,
        "items": [
            {
                "id": "p1",
                "type": "AnnotationPage",
                "items": [
                    {
                        "id": "a1",
                        "type": "Annotation",
                        "motivation": "painting",
                        "body": {
                            "id": "i1",
                            "type": "Image",
                            "format": "image/jpeg",
                            "width": 10,
                            "height": 10,
                            "service": [
                                {
                                    "id": "http://test.com/svc",
                                    "type": "ImageService2",
                                    "profile": "level2",
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
    canvas = IIIFCanvas.model_validate(manifest_data)
    respx_mock.get("http://test.com/svc/full/full/0/default.jpg").mock(
        return_value=httpx.Response(500)
    )

    target_dir = tmp_path / "ms1"
    target_dir.mkdir()
    settings = Settings()
    console = Console(quiet=True)

    with Progress(console=console) as progress:
        task_id = progress.add_task("test")
        async with httpx.AsyncClient() as client:
            await process_iiif_canvas(
                client, canvas, 1, settings, target_dir, progress, task_id
            )

    assert not (target_dir / "0001_Test.jpg").exists()
