from __future__ import annotations

import json

from .database import Database
from .stations import StationService
from .surface import SurfaceService


class EnvironmentJobService:
    def __init__(self, database: Database, surface: SurfaceService, stations: StationService) -> None:
        self.database = database
        self.surface = surface
        self.stations = stations

    def create(self, kind: str, latitude: float, longitude: float):
        return self.database.create_environment_job(kind, latitude, longitude)

    def execute(self, identifier: str) -> None:
        row = self.database.get_environment_job(identifier)
        if row is None:
            raise KeyError(identifier)
        total = 4 if row["kind"] == "surface" else 3
        self.database.mark_environment_job_running(identifier, total, "Preparando consulta")
        progress = lambda current, count, label: self.database.update_environment_job_progress(identifier, current, count, label)
        try:
            if row["kind"] == "surface":
                result = self.surface.estimate(row["latitude_deg"], row["longitude_deg"], progress=progress)
            else:
                result = self.stations.estimate(row["latitude_deg"], row["longitude_deg"], progress=progress)
            self.database.mark_environment_job_completed(identifier, result)
        except Exception as error:
            self.database.mark_environment_job_failed(identifier, f"{type(error).__name__}: {error}")


def environment_job_from_row(row) -> dict:
    values = dict(row)
    result_json = values.pop("result_json")
    values["result"] = json.loads(result_json) if result_json else None
    return values
