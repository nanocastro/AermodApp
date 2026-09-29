#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aermod_multisource import MultiSourceHourlyEngine, MultiSourceHourlyScenario


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Ejecuta AERMOD multifuente con meteorología horaria AERMET"
    )
    parser.add_argument("scenario", type=Path, help="Escenario multifuente horario JSON")
    parser.add_argument("--output", type=Path, required=True, help="Directorio de corrida vacío")
    parser.add_argument("--aermod", type=Path, default=ROOT / "bin/aermod")
    parser.add_argument("--meteorology-root", type=Path, default=ROOT / "data/hourly")
    parser.add_argument(
        "--terrain-directory", type=Path,
        help="Directorio AERMAP preparado, obligatorio para terreno complejo",
    )
    args = parser.parse_args()
    scenario = MultiSourceHourlyScenario.model_validate_json(
        args.scenario.read_text(encoding="utf-8")
    )
    result = MultiSourceHourlyEngine(
        aermod_executable=args.aermod,
        meteorology_root=args.meteorology_root,
    ).run(scenario, args.output, args.terrain_directory)
    print(json.dumps(result.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
