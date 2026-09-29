from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aermod_screening.executables import stage_executable
from aermod_screening.complex_engine import read_aermap
from aermod_screening.downwash import run_bpipprm_for_source

from .aermet import summarize_surface_file
from .generator import (
    ANNUAL_PLOT_FILE,
    PLOT_FILE,
    PLOT_FILES,
    PROFILE_FILE,
    RANK_FILE,
    RANK_FILES,
    SURFACE_FILE,
    generate_aermod_input,
)
from .models import (
    HourlyConcentrationPoint,
    HourlyDownwashComparison,
    HourlyMaximum,
    HourlyMeteorologicalCondition,
    HourlyPeriodMaximum,
    HourlyResult,
    HourlyScenario,
)
from .stations import HOURLY_STATIONS


def _parse_maximum(
    path: Path, utc_offset_hours: int, source_x: float = 0.0, source_y: float = 0.0
) -> HourlyMaximum:
    for line in path.read_text(encoding="latin-1").splitlines():
        if not re.match(r"^\s*1\s", line):
            continue
        fields = line.split()
        if len(fields) < 6:
            continue
        try:
            concentration = float(fields[1])
            timestamp = fields[2]
            x_m = float(fields[3]) - source_x
            y_m = float(fields[4]) - source_y
        except ValueError:
            continue
        bearing = math.degrees(math.atan2(x_m, y_m)) % 360
        year = 2000 + int(timestamp[:2])
        month, day, hour = int(timestamp[2:4]), int(timestamp[4:6]), int(timestamp[6:8])
        hour_ending = datetime(year, month, day, tzinfo=timezone(timedelta(hours=utc_offset_hours)))
        hour_ending += timedelta(hours=hour)
        return HourlyMaximum(
            concentration_ug_m3=concentration,
            aermod_timestamp=timestamp,
            hour_ending_local=hour_ending.isoformat(),
            x_m=x_m,
            y_m=y_m,
            distance_m=math.hypot(x_m, y_m),
            bearing_deg=bearing,
        )
    raise RuntimeError(f"No se pudo interpretar el máximo de {path.name}")


def _period_maximum(period: str, maximum: HourlyMaximum) -> HourlyPeriodMaximum:
    return HourlyPeriodMaximum(
        averaging_period=period,
        concentration_ug_m3=maximum.concentration_ug_m3,
        aermod_timestamp=maximum.aermod_timestamp,
        hour_ending_local=maximum.hour_ending_local,
        x_m=maximum.x_m,
        y_m=maximum.y_m,
        distance_m=maximum.distance_m,
        bearing_deg=maximum.bearing_deg,
    )


def _parse_annual_maximum(
    path: Path, source_x: float = 0.0, source_y: float = 0.0
) -> HourlyPeriodMaximum:
    candidates: list[tuple[float, float, float]] = []
    for line in path.read_text(encoding="latin-1").splitlines():
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        fields = line.split()
        if len(fields) < 9 or fields[6] != "ANNUAL":
            continue
        try:
            candidates.append((
                float(fields[2]), float(fields[0]) - source_x, float(fields[1]) - source_y
            ))
        except ValueError:
            continue
    if not candidates:
        raise RuntimeError(f"No se pudo interpretar el máximo anual de {path.name}")
    concentration, x_m, y_m = max(candidates)
    return HourlyPeriodMaximum(
        averaging_period="annual",
        concentration_ug_m3=concentration,
        x_m=x_m,
        y_m=y_m,
        distance_m=math.hypot(x_m, y_m),
        bearing_deg=math.degrees(math.atan2(x_m, y_m)) % 360,
    )


def _hour_ending(timestamp: str, utc_offset_hours: int) -> str:
    year = 2000 + int(timestamp[:2])
    month, day, hour = int(timestamp[2:4]), int(timestamp[4:6]), int(timestamp[6:8])
    value = datetime(year, month, day, tzinfo=timezone(timedelta(hours=utc_offset_hours)))
    return (value + timedelta(hours=hour)).isoformat()


def _optional(value: float, missing_at_or_below: float = -900) -> float | None:
    return None if value <= missing_at_or_below or value >= 90000 else value


def _parse_maximum_condition(
    surface_path: Path, maximum: HourlyMaximum, utc_offset_hours: int
) -> HourlyMeteorologicalCondition:
    stamp = maximum.aermod_timestamp
    target = (2000 + int(stamp[:2]), int(stamp[2:4]), int(stamp[4:6]), int(stamp[6:8]))
    with surface_path.open(encoding="ascii", errors="replace") as stream:
        next(stream)
        for line in stream:
            fields = line.split()
            if len(fields) < 24:
                continue
            try:
                current = (int(fields[0]), int(fields[1]), int(fields[2]), int(fields[4]))
                if current != target:
                    continue
                heat_flux = float(fields[5])
                regime = "convectiva" if heat_flux > 0.1 else "estable" if heat_flux < -0.1 else "neutral"
                return HourlyMeteorologicalCondition(
                    aermod_timestamp=stamp,
                    hour_ending_local=_hour_ending(stamp, utc_offset_hours),
                    wind_direction_deg=float(fields[16]),
                    wind_speed_m_s=float(fields[15]),
                    temperature_k=float(fields[18]),
                    friction_velocity_m_s=float(fields[6]),
                    convective_velocity_m_s=_optional(float(fields[7]), -8.9),
                    surface_heat_flux_w_m2=heat_flux,
                    convective_mixing_height_m=_optional(float(fields[9])),
                    mechanical_mixing_height_m=_optional(float(fields[10])),
                    monin_obukhov_length_m=_optional(float(fields[11])),
                    relative_humidity_percent=_optional(float(fields[22])),
                    station_pressure_mb=_optional(float(fields[23])),
                    boundary_layer_regime=regime,
                )
            except ValueError:
                continue
    raise RuntimeError(f"No se encontró la condición {stamp} en {surface_path.name}")


def _parse_concentration_surface(
    path: Path, source_x: float = 0.0, source_y: float = 0.0
) -> list[HourlyConcentrationPoint]:
    points = []
    for line in path.read_text(encoding="latin-1").splitlines():
        if not line.strip() or line.lstrip().startswith("*"):
            continue
        fields = line.split()
        if len(fields) < 10:
            continue
        try:
            points.append(HourlyConcentrationPoint(
                x_m=float(fields[0]) - source_x,
                y_m=float(fields[1]) - source_y,
                concentration_1h_ug_m3=float(fields[2]),
                aermod_timestamp=fields[-1],
            ))
        except ValueError:
            continue
    if not points:
        raise RuntimeError(f"No se pudo interpretar la superficie de {path.name}")
    return points


class HourlyEngine:
    def __init__(
        self, *, aermod_executable: Path, meteorology_root: Path,
        bpipprm_executable: Path | None = None,
    ) -> None:
        self.aermod_executable = aermod_executable.resolve()
        self.meteorology_root = meteorology_root.resolve()
        self.bpipprm_executable = (
            bpipprm_executable.resolve() if bpipprm_executable is not None else None
        )
        if not self.aermod_executable.is_file():
            raise FileNotFoundError(self.aermod_executable)

    def run(
        self, scenario: HourlyScenario, run_directory: Path, terrain_directory: Path | None = None
    ) -> HourlyResult:
        run_directory = run_directory.resolve()
        if run_directory.exists() and any(run_directory.iterdir()):
            raise FileExistsError(f"El directorio de corrida no está vacío: {run_directory}")
        run_directory.mkdir(parents=True, exist_ok=True)
        station = HOURLY_STATIONS[scenario.meteorology.station]
        year = scenario.meteorology.year
        met_directory = self.meteorology_root / station.slug / str(year)
        source_surface = met_directory / f"{station.slug}-{year}.sfc"
        source_profile = met_directory / f"{station.slug}-{year}.pfl"
        for source, target in ((source_surface, SURFACE_FILE), (source_profile, PROFILE_FILE)):
            if not source.is_file():
                raise FileNotFoundError(
                    f"Falta {source}; prepare primero la meteorología horaria con AERMET"
                )
            shutil.copy2(source, run_directory / target)

        (run_directory / "scenario.json").write_text(
            scenario.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        source_x = source_y = 0.0
        source_elevation = None
        terrain_receptors = None
        if scenario.terrain.mode == "complex":
            if terrain_directory is None or not (terrain_directory / "terrain-result.json").is_file():
                raise ValueError("Prepare el terreno del escenario antes de ejecutar")
            source_x, source_y, source_elevation, terrain_receptors = read_aermap(terrain_directory)
            shutil.copy2(terrain_directory / "terrain-result.json", run_directory / "terrain-result.json")
        building_parameters = None
        if scenario.downwash.enabled:
            if self.bpipprm_executable is None or not self.bpipprm_executable.is_file():
                raise FileNotFoundError(self.bpipprm_executable or "bpipprm")
            bpip_scenario = scenario.model_copy(deep=True)
            bpip_base_elevation = source_elevation if source_elevation is not None else 0.0
            for building in bpip_scenario.downwash.buildings:
                building.base_elevation_m = bpip_base_elevation
            building_parameters = run_bpipprm_for_source(
                name=bpip_scenario.name,
                source=bpip_scenario.source,
                buildings=bpip_scenario.downwash.buildings,
                source_base_elevation_m=bpip_base_elevation,
                directory=run_directory,
                executable=self.bpipprm_executable,
            )
            (run_directory / "building-base-elevations.json").write_text(
                json.dumps({
                    "method": (
                        "AERMAP source terrain elevation"
                        if source_elevation is not None else
                        "Co-planar source and buildings in flat terrain"
                    ),
                    "source_base_elevation_m": bpip_base_elevation,
                    "buildings": {
                        building.building_id: bpip_base_elevation
                        for building in bpip_scenario.downwash.buildings
                    },
                    "assumption": (
                        "Buildings share the source terrain elevation; physical heights "
                        "and plan geometry remain user inputs."
                    ),
                }, indent=2) + "\n",
                encoding="utf-8",
            )
        (run_directory / "aermod.inp").write_text(
            generate_aermod_input(
                scenario, station, source_x=source_x, source_y=source_y,
                source_elevation_m=source_elevation, terrain_receptors=terrain_receptors,
                building_parameters=building_parameters,
            ), encoding="ascii"
        )
        aermod = stage_executable(self.aermod_executable, run_directory)
        with (run_directory / "aermod.stdout").open("w", encoding="utf-8") as output:
            completed = subprocess.run(
                [str(aermod)], cwd=run_directory, stdout=output,
                stderr=subprocess.STDOUT, timeout=1800, check=False,
            )
        output_path = run_directory / "aermod.out"
        output_text = output_path.read_text(encoding="latin-1") if output_path.is_file() else ""
        successful = "AERMOD Finishes Successfully" in output_text
        no_fatal = re.search(r"FATAL ERROR MESSAGES[\s*]+NONE", output_text) is not None
        if completed.returncode != 0 or not successful or not no_fatal:
            raise RuntimeError(
                f"AERMOD horario falló (código {completed.returncode}); consulte aermod.out"
            )
        surface_summary = summarize_surface_file(run_directory / SURFACE_FILE)
        maximum = _parse_maximum(
            run_directory / RANK_FILE, station.utc_offset_hours, source_x, source_y
        )
        period_maxima = [_period_maximum("1h", maximum)]
        for period in (3, 8, 24):
            period_maxima.append(_period_maximum(
                f"{period}h",
                _parse_maximum(
                    run_directory / RANK_FILES[period], station.utc_offset_hours,
                    source_x, source_y,
                ),
            ))
        period_maxima.append(_parse_annual_maximum(
            run_directory / ANNUAL_PLOT_FILE, source_x, source_y
        ))
        downwash_comparison: list[HourlyDownwashComparison] = []
        if building_parameters:
            baseline_directory = run_directory / "without-downwash"
            baseline_directory.mkdir()
            for filename in (SURFACE_FILE, PROFILE_FILE):
                shutil.copy2(run_directory / filename, baseline_directory / filename)
            (baseline_directory / "aermod.inp").write_text(
                generate_aermod_input(
                    scenario,
                    station,
                    source_x=source_x,
                    source_y=source_y,
                    source_elevation_m=source_elevation,
                    terrain_receptors=terrain_receptors,
                    building_parameters=None,
                ),
                encoding="ascii",
            )
            baseline_aermod = stage_executable(
                self.aermod_executable, baseline_directory
            )
            with (baseline_directory / "aermod.stdout").open(
                "w", encoding="utf-8"
            ) as output:
                baseline_completed = subprocess.run(
                    [str(baseline_aermod)], cwd=baseline_directory, stdout=output,
                    stderr=subprocess.STDOUT, timeout=1800, check=False,
                )
            baseline_output = (baseline_directory / "aermod.out").read_text(
                encoding="latin-1"
            )
            if (
                baseline_completed.returncode != 0
                or "AERMOD Finishes Successfully" not in baseline_output
                or re.search(r"FATAL ERROR MESSAGES[\s*]+NONE", baseline_output) is None
            ):
                raise RuntimeError(
                    "El control horario sin downwash falló; consulte without-downwash/aermod.out"
                )
            baseline_maximum = _parse_maximum(
                baseline_directory / RANK_FILE, station.utc_offset_hours,
                source_x, source_y,
            )
            baseline_periods = [_period_maximum("1h", baseline_maximum)]
            for period in (3, 8, 24):
                baseline_periods.append(_period_maximum(
                    f"{period}h",
                    _parse_maximum(
                        baseline_directory / RANK_FILES[period],
                        station.utc_offset_hours, source_x, source_y,
                    ),
                ))
            baseline_periods.append(_parse_annual_maximum(
                baseline_directory / ANNUAL_PLOT_FILE, source_x, source_y
            ))
            for with_downwash, without_downwash in zip(
                period_maxima, baseline_periods, strict=True
            ):
                difference = (
                    with_downwash.concentration_ug_m3
                    - without_downwash.concentration_ug_m3
                )
                baseline_value = without_downwash.concentration_ug_m3
                downwash_comparison.append(HourlyDownwashComparison(
                    averaging_period=with_downwash.averaging_period,
                    with_downwash_ug_m3=with_downwash.concentration_ug_m3,
                    without_downwash_ug_m3=baseline_value,
                    difference_ug_m3=difference,
                    change_percent=(difference / baseline_value * 100) if baseline_value else None,
                    ratio=(with_downwash.concentration_ug_m3 / baseline_value) if baseline_value else None,
                ))
            (run_directory / "downwash-comparison.json").write_text(
                json.dumps({
                    "method": (
                        "Misma fuente, meteorología cronológica, terreno y receptores; "
                        "solo se retiran los parámetros PRIME de BPIPPRM."
                    ),
                    "periods": [item.model_dump() for item in downwash_comparison],
                }, indent=2) + "\n",
                encoding="utf-8",
            )
            for name in (
                "aermod.inp", "aermod.out", "aermod.stdout",
                *RANK_FILES.values(), *PLOT_FILES.values(), ANNUAL_PLOT_FILE,
            ):
                source_path = baseline_directory / name
                if source_path.is_file():
                    shutil.copy2(
                        source_path, run_directory / f"without-downwash-{name}"
                    )
        concentration_surface = _parse_concentration_surface(
            run_directory / PLOT_FILE, source_x, source_y
        )
        result = HourlyResult(
            status="completed",
            station=station.slug,
            year=year,
            receptor_count=len(scenario.receptors.receptors()),
            terrain_mode=scenario.terrain.mode,
            source_elevation_m=source_elevation,
            downwash_enabled=scenario.downwash.enabled,
            downwash_comparison=downwash_comparison,
            maximum_1h=maximum,
            period_maxima=period_maxima,
            maximum_condition=_parse_maximum_condition(
                run_directory / SURFACE_FILE, maximum, station.utc_offset_hours
            ),
            maximum_1h_by_receptor=concentration_surface,
            meteorology_total_hours=surface_summary["total_hours"],
            meteorology_usable_hours=surface_summary["usable_hours"],
            meteorology_usable_percent=surface_summary["usable_percent"],
            aermod_finished_successfully=successful,
            no_fatal_errors=no_fatal,
        )
        (run_directory / "result.json").write_text(
            json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8"
        )
        return result
