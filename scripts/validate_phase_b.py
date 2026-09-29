#!/usr/bin/env python3
"""Valida la API, SQLite, ejecución diferida y artefactos de la Fase B."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fastapi.testclient import TestClient

from aermod_api.app import create_app
from aermod_api.config import Settings


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aermod", type=Path, required=True)
    parser.add_argument("--makemet", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"El directorio de validación no está vacío: {output}")
    output.mkdir(parents=True, exist_ok=True)

    app = create_app(
        Settings(
            database_path=output / "aermod.sqlite3",
            runs_directory=output / "runs",
            aermod_executable=args.aermod,
            makemet_executable=args.makemet,
        )
    )
    definition = json.loads(
        (ROOT / "examples" / "epa_point_flat_nodw.json").read_text(encoding="utf-8")
    )
    with TestClient(app) as client:
        health = client.get("/health")
        project = client.post(
            "/projects",
            json={"name": "Validación Fase B", "description": "Caso EPA desde API"},
        )
        project_id = project.json()["id"]
        scenario = client.post(
            f"/projects/{project_id}/scenarios",
            json={"name": "EPA point flat", "definition": definition},
        )
        scenario_id = scenario.json()["id"]
        submitted = client.post(f"/scenarios/{scenario_id}/runs")
        run_id = submitted.json()["id"]
        completed = client.get(f"/runs/{run_id}")
        result = client.get(f"/runs/{run_id}/result")
        artifacts = client.get(f"/runs/{run_id}/artifacts")
        repeated = client.post(f"/runs/{run_id}/repeat")
        repeated_id = repeated.json()["id"]
        repeated_completed = client.get(f"/runs/{repeated_id}")

    result_body = result.json() if result.status_code == 200 else {}
    artifact_body = artifacts.json() if artifacts.status_code == 200 else []
    checks = {
        "health": health.status_code == 200 and health.json()["status"] == "ok",
        "project_persisted": project.status_code == 201,
        "scenario_persisted": scenario.status_code == 201,
        "run_submitted_as_pending": submitted.status_code == 201
        and submitted.json()["status"] == "pending",
        "run_completed": completed.status_code == 200
        and completed.json()["status"] == "completed",
        "epa_result_preserved": abs(result_body.get("maximum_1h_ug_m3", 0) - 1.91323)
        <= 0.00001
        and result_body.get("maximum_distance_m") == 1610.0,
        "curve_available": len(result_body.get("concentration_by_distance", [])) == 102,
        "artifacts_indexed": len(artifact_body) >= 10
        and all(item.get("sha256") for item in artifact_body),
        "repeat_is_immutable": repeated.status_code == 201
        and repeated_id != run_id
        and repeated_completed.json()["status"] == "completed",
    }
    report = {
        "phase": "B — API y persistencia",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "project_id": project_id,
        "scenario_id": scenario_id,
        "run_id": run_id,
        "repeated_run_id": repeated_id,
        "actual": {
            "maximum_1h_ug_m3": result_body.get("maximum_1h_ug_m3"),
            "maximum_distance_m": result_body.get("maximum_distance_m"),
            "curve_points": len(result_body.get("concentration_by_distance", [])),
            "artifact_count": len(artifact_body),
        },
        "checks": checks,
    }
    report_path = output / "phase-b-validation.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Reporte: {report_path}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

