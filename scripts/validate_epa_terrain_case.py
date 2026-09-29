#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path

EXPECTED = {"maximum_ug_m3": 1.914, "distance_m": 1620.0, "direction_deg": 110}


def parse_result(output: str) -> dict[str, float | int]:
    maximum = re.search(r"ELEVATED TERRAIN\s+([0-9.E+-]+)", output)
    location = re.search(
        r"DISTANCE FROM SOURCE\s+([0-9.]+) meters directed toward\s+([0-9]+) degrees",
        output,
    )
    if not maximum or not location:
        raise ValueError("No se encontro el resumen de terreno elevado de AERSCREEN")
    return {
        "maximum_ug_m3": float(maximum.group(1)),
        "distance_m": float(location.group(1)),
        "direction_deg": int(location.group(2)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida el caso oficial EPA POINT_TERR_NODW.")
    parser.add_argument("--case-dir", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    case_dir = args.case_dir.resolve()
    environment = os.environ.copy()
    environment["PATH"] = f"{case_dir}{os.pathsep}{environment['PATH']}"
    completed = subprocess.run(
        [str(case_dir / "aerscreen")], cwd=case_dir, input="Y\n\nK\n",
        capture_output=True, text=True, timeout=args.timeout, env=environment,
    )
    console = completed.stdout + completed.stderr
    (case_dir / "validation-console.txt").write_text(console, encoding="utf-8")
    result = parse_result(console)
    passed = completed.returncode == 0 and result == EXPECTED and "Finished Successfully" in console
    report = {
        "status": "PASS" if passed else "FAIL", "case": "EPA POINT_TERR_NODW",
        "expected": EXPECTED, "observed": result, "returncode": completed.returncode,
        "aerscreen_finished": "Finished Successfully" in console,
        "flowsector_receptors_skipped": 0 if "0 receptors skipped for FLOWSECTOR" in console else None,
        "refine_receptors_skipped": 0 if "0 receptors skipped for REFINE" in console else None,
    }
    (case_dir / "validation-report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, indent=2))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
