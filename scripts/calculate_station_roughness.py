#!/usr/bin/env python3
"""Calculate AERSURFACE-like sector roughness from a cached WorldCover XYZ."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from aermod_api.surface import (
    ROUGHNESS_SEASONS,
    aersurface_like_directional_roughness,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--latitude", required=True, type=float)
    parser.add_argument("--longitude", required=True, type=float)
    parser.add_argument("--xyz", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--airport", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    points = []
    with args.xyz.open(encoding="utf-8") as stream:
        for line in stream:
            lon, lat, value = line.split()
            points.append((float(lon), float(lat), int(float(value))))

    seasons = {
        season: aersurface_like_directional_roughness(
            points,
            args.latitude,
            args.longitude,
            season=season,
            airport=args.airport,
        )
        for season in ROUGHNESS_SEASONS
    }
    result = {
        "site": args.name,
        "latitude_deg": args.latitude,
        "longitude_deg": args.longitude,
        "method": "AERSURFACE ZORAD spatial aggregation adapted to ESA WorldCover",
        "is_official_aersurface_output": False,
        "sector_width_deg": 30,
        "radius_m": 1000.0,
        "pixel_resolution_m": 10.0,
        "minimum_weighting_distance_m": 5.0,
        "land_cover": "ESA WorldCover 2021 v200",
        "roughness_crosswalk": "EPA AERSURFACE 26135 with ECMWF fallbacks",
        "airport_adjustment": args.airport,
        "seasons": seasons,
    }
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
