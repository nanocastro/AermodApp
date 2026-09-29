from __future__ import annotations

import unicodedata
from dataclasses import dataclass

from .models import ScreeningScenario


SURFACE_FILE = "screening.sfc"
PROFILE_FILE = "screening.pfl"


@dataclass(frozen=True)
class TerrainReceptor:
    x: float
    y: float
    elevation_m: float
    hill_height_m: float


def aermod_ascii(value: str) -> str:
    """Convert user-facing text to the conservative ASCII accepted by AERMOD."""
    punctuation = str.maketrans({"—": "-", "–": "-", "−": "-", "“": '"', "”": '"', "’": "'"})
    normalized = unicodedata.normalize("NFKD", value.translate(punctuation))
    return normalized.encode("ascii", errors="ignore").decode("ascii")


def generate_makemet_prompts(scenario: ScreeningScenario) -> str:
    met = scenario.meteorology
    return "\n".join(
        [
            SURFACE_FILE,
            PROFILE_FILE,
            f"{met.minimum_wind_speed_m_s:.4f}",
            f"{met.anemometer_height_m:.4f}",
            "Y" if met.adjust_friction_velocity else "N",
            "1",
            f"{met.wind_direction_deg:.1f}",
            f"{met.minimum_temperature_k:.4f} {met.maximum_temperature_k:.4f}",
            f"{met.albedo:.4f}",
            f"{met.bowen_ratio:.4f}",
            f"{met.surface_roughness_m:.4f}",
            "n",
            "",
        ]
    )


def generate_aermod_input(scenario: ScreeningScenario) -> str:
    source = scenario.source
    receptors = scenario.receptors
    mode_options = "CONC SCREEN FLAT"

    lines = [
        "CO STARTING",
        f"   TITLEONE {aermod_ascii(scenario.name)}",
        "   TITLETWO GENERATED FROM STRUCTURED SCENARIO",
        f"   MODELOPT {mode_options}",
        "   AVERTIME 1",
        f"   POLLUTID {scenario.pollutant_id}",
    ]
    if scenario.dispersion_mode == "urban":
        lines.append(f"   URBANOPT {scenario.urban_population}")
    if receptors.receptor_height_m > 0:
        lines.append(f"   FLAGPOLE {receptors.receptor_height_m:.2f}")
    lines.extend(
        [
            "   RUNORNOT RUN",
            "CO FINISHED",
            "",
            "SO STARTING",
            f"   LOCATION {source.source_id} POINT 0.0 0.0",
            (
                f"   SRCPARAM {source.source_id} {source.emission_rate_g_s:.6g} "
                f"{source.stack_height_m:.6g} {source.stack_temperature_k:.6g} "
                f"{source.exit_velocity_m_s:.6g} {source.stack_diameter_m:.6g}"
            ),
        ]
    )
    if scenario.dispersion_mode == "urban":
        lines.append(f"   URBANSRC {source.source_id}")
    lines.extend(["   SRCGROUP ALL", "SO FINISHED", "", "RE STARTING"])
    for distance in receptors.distances():
        lines.append(f"   DISCCART {distance:.2f} 0.00")
    lines.extend(
        [
            "RE FINISHED",
            "",
            "ME STARTING",
            f"   SURFFILE {SURFACE_FILE} FREE",
            f"   PROFFILE {PROFILE_FILE} FREE",
            "   SURFDATA 11111 2010 SCREEN",
            "   UAIRDATA 22222 2010 SCREEN",
            f"   PROFBASE {receptors.base_elevation_m:.2f} METERS",
            "ME FINISHED",
            "",
            "OU STARTING",
            "   RECTABLE 1 FIRST",
            "   MAXTABLE ALLAVE 50",
            "   FILEFORM EXP",
            "   RANKFILE 1 10 SCREENING.FIL",
            "   PLOTFILE 1 ALL FIRST SCREENING.PLT",
            "OU FINISHED",
            "",
        ]
    )
    return "\n".join(lines)


def generate_complex_aermod_input(
    scenario: ScreeningScenario,
    *,
    source_x: float,
    source_y: float,
    source_elevation_m: float,
    receptors: list[TerrainReceptor],
    building_parameters: dict[str, list[float]] | None = None,
    elevated: bool = True,
) -> str:
    source = scenario.source
    lines = [
        "CO STARTING",
        f"   TITLEONE {aermod_ascii(scenario.name)}",
        "   TITLETWO AERMAP TERRAIN - DIRECTIONAL SCREENING",
        f"   MODELOPT CONC SCREEN {'ELEV' if elevated else 'FLAT'}",
        "   AVERTIME 1",
        f"   POLLUTID {scenario.pollutant_id}",
    ]
    if scenario.dispersion_mode == "urban":
        lines.append(f"   URBANOPT {scenario.urban_population}")
    if scenario.receptors.receptor_height_m > 0:
        lines.append(f"   FLAGPOLE {scenario.receptors.receptor_height_m:.2f}")
    lines.extend([
        "   RUNORNOT RUN", "CO FINISHED", "", "SO STARTING",
        f"   LOCATION {source.source_id} POINT {source_x:.2f} {source_y:.2f}" + (f" {source_elevation_m:.2f}" if elevated else ""),
        (
            f"   SRCPARAM {source.source_id} {source.emission_rate_g_s:.6g} "
            f"{source.stack_height_m:.6g} {source.stack_temperature_k:.6g} "
            f"{source.exit_velocity_m_s:.6g} {source.stack_diameter_m:.6g}"
        ),
    ])
    if scenario.dispersion_mode == "urban":
        lines.append(f"   URBANSRC {source.source_id}")
    if building_parameters:
        from .downwash import building_parameter_lines
        lines.extend(building_parameter_lines(source.source_id, building_parameters))
    lines.extend(["   SRCGROUP ALL", "SO FINISHED", "", "RE STARTING"])
    if elevated:
        lines.append("   ELEVUNIT METERS")
    for receptor in receptors:
        suffix = f" {receptor.elevation_m:.2f} {receptor.hill_height_m:.2f}" if elevated else ""
        lines.append(f"   DISCCART {receptor.x:.2f} {receptor.y:.2f}{suffix}")
    lines.extend([
        "RE FINISHED", "", "ME STARTING",
        f"   SURFFILE {SURFACE_FILE} FREE", f"   PROFFILE {PROFILE_FILE} FREE",
        "   SURFDATA 11111 2010 SCREEN", "   UAIRDATA 22222 2010 SCREEN",
        f"   PROFBASE {source_elevation_m:.2f} METERS", "ME FINISHED", "",
        "OU STARTING", "   RECTABLE 1 FIRST", "   MAXTABLE ALLAVE 50",
        "   FILEFORM EXP", "   RANKFILE 1 10 SCREENING.FIL",
        "   PLOTFILE 1 ALL FIRST SCREENING.PLT", "OU FINISHED", "",
    ])
    return "\n".join(lines)
