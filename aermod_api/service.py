from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

from aermod_screening import ScreeningEngine, ScreeningScenario
from aermod_screening.complex_engine import ComplexTerrainEngine
from aermod_screening.downwash_engine import FlatDownwashEngine
from aermod_screening.executables import stage_executable
from aermod_screening.models import RoughnessSensitivityResult
from aermod_screening.terrain import (
    copernicus_tile_name,
    copernicus_tiles_for_domain,
    download_copernicus,
    generate_aermap_input,
    prepare_for_aermap,
)
from aermod_hourly import HourlyEngine, HourlyScenario
from aermod_multisource import MultiSourceHourlyEngine, MultiSourceHourlyScenario
from aermod_multisource.geometry import build_geometry
from aermod_multisource.terrain import (
    domain_margin_m,
    generate_multisource_aermap_input,
    read_multisource_aermap,
)

from .config import Settings
from .database import Database


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_kind(path: Path) -> str:
    if path.name in {"scenario.json", "source-geometry.json", "aermod.inp", "prompts.inp", "building.inp", "building-base-elevations.json"}:
        return "input"
    if path.name in {"result.json", "roughness-sensitivity.json", "terrain-comparison.json", "downwash-comparison.json", "SCREENING.FIL", "SCREENING.PLT", "aermod.out", "building.out", "building.sum"} or path.name.startswith(("HOURLY", "MULTI_", "without-downwash-")):
        return "result"
    if path.suffix.lower() in {".stdout", ".log"}:
        return "log"
    if path.stem in {"aermod", "makemet", "aermap", "bpipprm"}:
        return "executable"
    return "intermediate"


class RunService:
    def __init__(self, database: Database, settings: Settings) -> None:
        self.database = database
        self.settings = settings

    def create(self, scenario_id: str):
        scenario_row = self.database.get_scenario(scenario_id)
        if scenario_row is None:
            raise KeyError(scenario_id)
        return self.database.create_run(scenario_id)

    def execute(self, run_id: str) -> None:
        run_row = self.database.get_run(run_id)
        if run_row is None:
            raise KeyError(run_id)
        scenario_row = self.database.get_scenario(run_row["scenario_id"])
        if scenario_row is None:
            raise KeyError(run_row["scenario_id"])
        run_directory = self.settings.runs_directory.resolve() / run_id
        self.database.mark_run_running(run_id)
        try:
            definition = json.loads(scenario_row["definition_json"])
            if definition.get("run_mode") == "multi_source_hourly":
                scenario = MultiSourceHourlyScenario.model_validate(definition)
                self.database.update_run_progress(
                    run_id, 0, 1, "Preparando fuentes y red receptora compartida"
                )
                result = MultiSourceHourlyEngine(
                    aermod_executable=self.settings.aermod_executable,
                    meteorology_root=self.settings.hourly_directory,
                ).run(
                    scenario,
                    run_directory,
                    self.settings.terrain_directory.resolve() / scenario_row["id"]
                    if scenario.terrain.mode == "complex" else None,
                )
                self.database.update_run_progress(run_id, 1, 1, "Corrida multifuente completada")
                self.database.mark_run_completed(run_id, result.model_dump())
                for path in sorted(run_directory.iterdir()):
                    if path.is_file():
                        self.database.add_artifact(
                            run_id, name=path.name, kind=artifact_kind(path),
                            relative_path=path.name, size_bytes=path.stat().st_size,
                            sha256=file_sha256(path),
                        )
                return
            if definition.get("run_mode") == "hourly":
                scenario = HourlyScenario.model_validate(definition)
                total_steps = 2 if scenario.downwash.enabled else 1
                self.database.update_run_progress(
                    run_id,
                    0,
                    total_steps,
                    (
                        "Preparando BPIPPRM, meteorología observada y malla de receptores"
                        if scenario.downwash.enabled
                        else "Preparando meteorología observada y malla de receptores"
                    ),
                )
                result = HourlyEngine(
                    aermod_executable=self.settings.aermod_executable,
                    meteorology_root=self.settings.hourly_directory,
                    bpipprm_executable=self.settings.bpipprm_executable,
                ).run(
                    scenario,
                    run_directory,
                    self.settings.terrain_directory.resolve() / scenario_row["id"]
                    if scenario.terrain.mode == "complex" else None,
                )
                self.database.update_run_progress(
                    run_id, total_steps, total_steps, "Corrida horaria completada"
                )
                self.database.mark_run_completed(run_id, result.model_dump())
                for path in sorted(run_directory.iterdir()):
                    if path.is_file():
                        self.database.add_artifact(
                            run_id, name=path.name, kind=artifact_kind(path),
                            relative_path=path.name, size_bytes=path.stat().st_size,
                            sha256=file_sha256(path),
                        )
                return
            scenario = ScreeningScenario.model_validate_json(scenario_row["definition_json"])
            candidates = scenario.meteorology.roughness_candidates_m
            sensitivity_count = len(candidates) * 36 if scenario.terrain.mode == "complex" and len(candidates) > 1 else 0
            final_count = 72 if scenario.downwash.enabled else (36 if scenario.terrain.mode == "complex" else 1)
            comparison_count = (72 if scenario.downwash.enabled else 1) if scenario.terrain.compare_with_flat else 0
            total = sensitivity_count + final_count + comparison_count
            self.database.update_run_progress(run_id, 0, total, "Preparando archivos de entrada")
            report_progress = lambda current, count, label: self.database.update_run_progress(run_id, current, count, label)
            if scenario.terrain.mode == "complex":
                terrain_directory = self.settings.terrain_directory.resolve() / scenario_row["id"]
                if not (terrain_directory / "terrain-result.json").is_file():
                    raise ValueError("Prepare el terreno del escenario antes de ejecutar")
                engine = ComplexTerrainEngine(
                    aermod_executable=self.settings.aermod_executable,
                    makemet_executable=self.settings.makemet_executable,
                    bpipprm_executable=self.settings.bpipprm_executable,
                )
                if sensitivity_count:
                    run_directory.mkdir(parents=True, exist_ok=False)
                    sensitivity = []
                    for index, candidate in enumerate(candidates):
                        candidate_scenario = scenario.model_copy(deep=True)
                        candidate_scenario.meteorology.surface_roughness_m = candidate
                        candidate_scenario.meteorology.roughness_candidates_m = []
                        candidate_scenario.downwash.enabled = False
                        candidate_scenario.downwash.buildings = []
                        offset = index * 36
                        candidate_result = engine.run(
                            candidate_scenario,
                            run_directory / f"roughness-{index + 1:02d}-{candidate:.4f}",
                            terrain_directory,
                            progress=lambda current, _count, label, offset=offset, candidate=candidate: report_progress(
                                offset + current, total, f"Sensibilidad z0 {candidate:.4f} m · {label}"
                            ),
                        )
                        sensitivity.append({
                            "roughness_m": candidate,
                            "maximum_1h_ug_m3": candidate_result.maximum_1h_ug_m3,
                            "maximum_distance_m": candidate_result.maximum_distance_m,
                            "maximum_direction_deg": candidate_result.maximum_direction_deg,
                        })
                    selected = max(sensitivity, key=lambda item: item["maximum_1h_ug_m3"])
                    final_scenario = scenario.model_copy(deep=True)
                    final_scenario.meteorology.surface_roughness_m = selected["roughness_m"]
                    result = engine.run(
                        final_scenario, run_directory / "final", terrain_directory,
                        progress=lambda current, _count, label: report_progress(
                            sensitivity_count + current, total, f"Corrida final · {label}"
                        ),
                    )
                    result.roughness_candidates_m = candidates
                    result.selected_surface_roughness_m = selected["roughness_m"]
                    result.roughness_sensitivity = [RoughnessSensitivityResult(**item) for item in sensitivity]
                    summary = {
                        "method": "Hasta cinco candidatos representativos; selección por máxima concentración AERMOD 1 h en 36 direcciones sin downwash.",
                        "candidates": sensitivity,
                        "selected_surface_roughness_m": selected["roughness_m"],
                    }
                    (run_directory / "roughness-sensitivity.json").write_text(
                        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
                    )
                    for path in (run_directory / "final").iterdir():
                        if path.is_file() and path.name not in {"scenario.json", "result.json"}:
                            shutil.copy2(path, run_directory / path.name)
                    (run_directory / "scenario.json").write_text(
                        scenario.model_dump_json(indent=2) + "\n", encoding="utf-8"
                    )
                    (run_directory / "result.json").write_text(
                        json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8"
                    )
                else:
                    result = engine.run(
                        scenario, run_directory, terrain_directory,
                        progress=lambda current, _count, label: report_progress(current, total, f"Corrida compleja · {label}"),
                    )
            elif scenario.downwash.enabled:
                result = FlatDownwashEngine(
                    aermod_executable=self.settings.aermod_executable,
                    makemet_executable=self.settings.makemet_executable,
                    bpipprm_executable=self.settings.bpipprm_executable,
                ).run(scenario, run_directory, progress=report_progress)
            else:
                result = ScreeningEngine(
                    aermod_executable=self.settings.aermod_executable,
                    makemet_executable=self.settings.makemet_executable,
                ).run(scenario, run_directory)
                self.database.update_run_progress(run_id, 1, 1, "Ejecución AERMOD completada")
            if scenario.terrain.compare_with_flat:
                flat_scenario = scenario.model_copy(deep=True)
                flat_scenario.terrain.mode = "flat"
                flat_scenario.terrain.provider = None
                flat_scenario.terrain.compare_with_flat = False
                flat_scenario.meteorology.roughness_candidates_m = []
                if result.selected_surface_roughness_m is not None:
                    flat_scenario.meteorology.surface_roughness_m = result.selected_surface_roughness_m
                comparison_offset = sensitivity_count + final_count
                if flat_scenario.downwash.enabled:
                    flat_result = FlatDownwashEngine(
                        aermod_executable=self.settings.aermod_executable,
                        makemet_executable=self.settings.makemet_executable,
                        bpipprm_executable=self.settings.bpipprm_executable,
                    ).run(
                        flat_scenario, run_directory / "flat-comparison",
                        progress=lambda current, _count, label: report_progress(
                            comparison_offset + current, total, f"Control plano · {label}"
                        ),
                    )
                else:
                    report_progress(comparison_offset, total, "Preparando control con terreno plano")
                    flat_result = ScreeningEngine(
                        aermod_executable=self.settings.aermod_executable,
                        makemet_executable=self.settings.makemet_executable,
                    ).run(flat_scenario, run_directory / "flat-comparison")
                    report_progress(total, total, "Control con terreno plano completado")
                difference = result.maximum_1h_ug_m3 - flat_result.maximum_1h_ug_m3
                result.flat_terrain_maximum_1h_ug_m3 = flat_result.maximum_1h_ug_m3
                result.flat_terrain_maximum_distance_m = flat_result.maximum_distance_m
                result.flat_terrain_maximum_direction_deg = flat_result.maximum_direction_deg
                result.terrain_difference_1h_ug_m3 = difference
                result.terrain_change_percent = (
                    difference / flat_result.maximum_1h_ug_m3 * 100
                    if flat_result.maximum_1h_ug_m3 else None
                )
                result.complex_to_flat_ratio = (
                    result.maximum_1h_ug_m3 / flat_result.maximum_1h_ug_m3
                    if flat_result.maximum_1h_ug_m3 else None
                )
                comparison = {
                    "method": "Misma fuente, meteorología, receptores y downwash; solo se reemplazan las cotas AERMAP por elevación uniforme.",
                    "complex": {
                        "maximum_1h_ug_m3": result.maximum_1h_ug_m3,
                        "maximum_distance_m": result.maximum_distance_m,
                        "maximum_direction_deg": result.maximum_direction_deg,
                    },
                    "flat": {
                        "maximum_1h_ug_m3": flat_result.maximum_1h_ug_m3,
                        "maximum_distance_m": flat_result.maximum_distance_m,
                        "maximum_direction_deg": flat_result.maximum_direction_deg,
                    },
                    "complex_minus_flat_1h_ug_m3": difference,
                    "change_percent": result.terrain_change_percent,
                    "complex_to_flat_ratio": result.complex_to_flat_ratio,
                }
                (run_directory / "terrain-comparison.json").write_text(
                    json.dumps(comparison, indent=2) + "\n", encoding="utf-8"
                )
                (run_directory / "result.json").write_text(
                    json.dumps(result.model_dump(), indent=2) + "\n", encoding="utf-8"
                )
            self.database.mark_run_completed(run_id, result.model_dump())
            for path in sorted(run_directory.iterdir()):
                if not path.is_file():
                    continue
                self.database.add_artifact(
                    run_id,
                    name=path.name,
                    kind=artifact_kind(path),
                    relative_path=path.name,
                    size_bytes=path.stat().st_size,
                    sha256=file_sha256(path),
                )
        except Exception as error:
            self.database.mark_run_failed(run_id, f"{type(error).__name__}: {error}")

    def artifact_path(self, artifact_row) -> Path:
        path = (
            self.settings.runs_directory.resolve()
            / artifact_row["run_id"]
            / artifact_row["relative_path"]
        ).resolve()
        expected_parent = (self.settings.runs_directory.resolve() / artifact_row["run_id"]).resolve()
        if path.parent != expected_parent or not path.is_file():
            raise FileNotFoundError(path)
        return path


class TerrainService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def prepare(
        self,
        scenario_id: str,
        scenario: ScreeningScenario | HourlyScenario | MultiSourceHourlyScenario,
    ) -> dict:
        if isinstance(scenario, MultiSourceHourlyScenario):
            return self._prepare_multisource(scenario_id, scenario)
        terrain = scenario.terrain
        source = scenario.source
        if terrain.mode != "complex":
            raise ValueError("El escenario no esta configurado con terreno complejo")
        if terrain.provider != "copernicus":
            raise ValueError("La carga de MDE-Ar IGN se habilitara mediante archivo; use Copernicus ahora")
        if source.latitude_deg is None or source.longitude_deg is None:
            raise ValueError("Faltan coordenadas de la fuente")
        if not self.settings.aermap_executable.is_file():
            raise FileNotFoundError(self.settings.aermap_executable)

        directory = self.settings.terrain_directory.resolve() / scenario_id
        downloads = directory / "downloads"
        receptor_distances = tuple(dict.fromkeys(scenario.receptors.distances()))
        domain_margin = max(5000.0, max(receptor_distances) * 1.5)
        downloaded = []
        for tile_latitude, tile_longitude in copernicus_tiles_for_domain(source.latitude_deg, source.longitude_deg, domain_margin):
            tile = copernicus_tile_name(tile_latitude, tile_longitude)
            downloaded.append(download_copernicus(tile_latitude, tile_longitude, downloads / f"{tile}.tif"))
        prepared_path = directory / "terrain-aermap.tif"
        preparation = prepare_for_aermap(
            downloaded, prepared_path, latitude_deg=source.latitude_deg,
            longitude_deg=source.longitude_deg, provider="copernicus",
        )
        (directory / "aermap.inp").write_text(
            generate_aermap_input(
                prepared_path.name, latitude_deg=source.latitude_deg,
                longitude_deg=source.longitude_deg,
                receptor_distances_m=receptor_distances,
                directions_deg=tuple(range(0, 360, 10)),
            ), encoding="ascii",
        )
        executable = stage_executable(self.settings.aermap_executable, directory)
        completed = subprocess.run(
            [str(executable), "aermap.inp", "aermap.out"], cwd=directory,
            capture_output=True, text=True, timeout=300,
        )
        (directory / "aermap.stdout").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        output_path = directory / "aermap.out"
        output = output_path.read_text(encoding="latin-1") if output_path.exists() else completed.stdout
        if completed.returncode != 0 or "AERMAP Finishes Successfully" not in output:
            raise RuntimeError("AERMAP no termino correctamente; consulte aermap.out")
        source_output = (directory / "source-aermap.out").read_text(encoding="latin-1")
        elevation_match = re.search(r"SO LOCATION\s+\S+\s+\S+\s+[-0-9.]+\s+[-0-9.]+\s+([-0-9.]+)", source_output)
        receptor_output = (directory / "receptors-aermap.out").read_text(encoding="latin-1")
        warnings = [line.strip() for line in output.splitlines() if "WARNING:" in line]
        result = {
            "scenario_id": scenario_id, "status": "prepared", "provider": "copernicus",
            "latitude_deg": preparation.latitude_deg, "longitude_deg": preparation.longitude_deg,
            "utm_zone": preparation.utm_zone, "utm_hemisphere": preparation.utm_hemisphere,
            "source_sha256": preparation.source_sha256,
            "prepared_sha256": preparation.prepared_sha256,
            "source_elevation_m": float(elevation_match.group(1)) if elevation_match else None,
            "receptor_count": receptor_output.count("DISCCART"), "warnings": warnings,
        }
        (directory / "terrain-result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        return result

    def _prepare_multisource(
        self, scenario_id: str, scenario: MultiSourceHourlyScenario
    ) -> dict:
        if scenario.terrain.mode != "complex":
            raise ValueError("El escenario no esta configurado con terreno complejo")
        if scenario.terrain.provider != "copernicus":
            raise ValueError(
                "La carga de MDE-Ar IGN se habilitara mediante archivo; use Copernicus ahora"
            )
        if not self.settings.aermap_executable.is_file():
            raise FileNotFoundError(self.settings.aermap_executable)
        geometry = build_geometry(scenario)
        margin = domain_margin_m(scenario, geometry)
        directory = self.settings.terrain_directory.resolve() / scenario_id
        downloads = directory / "downloads"
        downloaded = []
        for tile_latitude, tile_longitude in copernicus_tiles_for_domain(
            geometry.center_latitude_deg, geometry.center_longitude_deg, margin
        ):
            tile = copernicus_tile_name(tile_latitude, tile_longitude)
            downloaded.append(download_copernicus(
                tile_latitude, tile_longitude, downloads / f"{tile}.tif"
            ))
        prepared_path = directory / "terrain-aermap.tif"
        preparation = prepare_for_aermap(
            downloaded,
            prepared_path,
            latitude_deg=geometry.center_latitude_deg,
            longitude_deg=geometry.center_longitude_deg,
            provider="copernicus",
        )
        (directory / "aermap.inp").write_text(
            generate_multisource_aermap_input(
                prepared_path.name, scenario, geometry
            ),
            encoding="ascii",
        )
        executable = stage_executable(self.settings.aermap_executable, directory)
        completed = subprocess.run(
            [str(executable), "aermap.inp", "aermap.out"],
            cwd=directory,
            capture_output=True,
            text=True,
            timeout=300,
        )
        (directory / "aermap.stdout").write_text(
            completed.stdout + completed.stderr, encoding="utf-8"
        )
        output_path = directory / "aermap.out"
        output = (
            output_path.read_text(encoding="latin-1")
            if output_path.exists() else completed.stdout
        )
        if completed.returncode != 0 or "AERMAP Finishes Successfully" not in output:
            raise RuntimeError("AERMAP multifuente no termino correctamente; consulte aermap.out")
        sources, receptors = read_multisource_aermap(directory)
        expected_ids = {source.source_id for source in scenario.sources}
        if set(sources) != expected_ids:
            raise RuntimeError("AERMAP no devolvio todas las fuentes multifuente")
        source_elevations = {
            source_id: source.elevation_m for source_id, source in sources.items()
        }
        warnings = [line.strip() for line in output.splitlines() if "WARNING:" in line]
        result = {
            "scenario_id": scenario_id,
            "status": "prepared",
            "provider": "copernicus",
            "latitude_deg": preparation.latitude_deg,
            "longitude_deg": preparation.longitude_deg,
            "utm_zone": preparation.utm_zone,
            "utm_hemisphere": preparation.utm_hemisphere,
            "source_sha256": preparation.source_sha256,
            "prepared_sha256": preparation.prepared_sha256,
            "source_elevation_m": sum(source_elevations.values()) / len(source_elevations),
            "source_elevations_m": source_elevations,
            "receptor_count": len(receptors),
            "warnings": warnings,
        }
        (directory / "terrain-result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf-8"
        )
        return result
