from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.validate_epa_aermet_case import validate


ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT / "build/aermet-epa-regression/case"
EXPECTED = ROOT / "build/aermet-epa-regression/expected"


class AermetEpaRegressionTests(unittest.TestCase):
    @unittest.skipUnless(
        (CASE / "EX01_S1.INP").is_file() and (EXPECTED / "EX01_MP.SFC").is_file(),
        "Caso oficial EPA EX01 no descargado",
    )
    def test_official_ex01_outputs_match_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = validate(ROOT / "bin/aermet", CASE, EXPECTED, Path(directory))
        self.assertEqual(result["status"], "PASS")
        self.assertTrue(all(item["finished_successfully"] for item in result["stages"]))
        self.assertTrue(all(
            item["identical_after_newline_normalization"]
            for item in result["comparisons"]
        ))


if __name__ == "__main__":
    unittest.main()
