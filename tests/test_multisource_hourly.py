from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError

from aermod_hourly.stations import HOURLY_STATIONS
from aermod_multisource import MultiSourceHourlyEngine, MultiSourceHourlyScenario
from aermod_multisource.generator import generate_aermod_input
from aermod_multisource.geometry import build_geometry
from aermod_multisource.terrain import (
    TerrainSource,
    generate_multisource_aermap_input,
    read_multisource_aermap,
)
from aermod_screening.executables import stage_executable
from aermod_screening.generator import TerrainReceptor


ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/multisource_cordoba_2024.json"
COMPLEX_EXAMPLE = ROOT / "examples/multisource_cordoba_2024_complex.json"
CORDOBA_DEM = (
    ROOT / "data/private-validation/cordoba-terrain/terrain-aermap.tif"
)


class MultiSourceHourlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.payload = json.loads(EXAMPLE.read_text(encoding="utf-8"))

    def scenario(self) -> MultiSourceHourlyScenario:
        return MultiSourceHourlyScenario.model_validate(self.payload)

    def test_requires_unique_source_identifiers(self) -> None:
        payload = json.loads(json.dumps(self.payload))
        payload["sources"][1]["source_id"] = payload["sources"][0]["source_id"]
        with self.assertRaisesRegex(ValidationError, "identificadores de fuente deben ser únicos"):
            MultiSourceHourlyScenario.model_validate(payload)

    def test_requires_at_least_two_georeferenced_sources(self) -> None:
        payload = json.loads(json.dumps(self.payload))
        payload["sources"] = payload["sources"][:1]
        with self.assertRaises(ValidationError):
            MultiSourceHourlyScenario.model_validate(payload)
        payload = json.loads(json.dumps(self.payload))
        payload["sources"][1].pop("latitude_deg")
        with self.assertRaisesRegex(ValidationError, "deben informarse juntas"):
            MultiSourceHourlyScenario.model_validate(payload)

    def test_geometry_uses_shared_relative_utm_system(self) -> None:
        geometry = build_geometry(self.scenario())
        self.assertEqual(geometry.zone, 20)
        self.assertEqual(geometry.hemisphere, "south")
        self.assertEqual(len(geometry.sources), 2)
        self.assertLess(geometry.sources[0].x_m, 0)
        self.assertGreater(geometry.sources[1].x_m, 0)
        self.assertGreater(abs(geometry.sources[1].x_m - geometry.sources[0].x_m), 200)

    def test_generator_declares_every_source_and_combined_group(self) -> None:
        scenario = self.scenario()
        text = generate_aermod_input(
            scenario, HOURLY_STATIONS[scenario.meteorology.station], build_geometry(scenario)
        )
        self.assertIn("MODELOPT CONC FLAT", text)
        self.assertIn("AVERTIME 1 3 8 24 ANNUAL", text)
        self.assertIn("LOCATION STACK1 POINT", text)
        self.assertIn("LOCATION STACK2 POINT", text)
        self.assertIn("SRCPARAM STACK1", text)
        self.assertIn("SRCPARAM STACK2", text)
        self.assertIn("SRCGROUP ALL", text)
        self.assertNotIn("SCREEN", text)

    def test_generator_places_flagpole_height_in_control_pathway(self) -> None:
        scenario = self.scenario().model_copy(deep=True)
        scenario.receptors.receptor_height_m = 1.0
        text = generate_aermod_input(
            scenario, HOURLY_STATIONS[scenario.meteorology.station], build_geometry(scenario)
        )
        control, remainder = text.split("CO FINISHED", maxsplit=1)
        receptor = remainder.split("RE STARTING", maxsplit=1)[1].split("RE FINISHED", maxsplit=1)[0]
        self.assertIn("FLAGPOLE 1.00", control)
        self.assertNotIn("FLAGPOLE", receptor)

    def test_complex_generator_uses_every_aermap_elevation(self) -> None:
        scenario = MultiSourceHourlyScenario.model_validate_json(
            COMPLEX_EXAMPLE.read_text(encoding="utf-8")
        )
        geometry = build_geometry(scenario)
        terrain_sources = {
            "STACK1": TerrainSource("STACK1", 386800.0, 6517600.0, 450.5),
            "STACK2": TerrainSource("STACK2", 387020.0, 6517690.0, 449.9),
        }
        text = generate_aermod_input(
            scenario,
            HOURLY_STATIONS[scenario.meteorology.station],
            geometry,
            terrain_sources=terrain_sources,
            terrain_receptors=[TerrainReceptor(386900.0, 6517500.0, 448.0, 460.0)],
        )
        self.assertIn("MODELOPT CONC ELEV", text)
        self.assertIn("LOCATION STACK1 POINT 386800.00 6517600.00 450.50", text)
        self.assertIn("LOCATION STACK2 POINT 387020.00 6517690.00 449.90", text)
        self.assertIn("DISCCART 386900.00 6517500.00 448.00 460.00", text)
        self.assertIn("PROFBASE 488.90 METERS", text)

    def test_multisource_aermap_input_and_parser(self) -> None:
        scenario = MultiSourceHourlyScenario.model_validate_json(
            COMPLEX_EXAMPLE.read_text(encoding="utf-8")
        )
        geometry = build_geometry(scenario)
        text = generate_multisource_aermap_input("terrain.tif", scenario, geometry)
        self.assertEqual(text.count("LOCATION STACK"), 2)
        self.assertEqual(text.count("DISCCART"), 1800)
        self.assertIn(" -20 0", text)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "source-aermap.out").write_text(
                " SO LOCATION STACK1 POINT 386800.00 6517600.00 450.50\n"
                " SO LOCATION STACK2 POINT 387020.00 6517690.00 449.90\n",
                encoding="ascii",
            )
            (path / "receptors-aermap.out").write_text(
                " DISCCART 386900.00 6517500.00 448.00 460.00\n",
                encoding="ascii",
            )
            sources, receptors = read_multisource_aermap(path)
        self.assertEqual(set(sources), {"STACK1", "STACK2"})
        self.assertEqual(sources["STACK1"].elevation_m, 450.5)
        self.assertEqual(len(receptors), 1)

    @unittest.skipUnless(
        (ROOT / "bin/aermod").is_file()
        and (ROOT / "data/hourly/cordoba-aero/2024/cordoba-aero-2024.sfc").is_file(),
        "AERMOD y la meteorología horaria local son necesarios para la regresión",
    )
    def test_real_aermod_multisource_regression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = MultiSourceHourlyEngine(
                aermod_executable=ROOT / "bin/aermod",
                meteorology_root=ROOT / "data/hourly",
            ).run(self.scenario(), Path(directory) / "run")
        self.assertTrue(result.aermod_finished_successfully)
        self.assertTrue(result.no_fatal_errors)
        self.assertEqual(result.source_count, 2)
        self.assertEqual(result.receptor_count, 1800)
        self.assertAlmostEqual(result.maximum_1h.concentration_ug_m3, 8.0736, places=4)
        self.assertEqual([item.averaging_period for item in result.period_maxima], [
            "1h", "3h", "8h", "24h", "annual"
        ])

    @unittest.skipUnless(
        (ROOT / "bin/aermod").is_file()
        and (ROOT / "bin/aermap").is_file()
        and CORDOBA_DEM.is_file()
        and (ROOT / "data/hourly/cordoba-aero/2024/cordoba-aero-2024.sfc").is_file(),
        "AERMAP, AERMOD, DEM Córdoba y meteorología local son necesarios",
    )
    def test_real_complex_terrain_multisource_regression(self) -> None:
        scenario = MultiSourceHourlyScenario.model_validate_json(
            COMPLEX_EXAMPLE.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            terrain = root / "terrain"
            terrain.mkdir()
            (terrain / "terrain-aermap.tif").symlink_to(CORDOBA_DEM)
            geometry = build_geometry(scenario)
            (terrain / "aermap.inp").write_text(
                generate_multisource_aermap_input(
                    "terrain-aermap.tif", scenario, geometry
                ),
                encoding="ascii",
            )
            executable = stage_executable(ROOT / "bin/aermap", terrain)
            completed = subprocess.run(
                [str(executable), "aermap.inp", "aermap.out"],
                cwd=terrain,
                capture_output=True,
                text=True,
                timeout=300,
            )
            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertIn(
                "AERMAP Finishes Successfully",
                (terrain / "aermap.out").read_text(encoding="latin-1"),
            )
            sources, receptors = read_multisource_aermap(terrain)
            (terrain / "terrain-result.json").write_text(
                json.dumps({
                    "status": "prepared",
                    "source_elevations_m": {
                        source_id: source.elevation_m
                        for source_id, source in sources.items()
                    },
                    "receptor_count": len(receptors),
                }),
                encoding="utf-8",
            )
            result = MultiSourceHourlyEngine(
                aermod_executable=ROOT / "bin/aermod",
                meteorology_root=ROOT / "data/hourly",
            ).run(scenario, root / "run", terrain)
        self.assertEqual(result.terrain_mode, "complex")
        self.assertEqual([source.elevation_m for source in result.source_positions], [450.54, 449.88])
        self.assertAlmostEqual(result.maximum_1h.concentration_ug_m3, 7.69483, places=5)


if __name__ == "__main__":
    unittest.main()
