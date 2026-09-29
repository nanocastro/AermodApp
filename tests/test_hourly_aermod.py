from __future__ import annotations

import json
import math
import unittest
import tempfile
from pathlib import Path

from aermod_hourly.generator import generate_aermod_input
from aermod_hourly.engine import (
    HourlyEngine,
    _parse_annual_maximum,
    _parse_concentration_surface,
    _parse_maximum_condition,
)
from aermod_hourly.models import HourlyMaximum
from aermod_hourly.models import HourlyScenario
from aermod_hourly.stations import HOURLY_STATIONS
from aermod_screening.generator import TerrainReceptor


ROOT = Path(__file__).resolve().parents[1]
FLAT_DOWNWASH = ROOT / "examples/hourly_cordoba_2024_downwash.json"
COMPLEX_DOWNWASH = ROOT / "examples/hourly_cordoba_2024_complex_downwash.json"
CORDOBA_TERRAIN = ROOT / "data/private-validation/cordoba-terrain"


class HourlyAermodTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scenario = HourlyScenario.model_validate_json(
            (ROOT / "examples/hourly_cordoba_2024.json").read_text(encoding="utf-8")
        )

    def test_hourly_mode_uses_observed_files_without_screen(self) -> None:
        text = generate_aermod_input(self.scenario, HOURLY_STATIONS["cordoba-aero"])
        self.assertIn("MODELOPT CONC FLAT", text)
        self.assertNotIn(" SCREEN", text)
        self.assertIn("SURFDATA 87344 2024 CORDOBA", text)
        self.assertIn("UAIRDATA 00087344 2024 CORDOBA", text)
        self.assertIn("STARTEND 2024 01 01 2024 12 31", text)
        self.assertIn("AVERTIME 1 3 8 24 ANNUAL", text)
        self.assertIn("RANKFILE 24 10 HOURLY_24H.FIL", text)
        self.assertIn("PLOTFILE ANNUAL ALL HOURLY_ANNUAL.PLT", text)

    def test_hourly_complex_input_uses_aermap_elevations(self) -> None:
        scenario = self.scenario.model_copy(deep=True)
        scenario.terrain.mode = "complex"
        scenario.terrain.provider = "copernicus"
        text = generate_aermod_input(
            scenario,
            HOURLY_STATIONS["cordoba-aero"],
            source_x=386845.33,
            source_y=6517615.13,
            source_elevation_m=420.5,
            terrain_receptors=[TerrainReceptor(386845.33, 6516815.13, 412.0, 427.0)],
        )
        self.assertIn("MODELOPT CONC ELEV", text)
        self.assertIn("LOCATION STACK1 POINT 386845.33 6517615.13 420.50", text)
        self.assertIn("ELEVUNIT METERS", text)
        self.assertIn("DISCCART 386845.33 6516815.13 412.00 427.00", text)
        self.assertIn("PROFBASE 420.50 METERS", text)

    def test_hourly_input_places_flagpole_height_in_control_pathway(self) -> None:
        scenario = self.scenario.model_copy(deep=True)
        scenario.receptors.receptor_height_m = 1.0
        text = generate_aermod_input(scenario, HOURLY_STATIONS["cordoba-aero"])
        control, remainder = text.split("CO FINISHED", maxsplit=1)
        receptor = remainder.split("RE STARTING", maxsplit=1)[1].split("RE FINISHED", maxsplit=1)[0]
        self.assertIn("FLAGPOLE 1.00", control)
        self.assertNotIn("FLAGPOLE", receptor)

    def test_hourly_input_includes_all_prime_parameters(self) -> None:
        scenario = HourlyScenario.model_validate_json(
            FLAT_DOWNWASH.read_text(encoding="utf-8")
        )
        parameters = {
            name: [float(index) for index in range(36)]
            for name in ("BUILDHGT", "BUILDWID", "BUILDLEN", "XBADJ", "YBADJ")
        }
        text = generate_aermod_input(
            scenario, HOURLY_STATIONS["cordoba-aero"],
            building_parameters=parameters,
        )
        for name in parameters:
            self.assertEqual(text.count(f"{name:<8} STACK1"), 6)
        self.assertNotIn(" SCREEN", text)

    def test_receptor_grid_is_omnidirectional(self) -> None:
        receptors = self.scenario.receptors.receptors()
        self.assertEqual(len(receptors), 50 * 36)
        bearings_at_100 = {
            round(math.degrees(math.atan2(x, y)) % 360)
            for x, y in receptors if math.isclose(math.hypot(x, y), 100)
        }
        self.assertEqual(bearings_at_100, set(range(0, 360, 10)))

    def test_scenario_serializes_with_explicit_mode(self) -> None:
        payload = json.loads(self.scenario.model_dump_json())
        self.assertEqual(payload["run_mode"], "hourly")

    def test_parses_spatial_maxima_and_observed_maximum_condition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plot = root / "HOURLY.PLT"
            plot.write_text(
                "* header\n       0.00000    -800.00000  0.513798E+01     0.00     0.00     0.00    1-HR  ALL  1ST  24071711\n",
                encoding="ascii",
            )
            surface = root / "hourly.sfc"
            surface.write_text(
                "header\n"
                "2024 7 17 199 11 45.0 0.310 1.200 -9.000 1200. 450. -75.0 0.13 0.34 0.15 2.80 350.0 10.0 289.2 2.0 0 0.00 48.0 960.0 4 NAD-SFC NoSubs\n",
                encoding="ascii",
            )
            points = _parse_concentration_surface(plot)
            condition = _parse_maximum_condition(
                surface,
                HourlyMaximum(
                    concentration_ug_m3=5.13798, aermod_timestamp="24071711",
                    hour_ending_local="2024-07-17T11:00:00-03:00", x_m=0, y_m=-800,
                    distance_m=800, bearing_deg=180,
                ),
                -3,
            )
        self.assertEqual(len(points), 1)
        self.assertAlmostEqual(points[0].concentration_1h_ug_m3, 5.13798)
        self.assertEqual(condition.wind_direction_deg, 350)
        self.assertEqual(condition.boundary_layer_regime, "convectiva")
        self.assertEqual(condition.relative_humidity_percent, 48)

    def test_parses_annual_maximum_without_inventing_a_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plot = Path(directory) / "HOURLY_ANNUAL.PLT"
            plot.write_text(
                "* header\n"
                "   -383.02000    -321.39000  0.145113E+00     0.00     0.00     0.00  ANNUAL  ALL       00000001\n"
                "      0.00000    -800.00000  0.120000E+00     0.00     0.00     0.00  ANNUAL  ALL       00000001\n",
                encoding="ascii",
            )
            maximum = _parse_annual_maximum(plot)
        self.assertEqual(maximum.averaging_period, "annual")
        self.assertAlmostEqual(maximum.concentration_ug_m3, 0.145113)
        self.assertIsNone(maximum.aermod_timestamp)
        self.assertAlmostEqual(maximum.distance_m, 500, places=1)

    @unittest.skipUnless(
        (ROOT / "bin/aermod").is_file()
        and (ROOT / "bin/bpipprm").is_file()
        and (ROOT / "data/hourly/cordoba-aero/2024/cordoba-aero-2024.sfc").is_file(),
        "AERMOD, BPIPPRM y meteorología Córdoba son necesarios",
    )
    def test_real_hourly_flat_downwash_regression(self) -> None:
        scenario = HourlyScenario.model_validate_json(
            FLAT_DOWNWASH.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            result = HourlyEngine(
                aermod_executable=ROOT / "bin/aermod",
                meteorology_root=ROOT / "data/hourly",
                bpipprm_executable=ROOT / "bin/bpipprm",
            ).run(scenario, Path(directory) / "run")
        self.assertTrue(result.downwash_enabled)
        self.assertEqual(len(result.downwash_comparison), 5)
        self.assertAlmostEqual(result.maximum_1h.concentration_ug_m3, 5.13798, places=5)
        annual = result.downwash_comparison[-1]
        self.assertAlmostEqual(annual.with_downwash_ug_m3, 0.153636, places=6)
        self.assertAlmostEqual(annual.without_downwash_ug_m3, 0.145113, places=6)

    @unittest.skipUnless(
        (ROOT / "bin/aermod").is_file()
        and (ROOT / "bin/bpipprm").is_file()
        and (CORDOBA_TERRAIN / "terrain-result.json").is_file(),
        "AERMOD, BPIPPRM y terreno Córdoba son necesarios",
    )
    def test_real_hourly_complex_downwash_regression(self) -> None:
        scenario = HourlyScenario.model_validate_json(
            COMPLEX_DOWNWASH.read_text(encoding="utf-8")
        )
        with tempfile.TemporaryDirectory() as directory:
            result = HourlyEngine(
                aermod_executable=ROOT / "bin/aermod",
                meteorology_root=ROOT / "data/hourly",
                bpipprm_executable=ROOT / "bin/bpipprm",
            ).run(scenario, Path(directory) / "run", CORDOBA_TERRAIN)
        self.assertEqual(result.terrain_mode, "complex")
        self.assertTrue(result.downwash_enabled)
        self.assertEqual(result.source_elevation_m, 450.54)
        self.assertAlmostEqual(result.maximum_1h.concentration_ug_m3, 5.11089, places=5)
        self.assertAlmostEqual(
            result.downwash_comparison[-1].change_percent or 0, 5.95068, places=4
        )


if __name__ == "__main__":
    unittest.main()
