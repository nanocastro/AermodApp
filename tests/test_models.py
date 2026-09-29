from __future__ import annotations

import json
import unittest
from pathlib import Path

from pydantic import ValidationError

from aermod_screening.models import ScreeningScenario


ROOT = Path(__file__).resolve().parents[1]


def load_example() -> dict:
    return json.loads((ROOT / "examples" / "epa_point_flat_nodw.json").read_text())


class ScenarioValidationTests(unittest.TestCase):
    def test_epa_example_is_valid(self) -> None:
        scenario = ScreeningScenario.model_validate(load_example())
        self.assertEqual(len(scenario.receptors.distances()), 102)

    def test_invalid_temperature_range_is_rejected(self) -> None:
        data = load_example()
        data["meteorology"]["minimum_temperature_k"] = 320
        with self.assertRaisesRegex(ValidationError, "minimum_temperature_k"):
            ScreeningScenario.model_validate(data)

    def test_urban_population_is_required(self) -> None:
        data = load_example()
        data["dispersion_mode"] = "urban"
        with self.assertRaisesRegex(ValidationError, "urban_population"):
            ScreeningScenario.model_validate(data)

    def test_source_coordinates_must_be_a_valid_pair(self) -> None:
        data = load_example()
        data["source"]["latitude_deg"] = -32.8895
        with self.assertRaisesRegex(ValidationError, "longitude_deg"):
            ScreeningScenario.model_validate(data)

        data["source"]["longitude_deg"] = -68.8458
        scenario = ScreeningScenario.model_validate(data)
        self.assertEqual(scenario.source.latitude_deg, -32.8895)

    def test_complex_terrain_requires_coordinates_and_provider(self) -> None:
        data = load_example()
        data["terrain"] = {"mode": "complex", "provider": "copernicus"}
        with self.assertRaisesRegex(ValidationError, "coordenadas"):
            ScreeningScenario.model_validate(data)

        data["source"]["latitude_deg"] = -32.888355
        data["source"]["longitude_deg"] = -68.838844
        scenario = ScreeningScenario.model_validate(data)
        self.assertEqual(scenario.terrain.mode, "complex")
        self.assertEqual(scenario.terrain.provider, "copernicus")

    def test_flat_comparison_is_only_valid_for_complex_terrain(self) -> None:
        data = json.loads((ROOT / "examples/epa_point_flat_nodw.json").read_text())
        data["terrain"] = {"mode": "flat", "provider": None, "compare_with_flat": True}
        with self.assertRaises(ValidationError):
            ScreeningScenario.model_validate(data)

        data["source"]["latitude_deg"] = -33.064167
        data["source"]["longitude_deg"] = -68.973611
        data["terrain"] = {"mode": "complex", "provider": "copernicus", "compare_with_flat": True}
        self.assertTrue(ScreeningScenario.model_validate(data).terrain.compare_with_flat)

    def test_roughness_candidates_are_ordered_and_include_selected_value(self) -> None:
        data = load_example()
        data["meteorology"]["surface_roughness_m"] = .5
        data["meteorology"]["roughness_candidates_m"] = [.1, .5, .8]
        scenario = ScreeningScenario.model_validate(data)
        self.assertEqual(scenario.meteorology.roughness_candidates_m, [.1, .5, .8])

        data["meteorology"]["roughness_candidates_m"] = [.5, .1]
        with self.assertRaisesRegex(ValidationError, "ordenado"):
            ScreeningScenario.model_validate(data)
