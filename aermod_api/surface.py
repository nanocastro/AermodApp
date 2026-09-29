from __future__ import annotations

import csv
import json
import math
import subprocess
import time
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import cdsapi
import httpx
import numpy as np
from netCDF4 import Dataset

from .config import Settings

APPEEARS = "https://appeears.earthdatacloud.nasa.gov/api"
APPEEARS_TIMEOUT = httpx.Timeout(connect=30, read=180, write=60, pool=30)
ROUGHNESS_SEASONS = (
    "midsummer_lush",
    "winter_snow",
    "winter_no_snow",
    "transitional_spring",
    "autumn_unharvested",
)

# WorldCover-to-z0 crosswalk. EPA values reproduce AERSURFACE 26135 tables for
# the selected equivalent NLCD class. ECMWF values fill classes without a
# sufficiently specific NLCD equivalent. Values follow ROUGHNESS_SEASONS.
ROUGHNESS_BY_CLASS = {
    10: (.9, .8, 1.1, 1.3, 1.3),        # EPA NLCD 43: mixed forest
    20: (.3, .15, .3, .3, .3),           # EPA NLCD 52: shrub/scrub, non-arid
    30: (.01, .005, .05, .1, .1),       # EPA NLCD 71: grassland/herbaceous
    40: (.03, .014, .04, .2, .2),       # EPA NLCD 82: cultivated crops
    50: (.3, .2, .3, .3, .3),           # EPA NLCD 23: developed, medium intensity
    60: (.05, .01, .05, .05, .05),       # EPA NLCD 31: barren, non-arid
    70: (.002, .002, .002, .002, .002), # EPA NLCD 12: perennial ice/snow
    80: (.001, .001, .001, .001, .001), # EPA NLCD 11: open water
    90: (.2, .1, .2, .2, .2),           # EPA NLCD 95: emergent herbaceous wetland
    95: (.4, .3, .5, .5, .5),           # EPA NLCD 91: woody wetland
    100: (.034, .034, .034, .034, .034),# ECMWF: tundra
}

# AERSURFACE applies lower values to developed and agricultural classes when
# the meteorological tower is at an airport.
AIRPORT_ROUGHNESS_OVERRIDES = {
    40: (.02, .01, .02, .03, .03),      # EPA NLCD 82, airport
    50: (.05, .04, .06, .06, .06),      # EPA NLCD 23, airport
}
WORLDCOVER_CLASS_NAMES = {
    10: "tree_cover",
    20: "shrubland",
    30: "grassland",
    40: "cropland",
    50: "built_up",
    60: "bare_sparse_vegetation",
    70: "snow_ice",
    80: "permanent_water",
    90: "herbaceous_wetland",
    95: "mangroves",
    100: "moss_lichen",
}
MINIMUM_COVERAGE_PERCENT = 50.0


def coverage_quality(valid_count: int, expected_count: int) -> dict:
    if expected_count <= 0:
        raise ValueError("La cantidad esperada debe ser mayor que cero")
    coverage_percent = min(100.0, valid_count / expected_count * 100)
    return {
        "valid_count": valid_count,
        "expected_count": expected_count,
        "missing_count": max(expected_count - valid_count, 0),
        "coverage_percent": coverage_percent,
        "meets_minimum": coverage_percent > MINIMUM_COVERAGE_PERCENT,
    }


def representative_roughness_candidates(sectors: list[dict], limit: int = 5) -> list[float]:
    if limit < 2:
        raise ValueError("Se requieren al menos dos posiciones representativas")
    values = sorted({float(sector["roughness_m"]) for sector in sectors})
    if not values:
        raise ValueError("No hay rugosidades sectoriales válidas")
    if len(values) <= limit:
        return values
    return [values[round(index * (len(values) - 1) / (limit - 1))] for index in range(limit)]


def last_complete_months(today: date | None = None) -> tuple[date, date]:
    today = today or date.today()
    end = today.replace(day=1) - timedelta(days=1)
    start = (end.replace(day=1) - timedelta(days=1)).replace(day=1)
    return start, end


def worldcover_tile(latitude: float, longitude: float) -> str:
    north_edge = math.floor(latitude / 3) * 3
    west_edge = math.floor(longitude / 3) * 3
    return f"{'N' if north_edge >= 0 else 'S'}{abs(north_edge):02d}{'E' if west_edge >= 0 else 'W'}{abs(west_edge):03d}"


def bearing_distance(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    north = (lat - lat0) * 111_320
    east = (lon - lon0) * 111_320 * math.cos(math.radians((lat0 + lat) / 2))
    return math.degrees(math.atan2(east, north)) % 360, math.hypot(east, north)


def roughness_season_for_month(month: int, *, southern_hemisphere: bool,
                               continuous_snow: bool = False) -> str:
    if not 1 <= month <= 12:
        raise ValueError("El mes debe estar entre 1 y 12")
    if continuous_snow:
        return "winter_snow"
    if southern_hemisphere:
        if month in {12, 1, 2}:
            return "midsummer_lush"
        if month in {3, 4, 5}:
            return "autumn_unharvested"
        if month in {6, 7, 8}:
            return "winter_no_snow"
        return "transitional_spring"
    if month in {6, 7, 8}:
        return "midsummer_lush"
    if month in {9, 10, 11}:
        return "autumn_unharvested"
    if month in {12, 1, 2}:
        return "winter_no_snow"
    return "transitional_spring"


def roughness_for_class(land_class: int, season: str, *, airport: bool = False) -> float | None:
    try:
        season_index = ROUGHNESS_SEASONS.index(season)
    except ValueError as error:
        raise ValueError(f"Temporada de rugosidad desconocida: {season}") from error
    profile = (AIRPORT_ROUGHNESS_OVERRIDES.get(land_class)
               if airport else None) or ROUGHNESS_BY_CLASS.get(land_class)
    return None if profile is None else profile[season_index]


def directional_roughness(points: list[tuple[float, float, int]], latitude: float,
                          longitude: float, *, season: str = "winter_no_snow",
                          airport: bool = False) -> list[dict]:
    buckets: list[list[float]] = [[] for _ in range(36)]
    for lon, lat, land_class in points:
        bearing, distance = bearing_distance(latitude, longitude, lat, lon)
        roughness = roughness_for_class(land_class, season, airport=airport)
        if 100 <= distance <= 1000 and roughness is not None:
            buckets[int(((bearing + 5) % 360) // 10)].append(roughness)
    result = []
    for index, values in enumerate(buckets):
        if not values:
            raise ValueError(f"Sin píxeles WorldCover válidos para el sector {index * 10}°")
        result.append({"direction_deg": index * 10,
                       "roughness_m": float(np.mean(values)), "pixel_count": len(values)})
    return result


def aersurface_like_directional_roughness(
    points: list[tuple[float, float, int]],
    latitude: float,
    longitude: float,
    *,
    sector_width_deg: int = 30,
    radius_m: float = 1000.0,
    pixel_resolution_m: float = 10.0,
    season: str = "winter_no_snow",
    airport: bool = False,
) -> list[dict]:
    """Approximate AERSURFACE ZORAD with WorldCover land-cover classes.

    The official AERSURFACE implementation applies an inverse-distance weighted
    geometric mean to roughness values. This helper reproduces that spatial
    aggregation, but it is not AERSURFACE itself: WorldCover and the provisional
    WorldCover-to-z0 lookup replace the US-specific NLCD inputs and tables.
    """
    if sector_width_deg < 30 or 360 % sector_width_deg:
        raise ValueError("El ancho sectorial debe dividir 360° y ser al menos 30°")
    if radius_m <= 0 or pixel_resolution_m <= 0:
        raise ValueError("El radio y la resolución deben ser positivos")

    sector_count = 360 // sector_width_deg
    weighted_logs = [0.0] * sector_count
    weight_sums = [0.0] * sector_count
    class_counts: list[dict[int, int]] = [{} for _ in range(sector_count)]
    minimum_distance_m = pixel_resolution_m / 2

    for lon, lat, land_class in points:
        roughness = roughness_for_class(land_class, season, airport=airport)
        if roughness is None:
            continue
        bearing, distance = bearing_distance(latitude, longitude, lat, lon)
        if distance > radius_m:
            continue
        sector_index = min(int(bearing // sector_width_deg), sector_count - 1)
        weight = 1.0 / max(distance, minimum_distance_m)
        weighted_logs[sector_index] += weight * math.log(roughness)
        weight_sums[sector_index] += weight
        counts = class_counts[sector_index]
        counts[land_class] = counts.get(land_class, 0) + 1

    result = []
    for index, weight_sum in enumerate(weight_sums):
        if weight_sum == 0:
            raise ValueError(
                f"Sin píxeles WorldCover válidos para el sector "
                f"{index * sector_width_deg}°–{(index + 1) * sector_width_deg}°"
            )
        counts = class_counts[index]
        result.append({
            "sector_start_deg": index * sector_width_deg,
            "sector_end_deg": (index + 1) * sector_width_deg,
            "direction_center_deg": index * sector_width_deg + sector_width_deg / 2,
            "roughness_m": math.exp(weighted_logs[index] / weight_sum),
            "pixel_count": sum(counts.values()),
            "class_pixel_counts": {
                WORLDCOVER_CLASS_NAMES[land_class]: count
                for land_class, count in sorted(counts.items())
            },
        })
    return result


class SurfaceService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def estimate(self, latitude: float, longitude: float, progress: Callable[[int, int, str], None] | None = None) -> dict:
        start, end = last_complete_months()
        key = f"{latitude:.5f}_{longitude:.5f}_{start}_{end}".replace("-", "m")
        directory = self.settings.surface_directory.resolve() / key
        directory.mkdir(parents=True, exist_ok=True)
        if progress: progress(0, 4, "Consultando albedo MODIS")
        albedo = self._albedo(latitude, longitude, start, end, directory)
        if progress: progress(1, 4, "Consultando flujos ERA5-Land")
        bowen = self._bowen(latitude, longitude, start, end, directory)
        if progress: progress(2, 4, "Procesando cobertura ESA WorldCover")
        roughness_season = roughness_season_for_month(
            end.month, southern_hemisphere=latitude < 0
        )
        sectors = self._roughness(
            latitude, longitude, directory, season=roughness_season
        )
        if progress: progress(3, 4, "Calculando calidad y candidatos")
        roughness_candidates = representative_roughness_candidates(sectors)
        roughest = max(sectors, key=lambda item: item["roughness_m"])
        albedo_quality = coverage_quality(albedo["count"], (end - start).days + 1)
        bowen_quality = coverage_quality(bowen["count"], ((end - start).days + 1) * 24)
        meets_minimum_coverage = albedo_quality["meets_minimum"] and bowen_quality["meets_minimum"]
        warnings = ["Los parámetros representan solo dos meses calendario y pueden tener sesgo estacional.",
                    "Se adoptó provisionalmente el máximo de los 36 promedios sectoriales de rugosidad.",
                    f"La rugosidad usa la tabla estacional {roughness_season} de la correspondencia EPA/ECMWF."]
        for label, quality in (("MODIS", albedo_quality), ("ERA5-Land", bowen_quality)):
            if not quality["meets_minimum"]:
                warnings.append(
                    f"{label} no supera la cobertura mínima de {MINIMUM_COVERAGE_PERCENT:.0f} % "
                    f"({quality['coverage_percent']:.1f} %; faltan {quality['missing_count']} observaciones).")
        result = {
            "latitude_deg": latitude, "longitude_deg": longitude,
            "period_start": start.isoformat(), "period_end": end.isoformat(),
            "albedo": albedo["value"], "albedo_valid_count": albedo["count"],
            "albedo_expected_count": albedo_quality["expected_count"],
            "albedo_missing_count": albedo_quality["missing_count"],
            "albedo_coverage_percent": albedo_quality["coverage_percent"],
            "bowen_ratio": bowen["value"], "bowen_valid_count": bowen["count"],
            "bowen_expected_count": bowen_quality["expected_count"],
            "bowen_missing_count": bowen_quality["missing_count"],
            "bowen_coverage_percent": bowen_quality["coverage_percent"],
            "minimum_coverage_percent": MINIMUM_COVERAGE_PERCENT,
            "meets_minimum_coverage": meets_minimum_coverage,
            "surface_roughness_m": roughest["roughness_m"],
            "selected_roughness_direction_deg": roughest["direction_deg"],
            "roughness_season": roughness_season,
            "roughness_sectors": sectors,
            "roughness_candidates_m": roughness_candidates,
            "providers": {"albedo": "NASA MODIS MCD43A3.061",
                          "bowen": "ERA5-Land",
                          "roughness": "ESA WorldCover 2021 v200 + EPA AERSURFACE/ECMWF crosswalk"},
            "warnings": warnings,
        }
        (directory / "surface-result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8")
        if progress: progress(4, 4, "Parámetros locales listos")
        return result

    def _albedo(self, latitude: float, longitude: float, start: date, end: date,
                directory: Path) -> dict:
        output = directory / "modis-albedo.csv"
        if not output.exists():
            try:
                with httpx.Client(timeout=APPEEARS_TIMEOUT, follow_redirects=True) as client:
                    login = client.post(f"{APPEEARS}/login", auth=(
                        self.settings.earthdata_username, self.settings.earthdata_password))
                    if login.status_code in {401, 403}:
                        raise ValueError(
                            "NASA Earthdata rechazó las credenciales. Abrí Credenciales y volvé a ingresarlas."
                        )
                    login.raise_for_status()
                    headers = {"Authorization": f"Bearer {login.json()['token']}"}
                    payload = {"task_type": "point", "task_name": f"AERMOD-{start}-{end}",
                               "params": {"dates": [{"startDate": start.strftime('%m-%d-%Y'),
                                                      "endDate": end.strftime('%m-%d-%Y')}],
                               "layers": [{"product": "MCD43A3.061", "layer": "Albedo_WSA_shortwave"},
                                          {"product": "MCD43A3.061", "layer": "BRDF_Albedo_Band_Mandatory_Quality_shortwave"}],
                               "coordinates": [{"latitude": latitude, "longitude": longitude,
                                                "id": "source", "category": "source"}]}}
                    task = client.post(f"{APPEEARS}/task", headers=headers, json=payload)
                    task.raise_for_status(); task_id = task.json()["task_id"]
                    for _ in range(120):
                        status = client.get(f"{APPEEARS}/task/{task_id}", headers=headers)
                        status.raise_for_status()
                        state = status.json().get("status")
                        if state == "done": break
                        if state in {"error", "expired"}: raise RuntimeError(f"AppEEARS: {state}")
                        time.sleep(5)
                    else: raise TimeoutError("NASA AppEEARS no terminó el trabajo dentro de 10 minutos")
                    bundle_response = client.get(f"{APPEEARS}/bundle/{task_id}", headers=headers)
                    bundle_response.raise_for_status()
                    bundle = bundle_response.json()
                    item = next(item for item in bundle["files"] if item["file_name"].lower().endswith(".csv"))
                    response = client.get(f"{APPEEARS}/bundle/{task_id}/{item['file_id']}", headers=headers)
                    response.raise_for_status(); output.write_bytes(response.content)
            except httpx.TimeoutException as error:
                raise TimeoutError(
                    "NASA AppEEARS no respondió a tiempo durante la consulta MODIS. "
                    "Verificá la conexión y reintentá; el trabajo conserva su estado."
                ) from error
            except httpx.HTTPStatusError as error:
                raise RuntimeError(
                    f"NASA AppEEARS respondió con HTTP {error.response.status_code} durante la consulta MODIS"
                ) from error
        rows = list(csv.DictReader(output.open(encoding="utf-8-sig")))
        if not rows: raise ValueError("AppEEARS devolvió un CSV vacío")
        value_key = next(key for key in rows[0] if "Albedo_WSA_shortwave" in key)
        qa_key = next(key for key in rows[0] if "Mandatory_Quality_shortwave" in key)
        values = [float(row[value_key]) for row in rows
                  if row.get(value_key) not in {None, "", "NA"}
                  and row.get(qa_key) not in {None, "", "NA"} and int(float(row[qa_key])) <= 1]
        if not values: raise ValueError("MODIS no devolvió observaciones válidas")
        return {"value": float(np.mean(values)), "count": len(values)}

    def _bowen(self, latitude: float, longitude: float, start: date, end: date,
               directory: Path) -> dict:
        if not self.settings.cdsapi_key: raise ValueError("Falta CDSAPI_KEY")
        output = directory / "era5-land-fluxes.nc"
        if not output.exists():
            try:
                cdsapi.Client(url=self.settings.cdsapi_url, key=self.settings.cdsapi_key,
                              quiet=True, timeout=300).retrieve("reanalysis-era5-land", {
                    "variable": ["surface_sensible_heat_flux", "surface_latent_heat_flux"],
                    "year": str(end.year), "month": [f"{start.month:02d}", f"{end.month:02d}"],
                    "day": [f"{day:02d}" for day in range(1, 32)],
                    "time": [f"{hour:02d}:00" for hour in range(24)],
                    "data_format": "netcdf", "download_format": "unarchived",
                    "area": [latitude + .05, longitude - .05, latitude - .05, longitude + .05],
                }, str(output))
            except Exception as error:
                if "timeout" in type(error).__name__.lower() or "timed out" in str(error).lower():
                    raise TimeoutError(
                        "Copernicus CDS no respondió a tiempo durante la descarga ERA5-Land. "
                        "Verificá la conexión y reintentá."
                    ) from error
                raise RuntimeError(
                    f"Copernicus CDS no pudo obtener ERA5-Land ({type(error).__name__})"
                ) from error
        with Dataset(output) as dataset:
            sensible = next(np.asarray(dataset.variables[name][:], dtype=float) for name in dataset.variables
                            if name.lower() in {"sshf", "surface_sensible_heat_flux"})
            latent = next(np.asarray(dataset.variables[name][:], dtype=float) for name in dataset.variables
                          if name.lower() in {"slhf", "surface_latent_heat_flux"})
        valid = np.isfinite(sensible) & np.isfinite(latent) & (np.abs(latent) > 1e-9)
        if not valid.any(): raise ValueError("ERA5-Land no devolvió flujos válidos")
        return {"value": abs(float(sensible[valid].sum() / latent[valid].sum())),
                "count": int(valid.sum())}

    def _roughness(self, latitude: float, longitude: float, directory: Path, *,
                   season: str = "winter_no_snow", airport: bool = False) -> list[dict]:
        tile = worldcover_tile(latitude, longitude)
        raster, xyz = directory / f"worldcover-{tile}.tif", directory / f"worldcover-{tile}.xyz"
        if not raster.exists():
            url = ("https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
                   f"ESA_WorldCover_10m_2021_v200_{tile}_Map.tif")
            dlat, dlon = .012, .012 / max(math.cos(math.radians(latitude)), .2)
            try:
                subprocess.run(["gdal_translate", "-projwin", str(longitude-dlon), str(latitude+dlat),
                                str(longitude+dlon), str(latitude-dlat), url, str(raster)],
                               check=True, capture_output=True, text=True, timeout=300)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError(
                    "ESA WorldCover no respondió a tiempo durante la descarga de cobertura"
                ) from error
            except subprocess.CalledProcessError as error:
                raise RuntimeError("ESA WorldCover no pudo descargar la cobertura del suelo") from error
        if not xyz.exists():
            subprocess.run(["gdal_translate", "-of", "XYZ", str(raster), str(xyz)],
                           check=True, capture_output=True, text=True, timeout=120)
        points = []
        with xyz.open() as stream:
            for line in stream:
                lon, lat, value = line.split(); points.append((float(lon), float(lat), int(float(value))))
        return directional_roughness(
            points, latitude, longitude, season=season, airport=airport
        )
