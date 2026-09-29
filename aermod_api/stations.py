from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from typing import Callable

import httpx
import numpy as np

from .surface import last_complete_months


SMN_HOURLY_URL = "https://ssl.smn.gob.ar/dpd/descarga_opendata.php?file=observaciones/datohorario{day}.txt"
STATION_REGIONS = (
    {
        "name": "Mendoza",
        "stations": (
            {"code": "87418", "name": "Mendoza Aero", "smn_name": "MENDOZA AERO", "latitude_deg": -32.83, "longitude_deg": -68.78, "elevation_m": 705.0},
            {"code": "87420", "name": "Mendoza Observatorio", "smn_name": "MENDOZA OBSERVATORIO", "latitude_deg": -32.89, "longitude_deg": -68.87, "elevation_m": 827.0},
        ),
    },
    {
        "name": "Córdoba",
        "stations": (
            {"code": "87344", "name": "Córdoba Aero", "smn_name": "CORDOBA AERO", "latitude_deg": -31.32, "longitude_deg": -64.22, "elevation_m": 474.0},
            {"code": "87345", "name": "Córdoba Observatorio", "smn_name": "CORDOBA OBSERVATORIO", "latitude_deg": -31.40, "longitude_deg": -64.18, "elevation_m": 425.0},
        ),
    },
)


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    value = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(value))


def nearest_station_region(latitude: float, longitude: float) -> dict:
    return min(
        STATION_REGIONS,
        key=lambda region: min(
            haversine_distance_km(
                latitude, longitude, station["latitude_deg"], station["longitude_deg"]
            )
            for station in region["stations"]
        ),
    )


def parse_smn_hourly(text: str, station_names: set[str]) -> list[dict]:
    observations = []
    for line in text.splitlines()[2:]:
        if len(line) < 48:
            continue
        name = line[48:].strip()
        if name not in station_names:
            continue
        fields = line[:48].split()
        if len(fields) not in {6, 7}:
            continue
        date_text, hour_text, temperature_text, humidity_text = fields[:4]
        wind_direction_text, wind_speed_text = fields[-2:]
        try:
            observations.append({
                "station": name,
                "date": date_text,
                "hour": int(hour_text),
                "temperature_c": float(temperature_text),
                "humidity_percent": float(humidity_text),
                "wind_direction_deg": float(wind_direction_text),
                "wind_speed_km_h": float(wind_speed_text),
            })
        except ValueError:
            continue
    return observations


def station_statistics(observations: list[dict], expected_hours: int) -> dict:
    temperatures = np.asarray([item["temperature_c"] for item in observations], dtype=float)
    winds = np.asarray([item["wind_speed_km_h"] / 3.6 for item in observations], dtype=float)
    if not len(temperatures) or not len(winds):
        raise ValueError("La estación no contiene temperatura y viento válidos")
    percentiles = np.percentile(winds, [1, 5, 95, 99])
    return {
        "observation_count": len(observations),
        "expected_hour_count": expected_hours,
        "coverage_percent": min(100.0, len(observations) / expected_hours * 100),
        "temperature_mean_c": float(np.mean(temperatures)),
        "temperature_min_c": float(np.min(temperatures)),
        "temperature_max_c": float(np.max(temperatures)),
        "wind_mean_m_s": float(np.mean(winds)),
        "wind_min_observed_m_s": float(np.min(winds)),
        "wind_p01_m_s": float(percentiles[0]),
        "wind_p05_m_s": float(percentiles[1]),
        "wind_p95_m_s": float(percentiles[2]),
        "wind_p99_m_s": float(percentiles[3]),
        "makemet_minimum_wind_m_s": max(float(percentiles[0]), .5),
    }


class StationService:
    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def estimate(self, latitude: float, longitude: float, progress: Callable[[int, int, str], None] | None = None) -> dict:
        start, end = last_complete_months()
        region = nearest_station_region(latitude, longitude)
        regional_stations = region["stations"]
        days = [start + timedelta(days=index) for index in range((end - start).days + 1)]
        cache = self.directory.resolve() / "smn" / f"{start}_{end}"
        cache.mkdir(parents=True, exist_ok=True)

        def load(day: date) -> str:
            path = cache / f"datohorario{day:%Y%m%d}.txt"
            if not path.exists():
                response = httpx.get(SMN_HOURLY_URL.format(day=f"{day:%Y%m%d}"), timeout=30, follow_redirects=True)
                response.raise_for_status()
                if "El archivo no existe" in response.text:
                    raise FileNotFoundError(f"SMN no publicó datos para {day.isoformat()}")
                path.write_bytes(response.content)
            return path.read_text(encoding="latin-1")

        if progress: progress(0, 3, "Descargando archivos horarios SMN")
        with ThreadPoolExecutor(max_workers=8) as pool:
            texts = list(pool.map(load, days))
        if progress: progress(1, 3, f"Filtrando estaciones SMN de {region['name']}")
        station_names = {item["smn_name"] for item in regional_stations}
        observations = [item for text in texts for item in parse_smn_hourly(text, station_names)]
        expected_hours = len(days) * 24
        stations = []
        for metadata in regional_stations:
            station_observations = [item for item in observations if item["station"] == metadata["smn_name"]]
            stations.append({
                **{key: value for key, value in metadata.items() if key != "smn_name"},
                "distance_to_source_km": haversine_distance_km(latitude, longitude, metadata["latitude_deg"], metadata["longitude_deg"]),
                **station_statistics(station_observations, expected_hours),
            })
        combined = station_statistics(observations, expected_hours * len(regional_stations))
        if progress: progress(2, 3, "Calculando estadísticas y percentiles")
        result = {
            "region": region["name"],
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "source": "Servicio Meteorológico Nacional — datos horarios abiertos",
            "stations": stations,
            "combined": combined,
            "warnings": [f"Se seleccionó automáticamente la red regional de {region['name']} por proximidad a la fuente.",
                         "Las observaciones de estación no representan necesariamente las condiciones exactas en la fuente.",
                         "El promedio combinado pondera cada observación válida; revise cobertura y distancia antes de aplicarlo."],
        }
        if progress: progress(3, 3, "Estadísticas SMN listas")
        return result
