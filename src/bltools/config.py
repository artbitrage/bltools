from pydantic import BaseModel, Field
import yaml
from pathlib import Path
from typing import Optional


class BLConfig(BaseModel):
    sleeptime: float = Field(
        default=0.0,
        description="Time to sleep between downloads (unused in async mode but kept for compat)",
    )
    basedir: Path = Field(
        default=Path("."), description="Base directory to save downloads"
    )
    rangebegin: int = Field(default=1, description="Start page number")
    rangeend: int = Field(default=259, description="End page number")
    baseurl: str = Field(
        default="http://www.bl.uk/manuscripts/Proxy.ashx?view=",
        description="Base URL for manuscript proxy",
    )

    @classmethod
    def load_from_file(cls, path: Path = Path("bl.conf")) -> "BLConfig":
        if not path.exists():
            return cls()
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**(data or {}))
