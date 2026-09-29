from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass

from aermod_screening.terrain import utm_zone

from .models import MultiSourceHourlyScenario, MultiSourcePosition


@dataclass(frozen=True)
class MultiSourceGeometry:
    center_latitude_deg: float
    center_longitude_deg: float
    zone: int
    hemisphere: str
    center_x_m: float
    center_y_m: float
    sources: list[MultiSourcePosition]


def build_geometry(scenario: MultiSourceHourlyScenario) -> MultiSourceGeometry:
    center_latitude = sum(source.latitude_deg for source in scenario.sources if source.latitude_deg is not None) / len(scenario.sources)
    center_longitude = sum(source.longitude_deg for source in scenario.sources if source.longitude_deg is not None) / len(scenario.sources)
    zone = utm_zone(center_longitude)
    epsg = 32600 + zone if center_latitude >= 0 else 32700 + zone
    executable = shutil.which("gdaltransform")
    if not executable:
        raise RuntimeError("gdaltransform no está disponible")
    coordinates = [(center_longitude, center_latitude), *[
        (source.longitude_deg, source.latitude_deg) for source in scenario.sources
    ]]
    completed = subprocess.run(
        [executable, "-s_srs", "EPSG:4326", "-t_srs", f"EPSG:{epsg}"],
        input="".join(f"{longitude} {latitude}\n" for longitude, latitude in coordinates),
        capture_output=True, text=True, check=True,
    )
    transformed = [tuple(map(float, line.split()[:2])) for line in completed.stdout.splitlines()]
    if len(transformed) != len(coordinates):
        raise RuntimeError("No se pudieron transformar todas las fuentes a UTM")
    center_x, center_y = transformed[0]
    positions = [
        MultiSourcePosition(
            source_id=source.source_id,
            latitude_deg=source.latitude_deg,
            longitude_deg=source.longitude_deg,
            x_m=easting - center_x,
            y_m=northing - center_y,
        )
        for source, (easting, northing) in zip(scenario.sources, transformed[1:])
    ]
    return MultiSourceGeometry(
        center_latitude_deg=center_latitude,
        center_longitude_deg=center_longitude,
        zone=zone,
        hemisphere="north" if center_latitude >= 0 else "south",
        center_x_m=center_x,
        center_y_m=center_y,
        sources=positions,
    )
