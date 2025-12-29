from bltools.config import BLConfig
from bltools.main import app
from typer.testing import CliRunner
from pathlib import Path

runner = CliRunner()


def test_config_defaults():
    config = BLConfig()
    assert config.rangebegin == 1
    assert config.baseurl.startswith("http")


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "British Library Manuscript Downloader" in result.stdout


def test_invalid_range():
    result = runner.invoke(app, ["download", "foo", "--range", "invalid"])
    assert result.exit_code == 1
    assert "Invalid range format" in result.stdout
