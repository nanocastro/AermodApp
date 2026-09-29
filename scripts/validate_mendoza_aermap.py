#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path

from aermod_screening.terrain import generate_aermap_input


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba AERMAP con el MDE preparado para Mendoza.")
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--terrain", type=Path, required=True)
    parser.add_argument("--aermap", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    terrain = args.output_dir / "terrain.tif"
    executable = args.output_dir / "aermap"
    shutil.copy2(args.terrain, terrain)
    shutil.copy2(args.aermap, executable)
    executable.chmod(0o755)
    (args.output_dir / "AERMAP.INP").write_text(
        generate_aermap_input(
            terrain.name,
            latitude_deg=args.latitude,
            longitude_deg=args.longitude,
        ),
        encoding="ascii",
    )
    completed = subprocess.run(
        [str(executable.resolve()), "AERMAP.INP", "AERMAP.OUT"],
        cwd=args.output_dir,
        capture_output=True,
        text=True,
    )
    (args.output_dir / "aermap.stdout").write_text(completed.stdout + completed.stderr, encoding="utf-8")
    output_path = args.output_dir / "AERMAP.OUT"
    output = output_path.read_text(encoding="latin-1") if output_path.exists() else completed.stdout + completed.stderr
    success = "AERMAP Finishes Successfully" in output
    report = {
        "status": "PASS" if success and completed.returncode == 0 else "FAIL",
        "aermap_returncode": completed.returncode,
        "source_output": (args.output_dir / "source-aermap.out").exists(),
        "receptor_output": (args.output_dir / "receptors-aermap.out").exists(),
    }
    (args.output_dir / "validation-report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
