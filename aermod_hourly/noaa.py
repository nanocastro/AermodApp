from __future__ import annotations

import gzip
import hashlib
import json
import shutil
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from .stations import HourlyStation


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def noaa_urls(station: HourlyStation, year: int) -> dict[str, str]:
    return {
        "surface_isd_gzip": (
            f"https://www.ncei.noaa.gov/pub/data/noaa/{year}/"
            f"{station.surface_isd_id}-{year}.gz"
        ),
        "upper_igra_zip": (
            "https://www.ncei.noaa.gov/pub/data/igra/data/data-por/"
            f"{station.upper_igra_id}-data.txt.zip"
        ),
    }


def _download(url: str, destination: Path) -> None:
    if destination.is_file() and destination.stat().st_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "AERMOD-Hourly/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(destination)
    finally:
        partial.unlink(missing_ok=True)


def prepare_noaa_inputs(station: HourlyStation, year: int, directory: Path) -> dict:
    directory = directory.resolve()
    raw = directory / "raw"
    inputs = directory / "input"
    raw.mkdir(parents=True, exist_ok=True)
    inputs.mkdir(parents=True, exist_ok=True)

    urls = noaa_urls(station, year)
    surface_gzip = raw / f"{station.surface_isd_id}-{year}.gz"
    upper_zip = raw / f"{station.upper_igra_id}-data.txt.zip"
    _download(urls["surface_isd_gzip"], surface_gzip)
    _download(urls["upper_igra_zip"], upper_zip)

    surface_isd = inputs / f"{station.slug}-{year}.isd"
    if not surface_isd.exists():
        with gzip.open(surface_gzip, "rb") as source, surface_isd.open("wb") as output:
            shutil.copyfileobj(source, output)

    upper_igra = inputs / f"{station.slug}-igra.txt"
    if not upper_igra.exists():
        with zipfile.ZipFile(upper_zip) as archive:
            candidates = [name for name in archive.namelist() if name.endswith("-data.txt")]
            if len(candidates) != 1:
                raise ValueError(f"Archivo IGRA inesperado: {archive.namelist()}")
            with archive.open(candidates[0]) as source, upper_igra.open("wb") as output:
                shutil.copyfileobj(source, output)

    files = []
    for path, role, url in (
        (surface_gzip, "raw_surface_isd_gzip", urls["surface_isd_gzip"]),
        (upper_zip, "raw_upper_igra_zip", urls["upper_igra_zip"]),
        (surface_isd, "aermet_surface_isd", None),
        (upper_igra, "aermet_upper_igra", None),
    ):
        files.append({
            "path": str(path.relative_to(directory)),
            "role": role,
            "url": url,
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "station": station.slug,
        "year": year,
        "providers": {"surface": "NOAA NCEI ISD", "upper_air": "NOAA NCEI IGRA v2"},
        "station_ids": {
            "surface_isd": station.surface_isd_id,
            "upper_igra": station.upper_igra_id,
        },
        "files": files,
    }
    (directory / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest
