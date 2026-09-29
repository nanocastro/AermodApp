from __future__ import annotations

from aermod_screening.generator import aermod_ascii
from aermod_screening.generator import TerrainReceptor

from .models import HourlyScenario
from .stations import HourlyStation


SURFACE_FILE = "hourly.sfc"
PROFILE_FILE = "hourly.pfl"
RANK_FILE = "HOURLY.FIL"
PLOT_FILE = "HOURLY.PLT"
SHORT_TERM_PERIODS = (1, 3, 8, 24)
RANK_FILES = {period: RANK_FILE if period == 1 else f"HOURLY_{period}H.FIL" for period in SHORT_TERM_PERIODS}
PLOT_FILES = {period: PLOT_FILE if period == 1 else f"HOURLY_{period}H.PLT" for period in SHORT_TERM_PERIODS}
ANNUAL_PLOT_FILE = "HOURLY_ANNUAL.PLT"


def generate_aermod_input(
    scenario: HourlyScenario,
    station: HourlyStation,
    *,
    source_x: float = 0.0,
    source_y: float = 0.0,
    source_elevation_m: float | None = None,
    terrain_receptors: list[TerrainReceptor] | None = None,
    building_parameters: dict[str, list[float]] | None = None,
) -> str:
    source = scenario.source
    year = scenario.meteorology.year
    elevated = terrain_receptors is not None
    lines = [
        "CO STARTING",
        f"   TITLEONE {aermod_ascii(scenario.name)}",
        "   TITLETWO OBSERVED HOURLY METEOROLOGY - NOAA/AERMET",
        f"   MODELOPT CONC {'ELEV' if elevated else 'FLAT'}",
        "   AVERTIME 1 3 8 24 ANNUAL",
        f"   POLLUTID {scenario.pollutant_id}",
    ]
    if scenario.dispersion_mode == "urban":
        lines.append(f"   URBANOPT {scenario.urban_population}")
    if scenario.receptors.receptor_height_m > 0:
        lines.append(f"   FLAGPOLE {scenario.receptors.receptor_height_m:.2f}")
    lines.extend([
        "   RUNORNOT RUN",
        "CO FINISHED",
        "",
        "SO STARTING",
        f"   LOCATION {source.source_id} POINT {source_x:.2f} {source_y:.2f}" + (
            f" {source_elevation_m:.2f}" if elevated and source_elevation_m is not None else ""
        ),
        (
            f"   SRCPARAM {source.source_id} {source.emission_rate_g_s:.6g} "
            f"{source.stack_height_m:.6g} {source.stack_temperature_k:.6g} "
            f"{source.exit_velocity_m_s:.6g} {source.stack_diameter_m:.6g}"
        ),
    ])
    if scenario.dispersion_mode == "urban":
        lines.append(f"   URBANSRC {source.source_id}")
    if building_parameters:
        from aermod_screening.downwash import building_parameter_lines
        lines.extend(building_parameter_lines(source.source_id, building_parameters))
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
        "RE FINISHED",
        "",
        "ME STARTING",
        f"   SURFFILE {SURFACE_FILE} FREE",
        f"   PROFFILE {PROFILE_FILE} FREE",
        f"   SURFDATA {station.surface_station_id} {year} {station.name}",
        f"   UAIRDATA {station.upper_station_id} {year} {station.name}",
        f"   PROFBASE {(source_elevation_m or 0.0):.2f} METERS",
        f"   STARTEND {year} 01 01 {year} 12 31",
        "ME FINISHED",
        "",
        "OU STARTING",
        "   RECTABLE ALLAVE FIRST",
        "   MAXTABLE ALLAVE 50",
        "   FILEFORM EXP",
    ])
    for period in SHORT_TERM_PERIODS:
        lines.append(f"   RANKFILE {period} 10 {RANK_FILES[period]}")
        lines.append(f"   PLOTFILE {period} ALL FIRST {PLOT_FILES[period]}")
    lines.extend([
        f"   PLOTFILE ANNUAL ALL {ANNUAL_PLOT_FILE}",
        "OU FINISHED",
        "",
    ])
    return "\n".join(lines)
