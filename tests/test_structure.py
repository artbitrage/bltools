from bltools.main import app
from typer.testing import CliRunner
from bltools.settings import Settings

runner = CliRunner()


def test_config_defaults():
    settings = Settings()
    assert settings.rangebegin == 1
    assert settings.baseurl.startswith("http")


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0, (
        f"Help failed with {result.exit_code}. Exc: {result.exception}. Stdout: {result.stdout}"
    )
    # Check for core help text from Typer
    assert "Show this message and exit" in result.stdout


def test_invalid_range():
    result = runner.invoke(app, ["download", "foo", "--range", "invalid"])
    # Typer returns 2 for usage errors or exceptions during parsing
    assert result.exit_code != 0, (
        f"Invalid range failed with {result.exit_code}. Exc: {result.exception}. Stdout: {result.stdout} Stderr: {result.stderr}"
    )
    # Just ensure it failed, exact message might vary (Typer usage error vs our ValueError)
    pass
