#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


EXPECTED = {"maximum_ug_m3": 12.17, "distance_m": 150.0, "direction_deg": 270}


def parse_official_output(text: str) -> dict[str, float | int]:
    location = re.search(
        r"DISTANCE FROM SOURCE\s+([0-9.]+) meters directed toward\s+([0-9]+) degrees",
        text,
    )
    if not location:
        raise ValueError("No se encontro la ubicacion del maximo en la salida AERSCREEN")
    summary = re.search(r"ELEVATED TERRAIN\s+([0-9.]+)", text)
    if not summary:
        raise ValueError("No se encontro el resumen de concentracion AERSCREEN")
    return {
        "maximum_ug_m3": float(summary.group(1)),
        "distance_m": float(location.group(1)),
        "direction_deg": int(location.group(2)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida el caso oficial EPA POINT_TERR_DW.")
    parser.add_argument("--case-dir", type=Path, required=True)
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    output_path = next((path for path in (case_dir / "aerscreen_terr_dw.out", case_dir / "AERSCREEN_TERR_DW.OUT") if path.is_file()), None)
    if output_path is None:
        raise FileNotFoundError("Falta la salida AERSCREEN_TERR_DW")
    log_path = next((path for path in (case_dir / "aerscreen_terr_dw.log", case_dir / "AERSCREEN_TERR_DW.log") if path.is_file()), None)
    log = log_path.read_text(encoding="latin-1") if log_path else ""
    observed = parse_official_output(output_path.read_text(encoding="latin-1"))
    passed = observed == EXPECTED and "AERSCREEN Finished Successfully" in log
    report = {
        "status": "PASS" if passed else "FAIL",
        "case": "EPA POINT_TERR_DW",
        "expected": EXPECTED,
        "observed": observed,
        "aerscreen_finished": "AERSCREEN Finished Successfully" in log,
        "aermap_finished": "AERMAP Finishes Successfully" in log,
        "receptors_skipped": 0 if "0 receptors skipped" in log else None,
        "versions": {"aermod": "26135", "aermap": "24142", "bpipprm": "04274"},
    }
    (case_dir / "terrain-downwash-validation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
