#!/usr/bin/env python3
"""Reproduce el caso oficial EPA AERSCREEN point/flat/no-downwash."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

PACKAGES = {
    "aermod_source.zip": {
        "url": "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/preferred/aermod/aermod_source.zip",
        "sha256": "5092c1d68b77d9407c9f67d497b440a79d2ee746f9ed6515a63ad4a5b11cd8ed",
    },
    "makemet_code.zip": {
        "url": "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/screening/aerscreen/makemet_code.zip",
        "sha256": "c9f3be6b44d82681168b41673a96c31b6c8ac78de36a0627b5473c60360a9f62",
    },
    "aerscreen_test_cases.zip": {
        "url": "https://gaftp.epa.gov/Air/aqmg/SCRAM/models/screening/aerscreen/aerscreen_test_cases.zip",
        "sha256": "6080483105b10e7fa1e06b90c52ab1abb6636e89f9b92a8bdb0b7cbcb46c6f0b",
    },
}

AERMOD_OBJECTS = [
    "modules",
    "grsm",
    "aermod",
    "setup",
    "coset",
    "soset",
    "reset",
    "meset",
    "ouset",
    "inpsum",
    "metext",
    "iblval",
    "siggrid",
    "tempgrid",
    "windgrid",
    "calc1",
    "calc2",
    "prise",
    "arise",
    "prime",
    "sigmas",
    "pitarea",
    "uninam",
    "output",
    "evset",
    "evcalc",
    "evoutput",
    "rline",
    "bline",
]

CASE_MEMBERS = [
    "point/AERSCREEN_FLAT_NODW.inp",
    "point/AERSCREEN_FLAT_NODW.OUT",
    "point/AERSCREEN_FLAT_NODW.log",
    "point/AERSCREEN_FLAT_NODW_max_conc_distance.txt",
    "point/aerscreen_point_README.txt",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_and_verify(cache_dir: Path, name: str) -> Path:
    spec = PACKAGES[name]
    destination = cache_dir / name
    if destination.exists() and sha256(destination) == spec["sha256"]:
        print(f"[cache] {name}")
        return destination

    cache_dir.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")
    print(f"[download] {spec['url']}")
    with urllib.request.urlopen(spec["url"]) as response, partial.open("wb") as output:
        shutil.copyfileobj(response, output)
    partial.replace(destination)

    actual = sha256(destination)
    if actual != spec["sha256"]:
        raise RuntimeError(
            f"SHA-256 inesperado para {name}: {actual}; esperado: {spec['sha256']}"
        )
    return destination


def extract_zip(archive: Path, destination: Path, members: list[str] | None = None) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as package:
        selected = package.namelist() if members is None else members
        available = set(package.namelist())
        for member in selected:
            if member not in available:
                raise RuntimeError(f"No se encontró {member} en {archive.name}")
            target = (destination / member).resolve()
            if destination.resolve() not in target.parents:
                raise RuntimeError(f"Ruta insegura dentro de {archive.name}: {member}")
            package.extract(member, destination)


def run(command: list[str], *, cwd: Path, stdout: Path | None = None) -> None:
    print("[run]", " ".join(command))
    if stdout is None:
        subprocess.run(command, cwd=cwd, check=True)
        return
    with stdout.open("w", encoding="utf-8") as stream:
        subprocess.run(command, cwd=cwd, check=True, stdout=stream, stderr=subprocess.STDOUT)


def compile_models(work_dir: Path) -> tuple[Path, Path]:
    source_dir = work_dir / "sources"
    aermod_sources = source_dir / "aermod_source_v26135"
    makemet_sources = source_dir / "makemet"
    makemet_sources.mkdir(parents=True, exist_ok=True)

    extract_zip(work_dir / "downloads" / "aermod_source.zip", source_dir)
    extract_zip(work_dir / "downloads" / "makemet_code.zip", makemet_sources)

    compile_steps = [
        "set -eu",
        "flags='-fbounds-check -Wuninitialized -O2'",
    ]
    for source in AERMOD_OBJECTS:
        compile_steps.append(f"gfortran -c $flags {source}.f")
    objects = " ".join(f"{name}.o" for name in AERMOD_OBJECTS)
    compile_steps.append(f"gfortran -O2 -o aermod {objects}")
    run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{aermod_sources}:/src",
            "-w",
            "/src",
            "gcc:15",
            "bash",
            "-lc",
            "; ".join(compile_steps),
        ],
        cwd=work_dir,
        stdout=work_dir / "compile-aermod.log",
    )
    run(
        [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{makemet_sources}:/src",
            "-w",
            "/src",
            "gcc:15",
            "gfortran",
            "-O2",
            "-std=legacy",
            "-o",
            "makemet",
            "MAKEMET.FOR",
        ],
        cwd=work_dir,
        stdout=work_dir / "compile-makemet.log",
    )
    return aermod_sources / "aermod", makemet_sources / "makemet"


def parse_expected(reference: Path) -> tuple[float, float]:
    text = reference.read_text(encoding="latin-1")
    concentration = re.search(r"FLAT TERRAIN\s+([0-9.E+-]+)", text)
    distance = re.search(r"DISTANCE FROM SOURCE\s+([0-9.]+)\s+meters", text)
    if not concentration or not distance:
        raise RuntimeError("No se pudo interpretar la salida de referencia EPA")
    return float(concentration.group(1)), float(distance.group(1))


def parse_actual(rank_file: Path) -> tuple[float, float]:
    for line in rank_file.read_text(encoding="latin-1").splitlines():
        match = re.match(r"\s*1\s+([0-9.E+-]+)\s+\d{8}\s+([0-9.-]+)", line)
        if match:
            return float(match.group(1)), float(match.group(2))
    raise RuntimeError("No se pudo interpretar AERSCREEN.FIL")


def prepare_and_run_case(work_dir: Path, aermod: Path, makemet: Path) -> dict[str, object]:
    extracted = work_dir / "official-case"
    extract_zip(
        work_dir / "downloads" / "aerscreen_test_cases.zip",
        extracted,
        CASE_MEMBERS,
    )
    case_dir = work_dir / "run"
    case_dir.mkdir(parents=True, exist_ok=True)
    for source in (extracted / "point").iterdir():
        if source.is_file():
            shutil.copy2(source, case_dir / source.name)
    shutil.copy2(aermod, case_dir / "aermod")
    shutil.copy2(makemet, case_dir / "makemet")
    shutil.copy2(case_dir / "AERSCREEN_FLAT_NODW.inp", case_dir / "aermod.inp")

    # Invierno, sector espacial 2, según los metadatos del caso oficial.
    prompts = "\n".join(
        [
            "aerscreen_01_02.sfc",
            "aerscreen_01_02.pfl",
            "0.5000",
            "10.0000",
            "N",
            "1",
            "270",
            "270.0000  310.0000",
            "0.1400",
            "0.6300",
            "0.1280",
            "n",
            "",
        ]
    )
    (case_dir / "prompts.inp").write_text(prompts, encoding="ascii")
    with (case_dir / "prompts.inp").open("r", encoding="ascii") as input_stream, (
        case_dir / "makemet.stdout"
    ).open("w", encoding="utf-8") as output_stream:
        subprocess.run(
            ["./makemet"],
            cwd=case_dir,
            check=True,
            stdin=input_stream,
            stdout=output_stream,
            stderr=subprocess.STDOUT,
        )
    run(["./aermod"], cwd=case_dir, stdout=case_dir / "aermod.stdout")

    model_output = (case_dir / "aermod.out").read_text(encoding="latin-1")
    successful = "AERMOD Finishes Successfully" in model_output
    no_fatal = re.search(
        r"FATAL ERROR MESSAGES[\s*]+NONE", model_output
    ) is not None
    expected_concentration, expected_distance = parse_expected(
        case_dir / "AERSCREEN_FLAT_NODW.OUT"
    )
    actual_concentration, actual_distance = parse_actual(case_dir / "AERSCREEN.FIL")
    concentration_tolerance = 0.0005
    distance_tolerance = 0.01
    passed = (
        successful
        and no_fatal
        and abs(actual_concentration - expected_concentration) <= concentration_tolerance
        and abs(actual_distance - expected_distance) <= distance_tolerance
    )
    return {
        "status": "PASS" if passed else "FAIL",
        "case": "EPA AERSCREEN point / flat terrain / no downwash",
        "versions": {"aermod": "26135", "makemet": "16216"},
        "expected": {
            "maximum_1h_ug_m3": expected_concentration,
            "distance_m": expected_distance,
        },
        "actual": {
            "maximum_1h_ug_m3": actual_concentration,
            "distance_m": actual_distance,
        },
        "tolerances": {
            "maximum_1h_ug_m3_absolute": concentration_tolerance,
            "distance_m_absolute": distance_tolerance,
        },
        "checks": {
            "aermod_finished_successfully": successful,
            "no_fatal_errors": no_fatal,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, default=ROOT / ".cache" / "epa")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "epa-point-flat-nodw")
    args = parser.parse_args()

    if shutil.which("docker") is None:
        print("ERROR: Docker no está disponible", file=sys.stderr)
        return 2

    cache_dir = args.cache_dir.resolve()
    output_dir = args.output_dir.resolve()
    if output_dir.exists():
        shutil.rmtree(output_dir)
    downloads = output_dir / "downloads"
    downloads.mkdir(parents=True)

    try:
        for name in PACKAGES:
            cached = download_and_verify(cache_dir, name)
            shutil.copy2(cached, downloads / name)
        aermod, makemet = compile_models(output_dir)
        report = prepare_and_run_case(output_dir, aermod, makemet)
    except (OSError, RuntimeError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    report_path = output_dir / "validation-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Reporte: {report_path}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
