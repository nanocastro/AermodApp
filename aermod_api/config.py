from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_path: Path
    runs_directory: Path
    aermod_executable: Path
    makemet_executable: Path
    aermet_executable: Path = Path("bin/aermet")
    hourly_directory: Path = Path("data/hourly")
    aermap_executable: Path = Path("bin/aermap")
    terrain_directory: Path = Path("data/terrain")
    bpipprm_executable: Path = Path("bin/bpipprm")
    frontend_origins: tuple[str, ...] = ("http://localhost:5173", "http://127.0.0.1:5173")
    earthdata_username: str = ""
    earthdata_password: str = ""
    cdsapi_url: str = "https://cds.climate.copernicus.eu/api"
    cdsapi_key: str = ""
    surface_directory: Path = Path("data/surface")
    credentials_file: Path = Path("data/.credentials")
    frontend_directory: Path | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        load_dotenv(PROJECT_ROOT / ".env", override=False)
        return cls(
            database_path=Path(os.getenv("AERMOD_DATABASE", "data/aermod.sqlite3")),
            runs_directory=Path(os.getenv("AERMOD_RUNS_DIR", "data/runs")),
            aermod_executable=Path(os.getenv("AERMOD_EXECUTABLE", "bin/aermod")),
            makemet_executable=Path(os.getenv("MAKEMET_EXECUTABLE", "bin/makemet")),
            aermet_executable=Path(os.getenv("AERMET_EXECUTABLE", "bin/aermet")),
            hourly_directory=Path(os.getenv("AERMOD_HOURLY_DIR", "data/hourly")),
            aermap_executable=Path(os.getenv("AERMAP_EXECUTABLE", "bin/aermap")),
            terrain_directory=Path(os.getenv("AERMOD_TERRAIN_DIR", "data/terrain")),
            bpipprm_executable=Path(os.getenv("BPIPPRM_EXECUTABLE", "bin/bpipprm")),
            earthdata_username=os.getenv("EARTHDATA_USERNAME", "").strip(),
            earthdata_password=os.getenv("EARTHDATA_PASSWORD", ""),
            cdsapi_url=os.getenv("CDSAPI_URL", "https://cds.climate.copernicus.eu/api").strip(),
            cdsapi_key=os.getenv("CDSAPI_KEY", "").strip(),
            surface_directory=Path(os.getenv("AERMOD_SURFACE_DIR", "data/surface")),
            credentials_file=Path(os.getenv("AERMOD_CREDENTIALS_FILE", "data/.credentials")),
            frontend_directory=(Path(value) if (value := os.getenv("AERMOD_FRONTEND_DIR", "").strip()) else None),
            frontend_origins=tuple(
                origin.strip()
                for origin in os.getenv(
                    "AERMOD_FRONTEND_ORIGINS",
                    "http://localhost:5173,http://127.0.0.1:5173",
                ).split(",")
                if origin.strip()
            ),
        )
