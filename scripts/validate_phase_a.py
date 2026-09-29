#!/usr/bin/env python3
"""Valida la Fase A reconstruyendo el caso EPA íntegramente desde JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aermod_screening import ScreeningEngine, ScreeningScenario


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MAXIMUM = 1.913
EXPECTED_DISTANCE = 1610.0
MAXIMUM_TOLERANCE = 0.0005
DISTANCE_TOLERANCE = 0.01


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aermod", type=Path, required=True)
    parser.add_argument("--makemet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    scenario = ScreeningScenario.model_validate_json(
        (ROOT / "examples" / "epa_point_flat_nodw.json").read_text(encoding="utf-8")
    )
    result = ScreeningEngine(
        aermod_executable=args.aermod,
        makemet_executable=args.makemet,
    ).run(scenario, args.output_dir)

    checks = {
        "structured_scenario_generated_input": True,
        "aermod_finished_successfully": result.aermod_finished_successfully,
        "no_fatal_errors": result.no_fatal_errors,
        "maximum_matches_epa": abs(result.maximum_1h_ug_m3 - EXPECTED_MAXIMUM)
        <= MAXIMUM_TOLERANCE,
        "distance_matches_epa": abs(result.maximum_distance_m - EXPECTED_DISTANCE)
        <= DISTANCE_TOLERANCE,
        "curve_was_parsed": len(result.concentration_by_distance) == 102,
    }
    passed = all(checks.values())
    report = {
        "phase": "A — motor como servicio",
        "status": "PASS" if passed else "FAIL",
        "expected": {
            "maximum_1h_ug_m3": EXPECTED_MAXIMUM,
            "maximum_distance_m": EXPECTED_DISTANCE,
        },
        "actual": {
            "maximum_1h_ug_m3": result.maximum_1h_ug_m3,
            "maximum_distance_m": result.maximum_distance_m,
            "curve_points": len(result.concentration_by_distance),
        },
        "checks": checks,
    }
    report_path = args.output_dir.resolve() / "phase-a-validation.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Reporte: {report_path}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

