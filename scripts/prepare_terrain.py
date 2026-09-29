#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from aermod_screening.terrain import (
    copernicus_tile_name,
    download_copernicus,
    prepare_for_aermap,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Prepara un MDE GeoTIFF sin compresión para AERMAP.")
    parser.add_argument("--latitude", type=float, required=True)
    parser.add_argument("--longitude", type=float, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--provider", choices=["copernicus", "ign"], default="copernicus")
    parser.add_argument("--input", type=Path, help="Raster MDE-Ar descargado del IGN (obligatorio con --provider ign).")
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    if args.provider == "copernicus":
        tile = copernicus_tile_name(args.latitude, args.longitude)
        source = download_copernicus(args.latitude, args.longitude, args.output_dir / "downloads" / f"{tile}.tif")
    else:
        if args.input is None:
            parser.error("--input es obligatorio con --provider ign")
        source = args.input

    result = prepare_for_aermap(
        source,
        args.output_dir / "terrain-aermap.tif",
        latitude_deg=args.latitude,
        longitude_deg=args.longitude,
        provider=args.provider,
    )
    print(json.dumps(asdict(result), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
