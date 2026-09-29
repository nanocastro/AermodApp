from __future__ import annotations

import json
import re
import subprocess
from collections import Counter, defaultdict
from pathlib import Path

from .noaa import sha256_file
from .stations import HourlyStation


SEASONS = ("winter", "spring", "summer", "autumn")


def _coordinate(value: float, positive: str, negative: str) -> str:
    return f"{abs(value):.4f}{positive if value >= 0 else negative}"


def generate_aermet_input(station: HourlyStation, year: int) -> str:
    start = f"{year}/1/1"
    end = f"{year}/12/31"
    surface_lat = _coordinate(station.surface_latitude_deg, "N", "S")
    surface_lon = _coordinate(station.surface_longitude_deg, "E", "W")
    upper_lat = _coordinate(station.upper_latitude_deg, "N", "S")
    upper_lon = _coordinate(station.upper_longitude_deg, "E", "W")
    timezone_hours = abs(station.utc_offset_hours)
    stem = f"{station.slug}-{year}"

    lines = [
        "JOB",
        f"  REPORT {stem}-report.txt",
        f"  MESSAGES {stem}-messages.txt",
        "",
        "UPPERAIR",
        f"  DATA input/{station.slug}-igra.txt IGRA",
        f"  EXTRACT {stem}-upper-extract.txt",
        f"  QAOUT {stem}-upper-qaout.txt",
        f"  XDATES {start} TO {end}",
        f"  LOCATION {station.upper_station_id} {upper_lon} {upper_lat} {timezone_hours} {station.upper_elevation_m:.1f}",
        "",
        "SURFACE",
        f"  DATA input/{station.slug}-{year}.isd ISHD",
        f"  EXTRACT {stem}-surface-extract.txt",
        f"  QAOUT {stem}-surface-qaout.txt",
        f"  XDATES {start} TO {end}",
        f"  LOCATION {station.surface_station_id} {surface_lat} {surface_lon} {timezone_hours} {station.surface_elevation_m:.1f}",
        "",
        "METPREP",
        f"  OUTPUT {stem}.sfc",
        f"  PROFILE {stem}.pfl",
        f"  LOCATION {station.name} {surface_lon} {surface_lat} {timezone_hours}",
        "  METHOD UASELECT SUNRISE",
        "  METHOD REFLEVEL SUBNWS",
        f"  NWS_HGT WIND {station.anemometer_height_m:.1f}",
        "  FREQ_SECT SEASONAL 12",
    ]
    for index in range(12):
        lines.append(f"  SECTOR {index + 1} {index * 30} {(index + 1) * 30}")
    for frequency_index, season in enumerate(SEASONS, start=1):
        roughness_values = station.roughness_by_season[season]
        if len(roughness_values) != 12:
            raise ValueError(f"{station.slug}: {season} debe contener 12 sectores")
        for sector_index, roughness in enumerate(roughness_values, start=1):
            lines.append(
                f"  SITE_CHAR {frequency_index} {sector_index} "
                f"{station.albedo:.6f} {station.bowen_ratio:.6f} {roughness:.6f}"
            )
    lines.append("")
    return "\n".join(lines)


def summarize_surface_file(path: Path) -> dict:
    total = usable = calm = noncalm_missing_direction = 0
    monthly: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    flags: Counter[str] = Counter()
    with path.open(encoding="ascii", errors="replace") as stream:
        next(stream)
        for line in stream:
            fields = line.split()
            if len(fields) < 17:
                continue
            total += 1
            month = int(fields[1])
            monthly[month][0] += 1
            heat_flux = float(fields[5])
            wind_speed = float(fields[15])
            wind_direction = float(fields[16])
            is_usable = heat_flux > -900 and wind_speed < 900 and wind_direction < 900
            usable += int(is_usable)
            monthly[month][1] += int(is_usable)
            calm += int(wind_speed == 0)
            noncalm_missing_direction += int(
                wind_direction >= 999 and wind_speed < 900 and wind_speed > 0
            )
            if len(fields) >= 2:
                flags[" ".join(fields[-2:])] += 1
    return {
        "total_hours": total,
        "usable_hours": usable,
        "usable_percent": usable / total * 100 if total else 0,
        "calm_hours": calm,
        "noncalm_missing_direction_hours": noncalm_missing_direction,
        "monthly": {
            str(month): {
                "total_hours": values[0],
                "usable_hours": values[1],
                "usable_percent": values[1] / values[0] * 100 if values[0] else 0,
            }
            for month, values in sorted(monthly.items())
        },
        "terminal_flags": dict(flags),
    }


def summarize_report_file(path: Path) -> dict:
    text = path.read_text(encoding="ascii", errors="replace")
    patterns = {
        "days_without_soundings": r"NUMBER OF DAYS WITH NO SOUNDINGS:\s+(\d+)",
        "calm_hours": r"NUMBER OF TOTAL CALMS:\s+(\d+)",
        "variable_wind_hours": r"NUMBER OF VARIABLE WINDS:\s+(\d+)",
        "error_messages": r"ERROR MESSAGES\s+(\d+) MESSAGES",
        "warning_messages": r"WARNING MESSAGES\s+(\d+) MESSAGES",
    }
    result = {}
    for key, pattern in patterns.items():
        match = re.search(pattern, text)
        if not match:
            raise ValueError(f"No se encontró {key} en {path}")
        result[key] = int(match.group(1))
    return result


def run_aermet(executable: Path, station: HourlyStation, year: int, directory: Path) -> dict:
    executable = executable.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    directory = directory.resolve()
    input_path = directory / f"{station.slug}-{year}.inp"
    input_path.write_text(generate_aermet_input(station, year), encoding="ascii")
    console_path = directory / f"{station.slug}-{year}-console.txt"
    with console_path.open("w", encoding="ascii") as console:
        completed = subprocess.run(
            [str(executable), input_path.name],
            cwd=directory,
            stdout=console,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=600,
            check=False,
        )
    surface = directory / f"{station.slug}-{year}.sfc"
    profile = directory / f"{station.slug}-{year}.pfl"
    report = directory / f"{station.slug}-{year}-report.txt"
    if completed.returncode != 0 or not surface.is_file() or not profile.is_file():
        raise RuntimeError(
            f"AERMET falló para {station.slug} (código {completed.returncode}); "
            f"revise {console_path.name}"
        )
    result = {
        "station": station.slug,
        "year": year,
        "aermet_exit_code": completed.returncode,
        "aermet_version_target": "26135",
        "aermet_executable_sha256": sha256_file(executable),
        "surface_summary": summarize_surface_file(surface),
        "aermet_report_summary": summarize_report_file(report),
        "surface_parameter_provenance": {
            "albedo_bowen_period": list(station.surface_parameter_period),
            "albedo": station.albedo,
            "bowen_ratio": station.bowen_ratio,
            "roughness": "WorldCover airport crosswalk, 12 sectors, ZORAD-like aggregation",
        },
        "artifacts": [
            {"path": path.name, "size_bytes": path.stat().st_size, "sha256": sha256_file(path)}
            for path in sorted(directory.glob(f"{station.slug}-{year}*"))
            if path.is_file() and not path.name.endswith("-result.json")
        ],
    }
    (directory / f"{station.slug}-{year}-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result
