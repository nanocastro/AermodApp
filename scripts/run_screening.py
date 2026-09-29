#!/usr/bin/env python3
"""Ejecuta un escenario JSON mediante el servicio de screening."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aermod_screening import ScreeningEngine, ScreeningScenario


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", type=Path)
    parser.add_argument("--aermod", type=Path, required=True)
    parser.add_argument("--makemet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    scenario = ScreeningScenario.model_validate_json(args.scenario.read_text(encoding="utf-8"))
    engine = ScreeningEngine(
        aermod_executable=args.aermod,
        makemet_executable=args.makemet,
    )
    result = engine.run(scenario, args.output_dir)
    print(json.dumps(result.model_dump(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

