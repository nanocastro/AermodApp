from __future__ import annotations

import unittest
from pathlib import Path

from aermod_screening.generator import (
    TerrainReceptor,
    aermod_ascii,
    generate_aermod_input,
    generate_complex_aermod_input,
    generate_makemet_prompts,
)
from aermod_screening.models import ScreeningScenario


ROOT = Path(__file__).resolve().parents[1]


def scenario() -> ScreeningScenario:
    return ScreeningScenario.model_validate_json(
        (ROOT / "examples" / "epa_point_flat_nodw.json").read_text()
    )


class GeneratorTests(unittest.TestCase):
    def test_generates_complex_terrain_keywords(self) -> None:
        configured = scenario().model_copy(deep=True)
        configured.receptors.receptor_height_m = 1.0
        generated = generate_complex_aermod_input(
            configured, source_x=515073.46, source_y=6361078.41,
            source_elevation_m=757.53,
            receptors=[TerrainReceptor(515073.46, 6361128.41, 758.2, 760.1)],
        )
        self.assertIn("MODELOPT CONC SCREEN ELEV", generated)
        self.assertIn("515073.46 6361078.41 757.53", generated)
        self.assertIn("758.20 760.10", generated)
        control, remainder = generated.split("CO FINISHED", maxsplit=1)
        receptor = remainder.split("RE STARTING", maxsplit=1)[1].split("RE FINISHED", maxsplit=1)[0]
        self.assertIn("FLAGPOLE 1.00", control)
        self.assertNotIn("FLAGPOLE", receptor)

    def test_normalizes_user_title_to_aermod_ascii(self) -> None:
        self.assertEqual(aermod_ascii("Mendoza — emisión crítica"), "Mendoza - emision critica")

    def test_generates_screening_input(self) -> None:
        generated = generate_aermod_input(scenario())
        self.assertIn("MODELOPT CONC SCREEN FLAT", generated)
        self.assertIn("SRCPARAM SOURCE 1 61 415 11 5", generated)
        self.assertEqual(generated.count("DISCCART"), 102)
        self.assertIn("SURFFILE screening.sfc FREE", generated)

    def test_places_flagpole_height_in_control_pathway(self) -> None:
        configured = scenario().model_copy(deep=True)
        configured.receptors.receptor_height_m = 1.0
        generated = generate_aermod_input(configured)
        control, remainder = generated.split("CO FINISHED", maxsplit=1)
        receptor = remainder.split("RE STARTING", maxsplit=1)[1].split("RE FINISHED", maxsplit=1)[0]
        self.assertIn("FLAGPOLE 1.00", control)
        self.assertNotIn("FLAGPOLE", receptor)

    def test_generates_makemet_prompts(self) -> None:
        generated = generate_makemet_prompts(scenario())
        self.assertTrue(generated.startswith("screening.sfc\nscreening.pfl\n"))
        self.assertIn("270.0000 310.0000", generated)
        self.assertIn("0.6300", generated)

    def test_generates_single_area_urban_keywords(self) -> None:
        data = scenario().model_dump()
        data["dispersion_mode"] = "urban"
        data["urban_population"] = 100000
        generated = generate_aermod_input(ScreeningScenario.model_validate(data))
        self.assertIn("URBANOPT 100000\n", generated)
        self.assertIn("URBANSRC SOURCE\n", generated)
        self.assertNotIn("URBAN1", generated)
