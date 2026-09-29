from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Callable

from .downwash import run_bpipprm
from .executables import stage_executable
from .generator import TerrainReceptor, generate_complex_aermod_input, generate_makemet_prompts
from .models import ConcentrationPoint, ScreeningResult, ScreeningScenario, SectorResult
from .parser import _parse_maximum, parse_maximum_condition


class FlatDownwashEngine:
    """Directional flat-terrain screening using BPIPPRM PRIME parameters."""

    def __init__(self, *, aermod_executable: Path, makemet_executable: Path, bpipprm_executable: Path) -> None:
        self.aermod = aermod_executable.resolve()
        self.makemet = makemet_executable.resolve()
        self.bpipprm = bpipprm_executable.resolve()
        for executable in (self.aermod, self.makemet, self.bpipprm):
            if not executable.is_file():
                raise FileNotFoundError(executable)

    def run(self, scenario: ScreeningScenario, run_directory: Path, progress: Callable[[int, int, str], None] | None = None) -> ScreeningResult:
        run_directory.mkdir(parents=True, exist_ok=False)
        (run_directory / "scenario.json").write_text(scenario.model_dump_json(indent=2) + "\n", encoding="utf-8")
        parameters = run_bpipprm(scenario, run_directory, self.bpipprm)
        base = scenario.receptors.base_elevation_m
        maxima: list[tuple[float, float, int, Path]] = []
        baseline_maxima: list[float] = []
        curve: dict[float, float] = {}
        for direction in range(0, 360, 10):
            sector = run_directory / f"sector-{direction:03d}"
            sector.mkdir()
            directional = scenario.model_copy(deep=True)
            directional.meteorology.wind_direction_deg = direction
            plume_bearing = math.radians((direction + 180) % 360)
            receptors = [TerrainReceptor(
                x=distance * math.sin(plume_bearing), y=distance * math.cos(plume_bearing),
                elevation_m=base, hill_height_m=base,
            ) for distance in scenario.receptors.distances()]
            (sector / "prompts.inp").write_text(generate_makemet_prompts(directional), encoding="ascii")
            (sector / "aermod.inp").write_text(generate_complex_aermod_input(
                directional, source_x=0, source_y=0, source_elevation_m=base,
                receptors=receptors, building_parameters=parameters, elevated=False,
            ), encoding="ascii")
            aermod = stage_executable(self.aermod, sector)
            makemet = stage_executable(self.makemet, sector)
            with (sector / "prompts.inp").open("r", encoding="ascii") as stdin, (sector / "makemet.stdout").open("w") as stdout:
                subprocess.run([str(makemet)], cwd=sector, stdin=stdin, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=120)
            with (sector / "aermod.stdout").open("w") as stdout:
                subprocess.run([str(aermod)], cwd=sector, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=300)
            maximum, _ = _parse_maximum(sector / "SCREENING.FIL")
            points: list[tuple[float, float]] = []
            for line in (sector / "SCREENING.PLT").read_text(encoding="latin-1").splitlines():
                fields = line.split()
                if len(fields) < 3:
                    continue
                try:
                    x, y, concentration = map(float, fields[:3])
                except ValueError:
                    continue
                distance = round(math.hypot(x, y), 1)
                curve[distance] = max(curve.get(distance, 0), concentration)
                points.append((concentration, distance))
            maxima.append((maximum, max(points)[1], direction, sector))
            if progress:
                progress(len(maxima) * 2 - 1, 72, f"Sector {direction:03d}° con downwash")
            baseline = run_directory / f"baseline-{direction:03d}"
            baseline.mkdir()
            (baseline / "prompts.inp").write_text(generate_makemet_prompts(directional), encoding="ascii")
            (baseline / "aermod.inp").write_text(generate_complex_aermod_input(
                directional, source_x=0, source_y=0, source_elevation_m=base,
                receptors=receptors, building_parameters=None, elevated=False,
            ), encoding="ascii")
            baseline_aermod = stage_executable(self.aermod, baseline)
            baseline_makemet = stage_executable(self.makemet, baseline)
            with (baseline / "prompts.inp").open("r", encoding="ascii") as stdin, (baseline / "makemet.stdout").open("w") as stdout:
                subprocess.run([str(baseline_makemet)], cwd=baseline, stdin=stdin, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=120)
            with (baseline / "aermod.stdout").open("w") as stdout:
                subprocess.run([str(baseline_aermod)], cwd=baseline, stdout=stdout, stderr=subprocess.STDOUT, check=True, timeout=300)
            baseline_maxima.append(_parse_maximum(baseline / "SCREENING.FIL")[0])
            if progress:
                progress(len(maxima) * 2, 72, f"Sector {direction:03d}° control sin downwash")
        maximum, distance, direction, winning = max(maxima)
        baseline_maximum = max(baseline_maxima)
        difference = maximum - baseline_maximum
        maximum_sectors = [float(item[2]) for item in maxima if math.isclose(item[0], maximum, rel_tol=1e-6, abs_tol=1e-8)]
        for name in ("aermod.inp", "aermod.out", "SCREENING.FIL", "SCREENING.PLT", "makemet.stdout", "aermod.stdout", "screening.sfc", "screening.pfl"):
            if (winning / name).is_file():
                shutil.copy2(winning / name, run_directory / name)
        result = ScreeningResult(
            status="completed", maximum_1h_ug_m3=maximum, maximum_distance_m=distance,
            maximum_direction_deg=float(direction) if len(maximum_sectors) == 1 else None,
            maximum_sectors_deg=maximum_sectors, scaled_3h_ug_m3=maximum,
            scaled_8h_ug_m3=maximum * .9, scaled_24h_ug_m3=maximum * .6,
            scaled_annual_ug_m3=maximum * .1, aermod_finished_successfully=True,
            no_fatal_errors=True,
            concentration_by_distance=[ConcentrationPoint(distance_m=d, concentration_1h_ug_m3=c) for d, c in sorted(curve.items())],
            sector_results=[SectorResult(wind_direction_deg=item[2], maximum_1h_ug_m3=item[0], maximum_distance_m=item[1]) for item in sorted(maxima, key=lambda value: value[2])],
            maximum_condition=parse_maximum_condition(winning / "SCREENING.FIL", winning / "screening.sfc"),
            without_downwash_maximum_1h_ug_m3=baseline_maximum,
            downwash_difference_1h_ug_m3=difference,
            downwash_change_percent=(difference / baseline_maximum * 100) if baseline_maximum else None,
            downwash_ratio=(maximum / baseline_maximum) if baseline_maximum else None,
        )
        (run_directory / "result.json").write_text(json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8")
        return result
