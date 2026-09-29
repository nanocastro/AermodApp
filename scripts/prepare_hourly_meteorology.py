#!/usr/bin/env python3
"""Descarga NOAA ISD/IGRA y prepara meteorología AERMET auditable."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from aermod_hourly import HOURLY_STATIONS, prepare_noaa_inputs, run_aermet


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--station", choices=sorted(HOURLY_STATIONS), required=True)
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument("--output", type=Path, default=Path("data/hourly"))
    parser.add_argument("--aermet", type=Path, help="Ejecutable AERMET 26135; si se omite solo prepara NOAA")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    station = HOURLY_STATIONS[args.station]
    directory = args.output / station.slug / str(args.year)
    manifest = prepare_noaa_inputs(station, args.year, directory)
    result = {"manifest": manifest}
    if args.aermet:
        result["aermet"] = run_aermet(args.aermet, station, args.year, directory)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
