from __future__ import annotations

import re
from pathlib import Path

from .models import ConcentrationPoint, MeteorologicalCondition, ScreeningResult


def _parse_maximum(rank_file: Path) -> tuple[float, float]:
    for line in rank_file.read_text(encoding="latin-1").splitlines():
        match = re.match(r"\s*1\s+([0-9.E+-]+)\s+\d{8}\s+([0-9.-]+)", line)
        if match:
            return float(match.group(1)), float(match.group(2))
    raise RuntimeError("No se pudo interpretar el máximo de SCREENING.FIL")


def parse_maximum_condition(rank_file: Path, surface_file: Path) -> MeteorologicalCondition | None:
    rank_match = re.search(r"^\s*1\s+[0-9.E+-]+\s+(\d{8})", rank_file.read_text(encoding="latin-1"), re.MULTILINE)
    if not rank_match or not surface_file.is_file():
        return None
    stamp = rank_match.group(1)
    year, month, day, hour = int(stamp[:2]), int(stamp[2:4]), int(stamp[4:6]), int(stamp[6:8])
    for line in surface_file.read_text(encoding="latin-1").splitlines():
        fields = line.split()
        if len(fields) < 19:
            continue
        try:
            if [int(fields[0]), int(fields[1]), int(fields[2]), int(fields[4])] != [year, month, day, hour]:
                continue
            heat_flux = float(fields[5])
            stability = "convectiva" if heat_flux > 0.1 else "estable" if heat_flux < -0.1 else "neutral"
            convective_velocity = float(fields[7])
            mixing_height = float(fields[9])
            return MeteorologicalCondition(
                synthetic_date=stamp, wind_direction_deg=float(fields[16]),
                wind_speed_m_s=float(fields[15]), temperature_k=float(fields[18]),
                friction_velocity_m_s=float(fields[6]),
                convective_velocity_m_s=None if convective_velocity <= -9 else convective_velocity,
                mixing_height_m=None if mixing_height <= -900 else mixing_height,
                stability=stability,
            )
        except ValueError:
            continue
    return None


def _parse_curve(plot_file: Path) -> list[ConcentrationPoint]:
    points: list[ConcentrationPoint] = []
    for line in plot_file.read_text(encoding="latin-1").splitlines():
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        fields = line.split()
        if len(fields) < 3:
            continue
        try:
            distance = float(fields[0])
            concentration = float(fields[2])
        except ValueError:
            continue
        points.append(
            ConcentrationPoint(
                distance_m=distance,
                concentration_1h_ug_m3=concentration,
            )
        )
    if not points:
        raise RuntimeError("No se pudo interpretar la curva de SCREENING.PLT")
    return points


def parse_result(run_directory: Path) -> ScreeningResult:
    output = (run_directory / "aermod.out").read_text(encoding="latin-1")
    successful = "AERMOD Finishes Successfully" in output
    no_fatal = re.search(r"FATAL ERROR MESSAGES[\s*]+NONE", output) is not None
    if not successful or not no_fatal:
        raise RuntimeError("AERMOD no finalizó correctamente; consulte aermod.out")

    maximum, distance = _parse_maximum(run_directory / "SCREENING.FIL")
    return ScreeningResult(
        status="completed",
        maximum_1h_ug_m3=maximum,
        maximum_distance_m=distance,
        scaled_3h_ug_m3=maximum,
        scaled_8h_ug_m3=maximum * 0.9,
        scaled_24h_ug_m3=maximum * 0.6,
        scaled_annual_ug_m3=maximum * 0.1,
        aermod_finished_successfully=successful,
        no_fatal_errors=no_fatal,
        concentration_by_distance=_parse_curve(run_directory / "SCREENING.PLT"),
        maximum_condition=parse_maximum_condition(
            run_directory / "SCREENING.FIL", run_directory / "screening.sfc"
        ),
    )
