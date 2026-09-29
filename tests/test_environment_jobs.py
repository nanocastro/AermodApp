from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from aermod_api.database import Database
from aermod_api.environment_jobs import EnvironmentJobService, environment_job_from_row


class FakeEstimator:
    def __init__(self, result: dict | None = None, error: Exception | None = None) -> None:
        self.result = result or {"value": 1}
        self.error = error

    def estimate(self, latitude: float, longitude: float, progress):
        progress(1, 2, "Descargando")
        if self.error:
            raise self.error
        progress(2, 2, "Calculando")
        return {**self.result, "latitude": latitude, "longitude": longitude}


class EnvironmentJobTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.database = Database(Path(self.temporary.name) / "jobs.sqlite3")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_job_persists_progress_and_result(self) -> None:
        estimator = FakeEstimator({"provider": "cache"})
        service = EnvironmentJobService(self.database, estimator, estimator)
        created = service.create("surface", -33.064167, -68.973611)

        service.execute(created["id"])

        job = environment_job_from_row(self.database.get_environment_job(created["id"]))
        self.assertEqual(job["status"], "completed")
        self.assertEqual(job["progress_current"], 2)
        self.assertEqual(job["progress_total"], 2)
        self.assertEqual(job["progress_label"], "Resultados listos")
        self.assertEqual(job["result"]["provider"], "cache")
        self.assertIsNotNone(job["started_at"])
        self.assertIsNotNone(job["finished_at"])

    def test_job_persists_failure(self) -> None:
        failing = FakeEstimator(error=RuntimeError("servicio no disponible"))
        service = EnvironmentJobService(self.database, failing, failing)
        created = service.create("stations", -33.0, -69.0)

        service.execute(created["id"])

        job = environment_job_from_row(self.database.get_environment_job(created["id"]))
        self.assertEqual(job["status"], "failed")
        self.assertIn("servicio no disponible", job["error"])
        self.assertIsNone(job["result"])
        self.assertIsNotNone(job["finished_at"])
