from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings.
    Reads from environment variables (BLTOOLS_*) and .env file.
    """

    basedir: Path = Path(".")
    sleeptime: float = 0.0
    rangebegin: int = 1
    rangeend: int = 259
    baseurl: str = "http://www.bl.uk/manuscripts/Proxy.ashx?view="

    model_config = SettingsConfigDict(
        env_prefix="BLTOOLS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def get_settings() -> Settings:
    return Settings()
