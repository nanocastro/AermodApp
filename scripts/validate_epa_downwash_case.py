#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EXPECTED = {"maximum_ug_m3": 12.19, "distance_m": 150.0, "direction_deg": 250}


def parse_downwash_result(output: str) -> dict[str, float | int]:
    maximum = re.search(r"FLAT TERRAIN\s+([0-9.E+-]+)", output)
    location = re.search(
        r"DISTANCE FROM SOURCE\s+([0-9.]+) meters directed toward\s+([0-9]+) degrees",
        output,
    )
    if not maximum or not location:
        raise ValueError("No se encontro el resumen de downwash de AERSCREEN")
    return {
        "maximum_ug_m3": float(maximum.group(1)),
        "distance_m": float(location.group(1)),
        "direction_deg": int(location.group(2)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida EPA POINT_FLAT_DW ya ejecutado.")
    parser.add_argument("--case-dir", type=Path, required=True)
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    output = (case_dir / "AERSCREEN_FLAT_DW.OUT").read_text(encoding="latin-1")
    log_path = case_dir / "AERSCREEN_FLAT_DW.log"
    log = log_path.read_text(encoding="latin-1") if log_path.is_file() else ""
    observed = parse_downwash_result(output)
    report = {
        "status": "PASS" if observed == EXPECTED else "FAIL",
        "case": "EPA POINT_FLAT_DW", "expected": EXPECTED, "observed": observed,
        "aerscreen_finished": "AERSCREEN Finished Successfully" in log,
        "no_errors_or_warnings": "With no errors or warnings" in log,
        "bpipprm_version": "04274",
    }
    (case_dir / "validation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" and report["aerscreen_finished"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
