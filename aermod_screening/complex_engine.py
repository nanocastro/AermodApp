from __future__ import annotations

import json
import math
import re
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .generator import TerrainReceptor, generate_complex_aermod_input, generate_makemet_prompts
from .downwash import run_bpipprm
from .executables import stage_executable
from .models import ConcentrationPoint, ScreeningResult, ScreeningScenario, SectorResult
from .parser import _parse_maximum, parse_maximum_condition


def read_aermap(terrain_directory: Path) -> tuple[float, float, float, list[TerrainReceptor]]:
    source_text = (terrain_directory / "source-aermap.out").read_text(encoding="latin-1")
    source = re.search(
        r"SO LOCATION\s+\S+\s+POINT\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)", source_text
    )
    if not source:
        raise RuntimeError("No se pudo leer la fuente procesada por AERMAP")
    receptors: list[TerrainReceptor] = []
    for line in (terrain_directory / "receptors-aermap.out").read_text(encoding="latin-1").splitlines():
        match = re.match(r"\s*DISCCART\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)\s+([-0-9.]+)", line)
        if match:
            receptors.append(TerrainReceptor(*(float(value) for value in match.groups())))
    if not receptors:
        raise RuntimeError("AERMAP no produjo receptores utilizables")
    return float(source.group(1)), float(source.group(2)), float(source.group(3)), receptors


class ComplexTerrainEngine:
    def __init__(self, *, aermod_executable: Path, makemet_executable: Path, bpipprm_executable: Path | None = None) -> None:
        self.aermod = aermod_executable.resolve()
        self.makemet = makemet_executable.resolve()
        self.bpipprm = bpipprm_executable.resolve() if bpipprm_executable else None

    def run(self, scenario: ScreeningScenario, run_directory: Path, terrain_directory: Path, progress: Callable[[int, int, str], None] | None = None) -> ScreeningResult:
        run_directory.mkdir(parents=True, exist_ok=False)
        source_x, source_y, source_elevation, receptors = read_aermap(terrain_directory)
        (run_directory / "scenario.json").write_text(scenario.model_dump_json(indent=2) + "\n", encoding="utf-8")
        shutil.copy2(terrain_directory / "terrain-result.json", run_directory / "terrain-result.json")
        building_parameters = None
        if scenario.downwash.enabled:
            if self.bpipprm is None or not self.bpipprm.is_file():
                raise FileNotFoundError(self.bpipprm or "bpipprm")
            bpip_scenario = scenario.model_copy(deep=True)
            bpip_scenario.receptors.base_elevation_m = source_elevation
            for building in bpip_scenario.downwash.buildings:
                building.base_elevation_m = source_elevation
            (run_directory / "building-base-elevations.json").write_text(json.dumps({
                "method": "AERMAP source terrain elevation",
                "source_base_elevation_m": source_elevation,
                "buildings": {building.building_id: source_elevation for building in bpip_scenario.downwash.buildings},
                "assumption": "Buildings share the source terrain elevation; physical heights remain user inputs.",
            }, indent=2) + "\n", encoding="utf-8")
            building_parameters = run_bpipprm(bpip_scenario, run_directory, self.bpipprm)
        maxima: list[tuple[float, float, int, Path]] = []
        baseline_maxima: list[float] = []
        total = 72 if building_parameters else 36
        completed = 0
        curve: dict[float, float] = {}
        for direction in range(0, 360, 10):
            sector = run_directory / f"sector-{direction:03d}"
            sector.mkdir()
            directional = scenario.model_copy(deep=True)
            directional.meteorology.wind_direction_deg = direction
            plume_direction = (direction + 180) % 360
            directional_receptors = [receptor for receptor in receptors if math.isclose(
                math.degrees(math.atan2(receptor.x - source_x, receptor.y - source_y)) % 360,
                plume_direction, abs_tol=0.2,
            )]
            if not directional_receptors:
                raise RuntimeError(f"No hay receptores AERMAP para el sector {direction}")
            (sector / "prompts.inp").write_text(generate_makemet_prompts(directional), encoding="ascii")
            (sector / "aermod.inp").write_text(
                generate_complex_aermod_input(
                    directional, source_x=source_x, source_y=source_y,
                    source_elevation_m=source_elevation, receptors=directional_receptors,
                    building_parameters=building_parameters,
                ), encoding="ascii",
            )
            aermod = stage_executable(self.aermod, sector)
            makemet = stage_executable(self.makemet, sector)
            with (sector / "prompts.inp").open("r", encoding="ascii") as stdin, (sector / "makemet.stdout").open("w") as stdout:
                subprocess.run([str(makemet)], cwd=sector, stdin=stdin, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=120)
            with (sector / "aermod.stdout").open("w") as stdout:
                subprocess.run([str(aermod)], cwd=sector, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=300)
            maximum, _ = _parse_maximum(sector / "SCREENING.FIL")
            sector_points: list[tuple[float, float]] = []
            for line in (sector / "SCREENING.PLT").read_text(encoding="latin-1").splitlines():
                fields = line.split()
                if len(fields) < 3:
                    continue
                try:
                    x, y, concentration = map(float, fields[:3])
                except ValueError:
                    continue
                distance = round(math.hypot(x - source_x, y - source_y), 1)
                curve[distance] = max(curve.get(distance, 0.0), concentration)
                sector_points.append((concentration, distance))
            distance = max(sector_points)[1]
            maxima.append((maximum, distance, direction, sector))
            completed += 1
            if progress:
                progress(completed, total, f"Sector {direction:03d}° con downwash" if building_parameters else f"Sector {direction:03d}°")
            if building_parameters:
                baseline = run_directory / f"baseline-{direction:03d}"
                baseline.mkdir()
                (baseline / "prompts.inp").write_text(generate_makemet_prompts(directional), encoding="ascii")
                (baseline / "aermod.inp").write_text(generate_complex_aermod_input(
                    directional, source_x=source_x, source_y=source_y,
                    source_elevation_m=source_elevation, receptors=directional_receptors,
                ), encoding="ascii")
                baseline_aermod = stage_executable(self.aermod, baseline)
                baseline_makemet = stage_executable(self.makemet, baseline)
                with (baseline / "prompts.inp").open("r", encoding="ascii") as stdin, (baseline / "makemet.stdout").open("w") as stdout:
                    subprocess.run([str(baseline_makemet)], cwd=baseline, stdin=stdin, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=120)
                with (baseline / "aermod.stdout").open("w") as stdout:
                    subprocess.run([str(baseline_aermod)], cwd=baseline, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=300)
                baseline_maxima.append(_parse_maximum(baseline / "SCREENING.FIL")[0])
                completed += 1
                if progress:
                    progress(completed, total, f"Sector {direction:03d}° control sin downwash")
        maximum, distance, direction, winning = max(maxima)
        maximum_sectors = [
            float(sector_direction) for sector_maximum, _, sector_direction, _ in maxima
            if math.isclose(sector_maximum, maximum, rel_tol=1e-6, abs_tol=1e-8)
        ]
        baseline_maximum = max(baseline_maxima) if baseline_maxima else None
        difference = maximum - baseline_maximum if baseline_maximum is not None else None
        for name in ("aermod.inp", "aermod.out", "SCREENING.FIL", "SCREENING.PLT", "makemet.stdout", "aermod.stdout"):
            shutil.copy2(winning / name, run_directory / name)
        result = ScreeningResult(
            status="completed", maximum_1h_ug_m3=maximum, maximum_distance_m=distance,
            maximum_direction_deg=float(direction) if len(maximum_sectors) == 1 else None,
            maximum_sectors_deg=maximum_sectors, scaled_3h_ug_m3=maximum,
            scaled_8h_ug_m3=maximum * 0.9, scaled_24h_ug_m3=maximum * 0.6,
            scaled_annual_ug_m3=maximum * 0.1, aermod_finished_successfully=True,
            no_fatal_errors=True,
            concentration_by_distance=[ConcentrationPoint(distance_m=d, concentration_1h_ug_m3=c) for d, c in sorted(curve.items())],
            sector_results=[
                SectorResult(wind_direction_deg=sector_direction, maximum_1h_ug_m3=sector_maximum, maximum_distance_m=sector_distance)
                for sector_maximum, sector_distance, sector_direction, _ in sorted(maxima, key=lambda item: item[2])
            ],
            maximum_condition=parse_maximum_condition(
                winning / "SCREENING.FIL", winning / "screening.sfc"
            ),
            without_downwash_maximum_1h_ug_m3=baseline_maximum,
            downwash_difference_1h_ug_m3=difference,
            downwash_change_percent=(difference / baseline_maximum * 100) if baseline_maximum else None,
            downwash_ratio=(maximum / baseline_maximum) if baseline_maximum else None,
        )
        (run_directory / "result.json").write_text(json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8")
        return result
