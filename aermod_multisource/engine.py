from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from aermod_hourly.aermet import summarize_surface_file
from aermod_hourly.engine import (
    _parse_annual_maximum,
    _parse_concentration_surface,
    _parse_maximum,
    _parse_maximum_condition,
    _period_maximum,
)
from aermod_hourly.generator import PROFILE_FILE, SURFACE_FILE
from aermod_hourly.stations import HOURLY_STATIONS
from aermod_screening.executables import stage_executable

from .generator import ANNUAL_PLOT_FILE, PLOT_FILES, RANK_FILES, generate_aermod_input
from .geometry import build_geometry
from .models import MultiSourceHourlyResult, MultiSourceHourlyScenario
from .terrain import read_multisource_aermap


class MultiSourceHourlyEngine:
    def __init__(self, *, aermod_executable: Path, meteorology_root: Path) -> None:
        self.aermod_executable = aermod_executable.resolve()
        self.meteorology_root = meteorology_root.resolve()
        if not self.aermod_executable.is_file():
            raise FileNotFoundError(self.aermod_executable)

    def run(
        self,
        scenario: MultiSourceHourlyScenario,
        run_directory: Path,
        terrain_directory: Path | None = None,
    ) -> MultiSourceHourlyResult:
        run_directory = run_directory.resolve()
        if run_directory.exists() and any(run_directory.iterdir()):
            raise FileExistsError(f"El directorio de corrida no está vacío: {run_directory}")
        run_directory.mkdir(parents=True, exist_ok=True)
        station = HOURLY_STATIONS[scenario.meteorology.station]
        year = scenario.meteorology.year
        met_directory = self.meteorology_root / station.slug / str(year)
        for source, target in (
            (met_directory / f"{station.slug}-{year}.sfc", SURFACE_FILE),
            (met_directory / f"{station.slug}-{year}.pfl", PROFILE_FILE),
        ):
            if not source.is_file():
                raise FileNotFoundError(
                    f"Falta {source}; prepare primero la meteorología horaria con AERMET"
                )
            shutil.copy2(source, run_directory / target)

        geometry = build_geometry(scenario)
        terrain_sources = None
        terrain_receptors = None
        if scenario.terrain.mode == "complex":
            if terrain_directory is None or not (terrain_directory / "terrain-result.json").is_file():
                raise ValueError("Prepare el terreno multifuente antes de ejecutar")
            terrain_sources, terrain_receptors = read_multisource_aermap(terrain_directory)
            expected_ids = {source.source_id for source in scenario.sources}
            if set(terrain_sources) != expected_ids:
                raise ValueError("Las fuentes del resultado AERMAP no coinciden con el escenario")
            shutil.copy2(
                terrain_directory / "terrain-result.json",
                run_directory / "terrain-result.json",
            )
            geometry = type(geometry)(
                center_latitude_deg=geometry.center_latitude_deg,
                center_longitude_deg=geometry.center_longitude_deg,
                zone=geometry.zone,
                hemisphere=geometry.hemisphere,
                center_x_m=geometry.center_x_m,
                center_y_m=geometry.center_y_m,
                sources=[position.model_copy(update={
                    "elevation_m": terrain_sources[position.source_id].elevation_m
                }) for position in geometry.sources],
            )
        (run_directory / "scenario.json").write_text(
            scenario.model_dump_json(indent=2) + "\n", encoding="utf-8"
        )
        (run_directory / "source-geometry.json").write_text(
            json.dumps({
                "center_latitude_deg": geometry.center_latitude_deg,
                "center_longitude_deg": geometry.center_longitude_deg,
                "utm_zone": geometry.zone,
                "utm_hemisphere": geometry.hemisphere,
                "sources": [position.model_dump() for position in geometry.sources],
            }, indent=2) + "\n", encoding="utf-8",
        )
        (run_directory / "aermod.inp").write_text(
            generate_aermod_input(
                scenario,
                station,
                geometry,
                terrain_sources=terrain_sources,
                terrain_receptors=terrain_receptors,
            ),
            encoding="ascii",
        )
        executable = stage_executable(self.aermod_executable, run_directory)
        with (run_directory / "aermod.stdout").open("w", encoding="utf-8") as output:
            completed = subprocess.run(
                [str(executable)], cwd=run_directory, stdout=output,
                stderr=subprocess.STDOUT, timeout=1800, check=False,
            )
        output_path = run_directory / "aermod.out"
        output_text = output_path.read_text(encoding="latin-1") if output_path.is_file() else ""
        successful = "AERMOD Finishes Successfully" in output_text
        no_fatal = re.search(r"FATAL ERROR MESSAGES[\s*]+NONE", output_text) is not None
        if completed.returncode != 0 or not successful or not no_fatal:
            raise RuntimeError(
                f"AERMOD multifuente falló (código {completed.returncode}); consulte aermod.out"
            )

        origin_x = geometry.center_x_m if terrain_sources else 0.0
        origin_y = geometry.center_y_m if terrain_sources else 0.0
        maximum = _parse_maximum(
            run_directory / RANK_FILES[1], station.utc_offset_hours, origin_x, origin_y
        )
        period_maxima = [_period_maximum("1h", maximum)]
        for period in (3, 8, 24):
            period_maxima.append(_period_maximum(
                f"{period}h",
                _parse_maximum(
                    run_directory / RANK_FILES[period], station.utc_offset_hours,
                    origin_x, origin_y,
                ),
            ))
        period_maxima.append(_parse_annual_maximum(
            run_directory / ANNUAL_PLOT_FILE, origin_x, origin_y
        ))
        surface_summary = summarize_surface_file(run_directory / SURFACE_FILE)
        result = MultiSourceHourlyResult(
            status="completed", station=station.slug, year=year,
            source_count=len(scenario.sources),
            receptor_count=len(scenario.receptors.receptors()),
            domain_center_latitude_deg=geometry.center_latitude_deg,
            domain_center_longitude_deg=geometry.center_longitude_deg,
            utm_zone=geometry.zone, utm_hemisphere=geometry.hemisphere,
            source_positions=geometry.sources,
            terrain_mode=scenario.terrain.mode,
            maximum_1h=maximum, period_maxima=period_maxima,
            maximum_condition=_parse_maximum_condition(
                run_directory / SURFACE_FILE, maximum, station.utc_offset_hours
            ),
            maximum_1h_by_receptor=_parse_concentration_surface(
                run_directory / PLOT_FILES[1], origin_x, origin_y
            ),
            meteorology_total_hours=surface_summary["total_hours"],
            meteorology_usable_hours=surface_summary["usable_hours"],
            meteorology_usable_percent=surface_summary["usable_percent"],
            aermod_finished_successfully=successful, no_fatal_errors=no_fatal,
        )
        (run_directory / "result.json").write_text(
            json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8"
        )
        return result
