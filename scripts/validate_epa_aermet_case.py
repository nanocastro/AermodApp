#!/usr/bin/env python3
"""Ejecuta el caso oficial EPA AERMET 26135 EX01 y compara SFC/PFL."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


EPA_PACKAGE_URL = (
    "https://gaftp.epa.gov/air/aqmg/scram/models/met/aermet/"
    "aermet_test_cases.zip"
)
INPUT_FILES = ("14735-88.UA", "S1473588.144", "EX01_S1.INP", "EX01_S2.INP")
RESULT_FILES = ("EX01_MP.SFC", "EX01_MP.PFL")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def normalized(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def validate(
    executable: Path, case_directory: Path, expected_directory: Path, output_directory: Path
) -> dict:
    executable = executable.resolve()
    case_directory = case_directory.resolve()
    expected_directory = expected_directory.resolve()
    output_directory = output_directory.resolve()
    if not executable.is_file():
        raise FileNotFoundError(executable)
    if output_directory.exists() and any(output_directory.iterdir()):
        raise FileExistsError(f"El directorio no está vacío: {output_directory}")
    output_directory.mkdir(parents=True, exist_ok=True)
    for name in INPUT_FILES:
        shutil.copy2(case_directory / name, output_directory / name)

    stages = []
    for stage in (1, 2):
        input_name = f"EX01_S{stage}.INP"
        console = output_directory / f"stage{stage}.console.txt"
        with console.open("w", encoding="ascii") as stream:
            completed = subprocess.run(
                [str(executable), input_name], cwd=output_directory,
                stdout=stream, stderr=subprocess.STDOUT, timeout=120, check=False,
            )
        console_text = console.read_text(encoding="latin-1")
        stages.append({
            "stage": stage,
            "exit_code": completed.returncode,
            "finished_successfully": "AERMET FINISHED SUCCESSFULLY" in console_text,
        })

    comparisons = []
    for name in RESULT_FILES:
        actual = output_directory / name
        expected = expected_directory / name
        if not actual.is_file() or not expected.is_file():
            raise FileNotFoundError(actual if not actual.is_file() else expected)
        actual_normalized = normalized(actual)
        expected_normalized = normalized(expected)
        comparisons.append({
            "file": name,
            "identical_after_newline_normalization": actual_normalized == expected_normalized,
            "line_count": len(actual_normalized.splitlines()),
            "actual_sha256": sha256_bytes(actual.read_bytes()),
            "expected_sha256": sha256_bytes(expected.read_bytes()),
            "actual_normalized_sha256": sha256_bytes(actual_normalized),
            "expected_normalized_sha256": sha256_bytes(expected_normalized),
        })

    passed = all(item["exit_code"] == 0 and item["finished_successfully"] for item in stages)
    passed = passed and all(
        item["identical_after_newline_normalization"] for item in comparisons
    )
    result = {
        "status": "PASS" if passed else "FAIL",
        "model": "AERMET",
        "version": "26135",
        "official_source": EPA_PACKAGE_URL,
        "official_case": "aermet_def_testcases_26135/EX01",
        "comparison_policy": "Exacta tras normalizar CRLF/LF; sin tolerancia numérica",
        "executable_sha256": sha256_bytes(executable.read_bytes()),
        "inputs": [
            {
                "file": name,
                "sha256": sha256_bytes((case_directory / name).read_bytes()),
            }
            for name in INPUT_FILES
        ],
        "stages": stages,
        "comparisons": comparisons,
    }
    (output_directory / "regression-result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aermet", type=Path, default=Path("bin/aermet"))
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--expected", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    result = validate(arguments.aermet, arguments.case, arguments.expected, arguments.output)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
