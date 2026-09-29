from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from aermod_api.app import create_app
from aermod_api.config import Settings


ROOT = Path(__file__).resolve().parents[1]
AERMOD = ROOT / "build/epa-point-flat-nodw/sources/aermod_source_v26135/aermod"
MAKEMET = ROOT / "build/epa-point-flat-nodw/sources/makemet/makemet"
CORDOBA_DEM = ROOT / "data/private-validation/cordoba-terrain/terrain-aermap.tif"


@unittest.skipUnless(AERMOD.is_file() and MAKEMET.is_file(), "Binarios de validación no disponibles")
class ApiIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        app = create_app(
            Settings(
                database_path=root / "api.sqlite3",
                runs_directory=root / "runs",
                credentials_file=root / ".credentials",
                aermod_executable=AERMOD,
                makemet_executable=MAKEMET,
                hourly_directory=ROOT / "data/hourly",
                terrain_directory=root / "terrain",
                aermap_executable=ROOT / "bin/aermap",
            )
        )
        self.client = TestClient(app)
        self.definition = json.loads(
            (ROOT / "examples/epa_point_flat_nodw.json").read_text(encoding="utf-8")
        )

    def tearDown(self) -> None:
        self.client.close()
        self.temporary.cleanup()

    def test_complete_project_scenario_run_flow(self) -> None:
        health = self.client.get("/health")
        self.assertEqual(health.status_code, 200)
        self.assertTrue(health.json()["aermod_available"])

        project = self.client.post(
            "/projects",
            json={"name": "Validación EPA", "description": "Fase B", "responsible": "FCA"},
        )
        self.assertEqual(project.status_code, 201)
        project_id = project.json()["id"]

        scenario = self.client.post(
            f"/projects/{project_id}/scenarios",
            json={"name": "Point flat", "definition": self.definition},
        )
        self.assertEqual(scenario.status_code, 201, scenario.text)
        scenario_id = scenario.json()["id"]

        run = self.client.post(f"/scenarios/{scenario_id}/runs")
        self.assertEqual(run.status_code, 201, run.text)
        run_body = run.json()
        self.assertEqual(run_body["status"], "pending")
        run_id = run_body["id"]

        completed = self.client.get(f"/runs/{run_id}")
        self.assertEqual(completed.json()["status"], "completed")
        self.assertAlmostEqual(
            completed.json()["result"]["maximum_1h_ug_m3"], 1.91323, places=5
        )
        self.assertEqual(completed.json()["result"]["maximum_distance_m"], 1610.0)

        result = self.client.get(f"/runs/{run_id}/result")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()["concentration_by_distance"]), 102)

        artifacts = self.client.get(f"/runs/{run_id}/artifacts")
        self.assertEqual(artifacts.status_code, 200)
        result_artifact = next(item for item in artifacts.json() if item["name"] == "result.json")
        downloaded = self.client.get(
            f"/runs/{run_id}/artifacts/{result_artifact['id']}"
        )
        self.assertEqual(downloaded.status_code, 200)
        self.assertEqual(downloaded.json()["maximum_distance_m"], 1610.0)

        repeated = self.client.post(f"/runs/{run_id}/repeat")
        self.assertEqual(repeated.status_code, 201)
        self.assertEqual(repeated.json()["status"], "pending")
        self.assertNotEqual(repeated.json()["id"], run_id)
        repeated_completed = self.client.get(f"/runs/{repeated.json()['id']}")
        self.assertEqual(repeated_completed.json()["status"], "completed")

    def test_rejects_invalid_scenario_before_persistence(self) -> None:
        project = self.client.post("/projects", json={"name": "Validation"}).json()
        invalid = self.definition
        invalid["source"]["emission_rate_g_s"] = -1
        response = self.client.post(
            f"/projects/{project['id']}/scenarios",
            json={"name": "Invalid", "definition": invalid},
        )
        self.assertEqual(response.status_code, 422)
        scenarios = self.client.get(f"/projects/{project['id']}/scenarios")
        self.assertEqual(scenarios.json(), [])

    @unittest.skipUnless(
        (ROOT / "data/hourly/cordoba-aero/2024/cordoba-aero-2024.sfc").is_file(),
        "Meteorología horaria de Córdoba no disponible",
    )
    def test_complete_hourly_run_flow(self) -> None:
        project = self.client.post("/projects", json={"name": "Horario 2024"}).json()
        definition = json.loads(
            (ROOT / "examples/hourly_cordoba_2024.json").read_text(encoding="utf-8")
        )
        scenario = self.client.post(
            f"/projects/{project['id']}/scenarios",
            json={"name": "Córdoba horario", "definition": definition},
        )
        self.assertEqual(scenario.status_code, 201, scenario.text)
        self.assertEqual(scenario.json()["definition"]["run_mode"], "hourly")
        run = self.client.post(f"/scenarios/{scenario.json()['id']}/runs")
        self.assertEqual(run.status_code, 201, run.text)
        completed = self.client.get(f"/runs/{run.json()['id']}")
        self.assertEqual(completed.json()["status"], "completed", completed.text)
        result = completed.json()["result"]
        self.assertEqual(result["run_mode"], "hourly")
        self.assertEqual(result["meteorology_usable_hours"], 8095)
        self.assertAlmostEqual(result["maximum_1h"]["concentration_ug_m3"], 5.13798, places=5)
        self.assertEqual(
            [item["averaging_period"] for item in result["period_maxima"]],
            ["1h", "3h", "8h", "24h", "annual"],
        )
        self.assertAlmostEqual(result["period_maxima"][1]["concentration_ug_m3"], 2.83769, places=5)
        self.assertAlmostEqual(result["period_maxima"][2]["concentration_ug_m3"], 2.22521, places=5)
        self.assertAlmostEqual(result["period_maxima"][3]["concentration_ug_m3"], 1.10383, places=5)
        self.assertAlmostEqual(result["period_maxima"][4]["concentration_ug_m3"], 0.145113, places=6)
        self.assertIsNone(result["period_maxima"][4]["aermod_timestamp"])
        self.assertEqual(len(result["maximum_1h_by_receptor"]), 1800)
        self.assertEqual(result["maximum_condition"]["wind_direction_deg"], 360.0)
        self.assertEqual(result["maximum_condition"]["wind_speed_m_s"], 1.0)

    @unittest.skipUnless(
        (ROOT / "data/hourly/cordoba-aero/2024/cordoba-aero-2024.sfc").is_file(),
        "Meteorología horaria de Córdoba no disponible",
    )
    def test_complete_hourly_downwash_run_flow(self) -> None:
        project = self.client.post("/projects", json={"name": "Horario PRIME 2024"}).json()
        definition = json.loads(
            (ROOT / "examples/hourly_cordoba_2024_downwash.json").read_text(
                encoding="utf-8"
            )
        )
        scenario = self.client.post(
            f"/projects/{project['id']}/scenarios",
            json={"name": "Córdoba horario con downwash", "definition": definition},
        )
        self.assertEqual(scenario.status_code, 201, scenario.text)
        run = self.client.post(f"/scenarios/{scenario.json()['id']}/runs")
        self.assertEqual(run.status_code, 201, run.text)
        completed = self.client.get(f"/runs/{run.json()['id']}")
        self.assertEqual(completed.json()["status"], "completed", completed.text)
        result = completed.json()["result"]
        self.assertTrue(result["downwash_enabled"])
        self.assertEqual(len(result["downwash_comparison"]), 5)
        annual = result["downwash_comparison"][4]
        self.assertEqual(annual["averaging_period"], "annual")
        self.assertAlmostEqual(annual["with_downwash_ug_m3"], 0.153636, places=6)
        self.assertAlmostEqual(annual["without_downwash_ug_m3"], 0.145113, places=6)
        self.assertAlmostEqual(annual["change_percent"], 5.87335, places=5)
        result_response = self.client.get(f"/runs/{run.json()['id']}/result")
        self.assertEqual(result_response.status_code, 200, result_response.text)
        self.assertTrue(result_response.json()["downwash_enabled"])

    @unittest.skipUnless(
        (ROOT / "data/hourly/cordoba-aero/2024/cordoba-aero-2024.sfc").is_file(),
        "Meteorología horaria de Córdoba no disponible",
    )
    def test_complete_multisource_hourly_run_flow(self) -> None:
        project = self.client.post("/projects", json={"name": "Multifuente 2024"}).json()
        definition = json.loads(
            (ROOT / "examples/multisource_cordoba_2024.json").read_text(encoding="utf-8")
        )
        scenario = self.client.post(
            f"/projects/{project['id']}/scenarios",
            json={"name": "Córdoba multifuente", "definition": definition},
        )
        self.assertEqual(scenario.status_code, 201, scenario.text)
        self.assertEqual(scenario.json()["definition"]["run_mode"], "multi_source_hourly")
        self.assertEqual(len(scenario.json()["definition"]["sources"]), 2)
        terrain = self.client.post(f"/scenarios/{scenario.json()['id']}/terrain/prepare")
        self.assertEqual(terrain.status_code, 409)
        run = self.client.post(f"/scenarios/{scenario.json()['id']}/runs")
        self.assertEqual(run.status_code, 201, run.text)
        completed = self.client.get(f"/runs/{run.json()['id']}")
        self.assertEqual(completed.json()["status"], "completed", completed.text)
        result = completed.json()["result"]
        self.assertEqual(result["run_mode"], "multi_source_hourly")
        self.assertEqual(result["source_count"], 2)
        self.assertEqual(result["receptor_count"], 1800)
        self.assertAlmostEqual(result["maximum_1h"]["concentration_ug_m3"], 8.0736, places=4)
        self.assertEqual(len(result["source_positions"]), 2)
        result_response = self.client.get(f"/runs/{run.json()['id']}/result")
        self.assertEqual(result_response.status_code, 200, result_response.text)
        self.assertEqual(result_response.json()["run_mode"], "multi_source_hourly")

    @unittest.skipUnless(
        CORDOBA_DEM.is_file() and (ROOT / "bin/aermap").is_file(),
        "DEM Córdoba y AERMAP no disponibles",
    )
    def test_prepare_multisource_complex_terrain_through_api(self) -> None:
        project = self.client.post("/projects", json={"name": "Multifuente terreno"}).json()
        definition = json.loads(
            (ROOT / "examples/multisource_cordoba_2024_complex.json").read_text(
                encoding="utf-8"
            )
        )
        scenario = self.client.post(
            f"/projects/{project['id']}/scenarios",
            json={"name": "Córdoba multifuente complejo", "definition": definition},
        )
        self.assertEqual(scenario.status_code, 201, scenario.text)
        with patch("aermod_api.service.download_copernicus", return_value=CORDOBA_DEM):
            prepared = self.client.post(
                f"/scenarios/{scenario.json()['id']}/terrain/prepare"
            )
        self.assertEqual(prepared.status_code, 200, prepared.text)
        payload = prepared.json()
        self.assertEqual(payload["receptor_count"], 1800)
        self.assertEqual(set(payload["source_elevations_m"]), {"STACK1", "STACK2"})
        self.assertAlmostEqual(payload["source_elevations_m"]["STACK1"], 450.54, places=2)

    def test_flat_scenario_rejects_terrain_preparation(self) -> None:
        project = self.client.post("/projects", json={"name": "Terrain"}).json()
        scenario = self.client.post(
            f"/projects/{project['id']}/scenarios",
            json={"name": "Flat", "definition": self.definition},
        ).json()
        response = self.client.post(f"/scenarios/{scenario['id']}/terrain/prepare")
        self.assertEqual(response.status_code, 409)
        self.assertIn("terreno complejo", response.json()["detail"])

    def test_credentials_are_stored_without_being_returned(self) -> None:
        initial = self.client.get("/credentials")
        self.assertEqual(initial.status_code, 200)
        self.assertFalse(initial.json()["earthdata_configured"])
        response = self.client.post("/credentials", json={
            "earthdata_username": "usuario_prueba",
            "earthdata_password": "secreto-prueba",
            "cdsapi_key": "token-prueba",
        })
        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["earthdata_configured"])
        self.assertTrue(response.json()["cds_configured"])
        self.assertNotIn("secreto-prueba", response.text)
        self.assertNotIn("token-prueba", response.text)
        health = self.client.get("/health").json()
        self.assertTrue(health["earthdata_configured"])
        self.assertTrue(health["cds_configured"])
