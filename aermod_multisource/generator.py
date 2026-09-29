from __future__ import annotations

from aermod_hourly.generator import PROFILE_FILE, SURFACE_FILE
from aermod_screening.generator import aermod_ascii
from aermod_screening.generator import TerrainReceptor

from .geometry import MultiSourceGeometry
from .models import MultiSourceHourlyScenario
from .terrain import TerrainSource


SHORT_TERM_PERIODS = (1, 3, 8, 24)
RANK_FILES = {period: f"MULTI_{period}H.FIL" for period in SHORT_TERM_PERIODS}
PLOT_FILES = {period: f"MULTI_{period}H.PLT" for period in SHORT_TERM_PERIODS}
ANNUAL_PLOT_FILE = "MULTI_ANNUAL.PLT"


def generate_aermod_input(
    scenario: MultiSourceHourlyScenario,
    station,
    geometry: MultiSourceGeometry,
    *,
    terrain_sources: dict[str, TerrainSource] | None = None,
    terrain_receptors: list[TerrainReceptor] | None = None,
) -> str:
    year = scenario.meteorology.year
    position_by_id = {position.source_id: position for position in geometry.sources}
    elevated = terrain_sources is not None and terrain_receptors is not None
    if elevated and set(terrain_sources) != set(position_by_id):
        raise ValueError("Las fuentes procesadas por AERMAP no coinciden con el escenario")
    lines = [
        "CO STARTING",
        f"   TITLEONE {aermod_ascii(scenario.name)}",
        "   TITLETWO MULTIPLE POINT SOURCES - OBSERVED HOURLY METEOROLOGY",
        f"   MODELOPT CONC {'ELEV' if elevated else 'FLAT'}",
        "   AVERTIME 1 3 8 24 ANNUAL",
        f"   POLLUTID {scenario.pollutant_id}",
    ]
    if scenario.dispersion_mode == "urban":
        lines.append(f"   URBANOPT {scenario.urban_population}")
    if scenario.receptors.receptor_height_m > 0:
        lines.append(f"   FLAGPOLE {scenario.receptors.receptor_height_m:.2f}")
    lines.extend(["   RUNORNOT RUN", "CO FINISHED", "", "SO STARTING"])
    for source in scenario.sources:
        position = position_by_id[source.source_id]
        terrain_source = terrain_sources[source.source_id] if elevated else None
        source_x = terrain_source.x_m if terrain_source else position.x_m
        source_y = terrain_source.y_m if terrain_source else position.y_m
        lines.extend([
            f"   LOCATION {source.source_id} POINT {source_x:.2f} {source_y:.2f}" + (
                f" {terrain_source.elevation_m:.2f}" if terrain_source else ""
            ),
            (
                f"   SRCPARAM {source.source_id} {source.emission_rate_g_s:.6g} "
                f"{source.stack_height_m:.6g} {source.stack_temperature_k:.6g} "
                f"{source.exit_velocity_m_s:.6g} {source.stack_diameter_m:.6g}"
            ),
        ])
        if scenario.dispersion_mode == "urban":
            lines.append(f"   URBANSRC {source.source_id}")
    lines.extend(["   SRCGROUP ALL", "SO FINISHED", "", "RE STARTING"])
    if elevated:
        lines.append("   ELEVUNIT METERS")
    if terrain_receptors is None:
        for x_m, y_m in scenario.receptors.receptors():
            lines.append(f"   DISCCART {x_m:.2f} {y_m:.2f}")
    else:
        for receptor in terrain_receptors:
            lines.append(
                f"   DISCCART {receptor.x:.2f} {receptor.y:.2f} "
                f"{receptor.elevation_m:.2f} {receptor.hill_height_m:.2f}"
            )
    lines.extend([
        "RE FINISHED", "", "ME STARTING",
        f"   SURFFILE {SURFACE_FILE} FREE", f"   PROFFILE {PROFILE_FILE} FREE",
        f"   SURFDATA {station.surface_station_id} {year} {station.name}",
        f"   UAIRDATA {station.upper_station_id} {year} {station.name}",
        f"   PROFBASE {station.surface_elevation_m if elevated else 0.0:.2f} METERS",
        f"   STARTEND {year} 01 01 {year} 12 31",
        "ME FINISHED", "", "OU STARTING",
        "   RECTABLE ALLAVE FIRST", "   MAXTABLE ALLAVE 50", "   FILEFORM EXP",
    ])
    for period in SHORT_TERM_PERIODS:
        lines.append(f"   RANKFILE {period} 10 {RANK_FILES[period]}")
        lines.append(f"   PLOTFILE {period} ALL FIRST {PLOT_FILES[period]}")
    lines.extend([
        f"   PLOTFILE ANNUAL ALL {ANNUAL_PLOT_FILE}",
        "OU FINISHED", "",
    ])
    return "\n".join(lines)
