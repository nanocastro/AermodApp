from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import Path

from aermod_screening.generator import TerrainReceptor

from .geometry import MultiSourceGeometry
from .models import MultiSourceHourlyScenario


@dataclass(frozen=True)
class TerrainSource:
    source_id: str
    x_m: float
    y_m: float
    elevation_m: float


def domain_margin_m(
    scenario: MultiSourceHourlyScenario, geometry: MultiSourceGeometry
) -> float:
    source_extent = max(
        math.hypot(position.x_m, position.y_m) for position in geometry.sources
    )
    receptor_extent = max(scenario.receptors.distances())
    return max(5000.0, (source_extent + receptor_extent) * 1.5)


def generate_multisource_aermap_input(
    terrain_filename: str,
    scenario: MultiSourceHourlyScenario,
    geometry: MultiSourceGeometry,
) -> str:
    signed_zone = -geometry.zone if geometry.hemisphere == "south" else geometry.zone
    margin = domain_margin_m(scenario, geometry)
    lines = [
        "CO STARTING",
        "   TITLEONE MULTISOURCE TERRAIN PREPARATION",
        "   TERRHGTS EXTRACT",
        "   DATATYPE NED",
        f"   DATAFILE {terrain_filename}",
        (
            f"   DOMAINXY {geometry.center_x_m-margin:.2f} "
            f"{geometry.center_y_m-margin:.2f} {signed_zone} "
            f"{geometry.center_x_m+margin:.2f} "
            f"{geometry.center_y_m+margin:.2f} {signed_zone}"
        ),
        (
            f"   ANCHORXY {geometry.center_x_m:.2f} {geometry.center_y_m:.2f} "
            f"{geometry.center_x_m:.2f} {geometry.center_y_m:.2f} "
            f"{signed_zone} 0"
        ),
        "   RUNORNOT RUN",
        "CO FINISHED",
        "",
        "SO STARTING",
    ]
    for position in geometry.sources:
        lines.append(
            f"   LOCATION {position.source_id} POINT "
            f"{geometry.center_x_m + position.x_m:.2f} "
            f"{geometry.center_y_m + position.y_m:.2f}"
        )
    lines.extend(["SO FINISHED", "", "RE STARTING"])
    for x_m, y_m in scenario.receptors.receptors():
        lines.append(
            f"   DISCCART {geometry.center_x_m + x_m:.2f} "
            f"{geometry.center_y_m + y_m:.2f}"
        )
    lines.extend([
        "RE FINISHED", "", "OU STARTING",
        "   RECEPTOR receptors-aermap.out",
        "   SOURCLOC source-aermap.out",
        "OU FINISHED", "",
    ])
    return "\n".join(lines)


def read_multisource_aermap(
    terrain_directory: Path,
) -> tuple[dict[str, TerrainSource], list[TerrainReceptor]]:
    sources: dict[str, TerrainSource] = {}
    for line in (terrain_directory / "source-aermap.out").read_text(
        encoding="latin-1"
    ).splitlines():
        match = re.match(
            r"\s*SO LOCATION\s+(\S+)\s+POINT\s+([-0-9.]+)\s+"
            r"([-0-9.]+)\s+([-0-9.]+)",
            line,
        )
        if match:
            source_id, x_m, y_m, elevation_m = match.groups()
            sources[source_id] = TerrainSource(
                source_id, float(x_m), float(y_m), float(elevation_m)
            )
    if not sources:
        raise RuntimeError("AERMAP no produjo fuentes multifuente utilizables")
    receptors: list[TerrainReceptor] = []
    for line in (terrain_directory / "receptors-aermap.out").read_text(
        encoding="latin-1"
    ).splitlines():
        match = re.match(
            r"\s*DISCCART\s+([-0-9.]+)\s+([-0-9.]+)\s+"
            r"([-0-9.]+)\s+([-0-9.]+)",
            line,
        )
        if match:
            receptors.append(TerrainReceptor(*(float(value) for value in match.groups())))
    if not receptors:
        raise RuntimeError("AERMAP no produjo receptores multifuente utilizables")
    return sources, receptors
