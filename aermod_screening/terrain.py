from __future__ import annotations

import hashlib
import json
import math
import shutil
import subprocess
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path


COPERNICUS_BASE_URL = "https://copernicus-dem-30m.s3.eu-central-1.amazonaws.com"


@dataclass(frozen=True)
class TerrainPreparation:
    provider: str
    source_path: str
    prepared_path: str
    source_sha256: str
    prepared_sha256: str
    latitude_deg: float
    longitude_deg: float
    utm_zone: int
    utm_hemisphere: str


def wgs84_to_utm(latitude_deg: float, longitude_deg: float) -> tuple[float, float, int]:
    zone = utm_zone(longitude_deg)
    epsg = 32600 + zone if latitude_deg >= 0 else 32700 + zone
    gdaltransform = shutil.which("gdaltransform")
    if not gdaltransform:
        raise RuntimeError("gdaltransform no está disponible")
    completed = subprocess.run(
        [gdaltransform, "-s_srs", "EPSG:4326", "-t_srs", f"EPSG:{epsg}"],
        input=f"{longitude_deg} {latitude_deg}\n",
        check=True,
        capture_output=True,
        text=True,
    )
    easting, northing, *_ = completed.stdout.split()
    return float(easting), float(northing), -zone if latitude_deg < 0 else zone


def generate_aermap_input(
    terrain_filename: str,
    *,
    latitude_deg: float,
    longitude_deg: float,
    receptor_distances_m: tuple[float, ...] = (50.0, 500.0, 1000.0, 2000.0),
    directions_deg: tuple[int, ...] = tuple(range(0, 360, 45)),
) -> str:
    easting, northing, signed_zone = wgs84_to_utm(latitude_deg, longitude_deg)
    maximum_distance = max(receptor_distances_m)
    domain_margin = max(5000.0, maximum_distance * 1.5)
    lines = [
        "CO STARTING",
        "   TITLEONE MENDOZA TERRAIN PREPARATION",
        "   TERRHGTS EXTRACT",
        "   DATATYPE NED",
        f"   DATAFILE {terrain_filename}",
        (
            f"   DOMAINXY {easting-domain_margin:.2f} {northing-domain_margin:.2f} {signed_zone} "
            f"{easting+domain_margin:.2f} {northing+domain_margin:.2f} {signed_zone}"
        ),
        f"   ANCHORXY {easting:.2f} {northing:.2f} {easting:.2f} {northing:.2f} {signed_zone} 0",
        "   RUNORNOT RUN",
        "CO FINISHED",
        "",
        "SO STARTING",
        f"   LOCATION SOURCE POINT {easting:.2f} {northing:.2f}",
        "SO FINISHED",
        "",
        "RE STARTING",
    ]
    for distance in receptor_distances_m:
        for direction in directions_deg:
            radians = math.radians(direction)
            receptor_x = easting + distance * math.sin(radians)
            receptor_y = northing + distance * math.cos(radians)
            lines.append(f"   DISCCART {receptor_x:.2f} {receptor_y:.2f}")
    lines.extend(
        [
            "RE FINISHED",
            "",
            "OU STARTING",
            "   RECEPTOR receptors-aermap.out",
            "   SOURCLOC source-aermap.out",
            "OU FINISHED",
            "",
        ]
    )
    return "\n".join(lines)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def utm_zone(longitude_deg: float) -> int:
    if not -180 <= longitude_deg <= 180:
        raise ValueError("La longitud debe estar entre -180 y 180 grados")
    return min(60, max(1, math.floor((longitude_deg + 180) / 6) + 1))


def copernicus_tile_name(latitude_deg: float, longitude_deg: float) -> str:
    if not -90 <= latitude_deg <= 90:
        raise ValueError("La latitud debe estar entre -90 y 90 grados")
    if not -180 <= longitude_deg <= 180:
        raise ValueError("La longitud debe estar entre -180 y 180 grados")
    latitude_floor = math.floor(latitude_deg)
    longitude_floor = math.floor(longitude_deg)
    latitude_token = f"{'N' if latitude_floor >= 0 else 'S'}{abs(latitude_floor):02d}_00"
    longitude_token = f"{'E' if longitude_floor >= 0 else 'W'}{abs(longitude_floor):03d}_00"
    return f"Copernicus_DSM_COG_10_{latitude_token}_{longitude_token}_DEM"


def copernicus_url(latitude_deg: float, longitude_deg: float) -> str:
    tile = copernicus_tile_name(latitude_deg, longitude_deg)
    return f"{COPERNICUS_BASE_URL}/{tile}/{tile}.tif"


def copernicus_tiles_for_domain(latitude_deg: float, longitude_deg: float, margin_m: float) -> list[tuple[float, float]]:
    """Return representative coordinates for every 1-degree tile intersecting a square domain."""
    latitude_delta = margin_m / 111_320.0
    longitude_delta = margin_m / (111_320.0 * max(0.01, math.cos(math.radians(latitude_deg))))
    latitudes = range(math.floor(latitude_deg - latitude_delta), math.floor(latitude_deg + latitude_delta) + 1)
    longitudes = range(math.floor(longitude_deg - longitude_delta), math.floor(longitude_deg + longitude_delta) + 1)
    return [(latitude + 0.5, longitude + 0.5) for latitude in latitudes for longitude in longitudes]


def download_copernicus(latitude_deg: float, longitude_deg: float, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 0:
        return destination
    partial = destination.with_suffix(destination.suffix + ".part")
    try:
        with urllib.request.urlopen(copernicus_url(latitude_deg, longitude_deg)) as response, partial.open("wb") as output:
            shutil.copyfileobj(response, output)
        partial.replace(destination)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    return destination


def prepare_for_aermap(
    source: Path | list[Path],
    destination: Path,
    *,
    latitude_deg: float,
    longitude_deg: float,
    provider: str,
) -> TerrainPreparation:
    sources = [source] if isinstance(source, Path) else source
    if not sources:
        raise ValueError("Se requiere al menos una tesela de terreno")
    for item in sources:
        if not item.is_file():
            raise FileNotFoundError(item)
    gdal_translate = shutil.which("gdal_translate")
    gdalbuildvrt = shutil.which("gdalbuildvrt")
    if not gdal_translate or (len(sources) > 1 and not gdalbuildvrt):
        raise RuntimeError("gdal_translate no está disponible")
    destination.parent.mkdir(parents=True, exist_ok=True)
    input_path = sources[0]
    if len(sources) > 1:
        input_path = destination.with_suffix(".mosaic.vrt")
        subprocess.run([gdalbuildvrt, str(input_path), *(str(item) for item in sources)], check=True, capture_output=True, text=True)
    destination.unlink(missing_ok=True)
    subprocess.run(
        [gdal_translate, "-of", "GTiff", "-co", "COMPRESS=NONE", "-co", "TILED=NO", str(input_path), str(destination)],
        check=True,
        capture_output=True,
        text=True,
    )
    preparation = TerrainPreparation(
        provider=provider,
        source_path=";".join(str(item.resolve()) for item in sources),
        prepared_path=str(destination.resolve()),
        source_sha256=hashlib.sha256("".join(sha256(item) for item in sources).encode("ascii")).hexdigest(),
        prepared_sha256=sha256(destination),
        latitude_deg=latitude_deg,
        longitude_deg=longitude_deg,
        utm_zone=utm_zone(longitude_deg),
        utm_hemisphere="north" if latitude_deg >= 0 else "south",
    )
    destination.with_suffix(".metadata.json").write_text(
        json.dumps(asdict(preparation), indent=2) + "\n", encoding="utf-8"
    )
    return preparation
