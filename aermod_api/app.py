from __future__ import annotations

import json
import subprocess
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from aermod_screening.models import ScreeningResult, ScreeningScenario
from aermod_hourly import HourlyResult, HourlyScenario
from aermod_multisource import MultiSourceHourlyResult, MultiSourceHourlyScenario

from .config import Settings
from .database import Database
from .schemas import (
    ArtifactRead,
    CredentialStatusRead,
    CredentialsUpdate,
    EnvironmentJobCreate,
    EnvironmentJobRead,
    HealthRead,
    ProjectCreate,
    ProjectRead,
    RunRead,
    ScenarioCreate,
    ScenarioRead,
    SurfaceEstimateRead,
    SurfaceEstimateRequest,
    StationEstimateRead,
    StationEstimateRequest,
    TerrainPreparationRead,
)
from .service import RunService, TerrainService
from .environment_jobs import EnvironmentJobService, environment_job_from_row
from .surface import SurfaceService
from .stations import StationService
from .credentials import CredentialStore


def project_from_row(row) -> ProjectRead:
    return ProjectRead(**dict(row))


def scenario_from_row(row) -> ScenarioRead:
    values = dict(row)
    payload = json.loads(values.pop("definition_json"))
    if payload.get("run_mode") == "hourly":
        values["definition"] = HourlyScenario.model_validate(payload)
    elif payload.get("run_mode") == "multi_source_hourly":
        values["definition"] = MultiSourceHourlyScenario.model_validate(payload)
    else:
        values["definition"] = ScreeningScenario.model_validate(payload)
    return ScenarioRead(**values)


def run_from_row(row) -> RunRead:
    values = dict(row)
    result_json = values.pop("result_json")
    if result_json:
        payload = json.loads(result_json)
        if payload.get("run_mode") == "hourly":
            values["result"] = HourlyResult.model_validate(payload)
        elif payload.get("run_mode") == "multi_source_hourly":
            values["result"] = MultiSourceHourlyResult.model_validate(payload)
        else:
            values["result"] = ScreeningResult.model_validate(payload)
    else:
        values["result"] = None
    return RunRead(**values)


def artifact_from_row(row) -> ArtifactRead:
    values = dict(row)
    values.pop("relative_path")
    return ArtifactRead(**values)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_environment()
    credential_store = CredentialStore(settings.credentials_file, settings)
    settings_holder = [credential_store.apply(settings)]
    settings = settings_holder[0]
    database = Database(settings.database_path)
    run_service = RunService(database, settings)
    terrain_service = TerrainService(settings)
    surface_service = SurfaceService(settings)
    station_service = StationService(settings.surface_directory)
    environment_job_service = EnvironmentJobService(database, surface_service, station_service)
    app = FastAPI(title="AERMOD Screening API", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.frontend_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.settings = settings
    app.state.database = database

    @app.get("/credentials", response_model=CredentialStatusRead)
    def credential_status() -> CredentialStatusRead:
        return CredentialStatusRead(**credential_store.status())

    @app.post("/credentials", response_model=CredentialStatusRead)
    def update_credentials(payload: CredentialsUpdate) -> CredentialStatusRead:
        credential_store.save(**payload.model_dump())
        refreshed = credential_store.apply(settings_holder[0])
        settings_holder[0] = refreshed
        surface_service.settings = refreshed
        app.state.settings = refreshed
        return CredentialStatusRead(**credential_store.status())

    @app.get("/health", response_model=HealthRead)
    def health() -> HealthRead:
        database.ping()
        return HealthRead(
            status="ok",
            database="ok",
            aermod_available=settings.aermod_executable.is_file(),
            aermet_available=settings.aermet_executable.is_file(),
            makemet_available=settings.makemet_executable.is_file(),
            aermap_available=settings.aermap_executable.is_file(),
            bpipprm_available=settings.bpipprm_executable.is_file(),
            earthdata_configured=bool(
                settings_holder[0].earthdata_username and settings_holder[0].earthdata_password
            ),
            cds_configured=bool(settings_holder[0].cdsapi_url and settings_holder[0].cdsapi_key),
        )

    @app.post("/projects", response_model=ProjectRead, status_code=status.HTTP_201_CREATED)
    def create_project(payload: ProjectCreate) -> ProjectRead:
        return project_from_row(database.create_project(payload))

    @app.get("/projects", response_model=list[ProjectRead])
    def list_projects() -> list[ProjectRead]:
        return [project_from_row(row) for row in database.list_projects()]

    @app.get("/projects/{project_id}", response_model=ProjectRead)
    def get_project(project_id: str) -> ProjectRead:
        row = database.get_project(project_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")
        return project_from_row(row)

    @app.post(
        "/projects/{project_id}/scenarios",
        response_model=ScenarioRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_scenario(project_id: str, payload: ScenarioCreate) -> ScenarioRead:
        if database.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")
        return scenario_from_row(database.create_scenario(project_id, payload))

    @app.get("/projects/{project_id}/scenarios", response_model=list[ScenarioRead])
    def list_scenarios(project_id: str) -> list[ScenarioRead]:
        if database.get_project(project_id) is None:
            raise HTTPException(status_code=404, detail="Proyecto no encontrado")
        return [scenario_from_row(row) for row in database.list_scenarios(project_id)]

    @app.get("/scenarios/{scenario_id}", response_model=ScenarioRead)
    def get_scenario(scenario_id: str) -> ScenarioRead:
        row = database.get_scenario(scenario_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Escenario no encontrado")
        return scenario_from_row(row)

    @app.post("/scenarios/{scenario_id}/terrain/prepare", response_model=TerrainPreparationRead)
    def prepare_terrain(scenario_id: str) -> TerrainPreparationRead:
        row = database.get_scenario(scenario_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Escenario no encontrado")
        definition = json.loads(row["definition_json"])
        if definition.get("run_mode") == "hourly":
            scenario = HourlyScenario.model_validate(definition)
        elif definition.get("run_mode") == "multi_source_hourly":
            scenario = MultiSourceHourlyScenario.model_validate(definition)
        else:
            scenario = ScreeningScenario.model_validate(definition)
        try:
            return TerrainPreparationRead(**terrain_service.prepare(scenario_id, scenario))
        except (ValueError, FileNotFoundError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        except (RuntimeError, subprocess.SubprocessError) as error:
            raise HTTPException(status_code=500, detail=str(error)) from None

    @app.post("/surface/estimate", response_model=SurfaceEstimateRead)
    def estimate_surface(payload: SurfaceEstimateRequest) -> SurfaceEstimateRead:
        try:
            return SurfaceEstimateRead(**surface_service.estimate(
                payload.latitude_deg, payload.longitude_deg))
        except (ValueError, FileNotFoundError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"No se pudieron obtener los datos locales: {error}") from None

    @app.post("/meteorology/stations/estimate", response_model=StationEstimateRead)
    def estimate_stations(payload: StationEstimateRequest) -> StationEstimateRead:
        try:
            return StationEstimateRead(**station_service.estimate(payload.latitude_deg, payload.longitude_deg))
        except (ValueError, FileNotFoundError) as error:
            raise HTTPException(status_code=409, detail=str(error)) from None
        except Exception as error:
            raise HTTPException(status_code=502, detail=f"No se pudieron obtener los datos horarios SMN: {error}") from None

    @app.post("/environment/jobs", response_model=EnvironmentJobRead, status_code=status.HTTP_201_CREATED)
    def create_environment_job(payload: EnvironmentJobCreate, background_tasks: BackgroundTasks) -> EnvironmentJobRead:
        row = environment_job_service.create(payload.kind, payload.latitude_deg, payload.longitude_deg)
        background_tasks.add_task(environment_job_service.execute, row["id"])
        return EnvironmentJobRead(**environment_job_from_row(row))

    @app.get("/environment/jobs/{job_id}", response_model=EnvironmentJobRead)
    def get_environment_job(job_id: str) -> EnvironmentJobRead:
        row = database.get_environment_job(job_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Trabajo ambiental no encontrado")
        return EnvironmentJobRead(**environment_job_from_row(row))

    @app.post("/environment/jobs/{job_id}/retry", response_model=EnvironmentJobRead, status_code=status.HTTP_201_CREATED)
    def retry_environment_job(job_id: str, background_tasks: BackgroundTasks) -> EnvironmentJobRead:
        previous = database.get_environment_job(job_id)
        if previous is None:
            raise HTTPException(status_code=404, detail="Trabajo ambiental no encontrado")
        row = environment_job_service.create(previous["kind"], previous["latitude_deg"], previous["longitude_deg"])
        background_tasks.add_task(environment_job_service.execute, row["id"])
        return EnvironmentJobRead(**environment_job_from_row(row))

    @app.post(
        "/scenarios/{scenario_id}/runs",
        response_model=RunRead,
        status_code=status.HTTP_201_CREATED,
    )
    def create_run(scenario_id: str, background_tasks: BackgroundTasks) -> RunRead:
        if database.get_scenario(scenario_id) is None:
            raise HTTPException(status_code=404, detail="Escenario no encontrado")
        row = run_service.create(scenario_id)
        background_tasks.add_task(run_service.execute, row["id"])
        return run_from_row(row)

    @app.get("/scenarios/{scenario_id}/runs", response_model=list[RunRead])
    def list_runs(scenario_id: str) -> list[RunRead]:
        if database.get_scenario(scenario_id) is None:
            raise HTTPException(status_code=404, detail="Escenario no encontrado")
        return [run_from_row(row) for row in database.list_runs(scenario_id)]

    @app.get("/runs/{run_id}", response_model=RunRead)
    def get_run(run_id: str) -> RunRead:
        row = database.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Corrida no encontrada")
        return run_from_row(row)

    @app.post("/runs/{run_id}/repeat", response_model=RunRead, status_code=status.HTTP_201_CREATED)
    def repeat_run(run_id: str, background_tasks: BackgroundTasks) -> RunRead:
        row = database.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Corrida no encontrada")
        repeated = run_service.create(row["scenario_id"])
        background_tasks.add_task(run_service.execute, repeated["id"])
        return run_from_row(repeated)

    @app.get(
        "/runs/{run_id}/result",
        response_model=ScreeningResult | HourlyResult | MultiSourceHourlyResult,
    )
    def get_result(
        run_id: str,
    ) -> ScreeningResult | HourlyResult | MultiSourceHourlyResult:
        row = database.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="Corrida no encontrada")
        if row["status"] != "completed" or row["result_json"] is None:
            raise HTTPException(status_code=409, detail="La corrida no tiene un resultado disponible")
        payload = json.loads(row["result_json"])
        if payload.get("run_mode") == "hourly":
            return HourlyResult.model_validate(payload)
        if payload.get("run_mode") == "multi_source_hourly":
            return MultiSourceHourlyResult.model_validate(payload)
        return ScreeningResult.model_validate(payload)

    @app.get("/runs/{run_id}/artifacts", response_model=list[ArtifactRead])
    def list_artifacts(run_id: str) -> list[ArtifactRead]:
        if database.get_run(run_id) is None:
            raise HTTPException(status_code=404, detail="Corrida no encontrada")
        return [artifact_from_row(row) for row in database.list_artifacts(run_id)]

    @app.get("/runs/{run_id}/artifacts/{artifact_id}", response_class=FileResponse)
    def download_artifact(run_id: str, artifact_id: str) -> FileResponse:
        row = database.get_artifact(artifact_id)
        if row is None or row["run_id"] != run_id:
            raise HTTPException(status_code=404, detail="Artefacto no encontrado")
        try:
            path = run_service.artifact_path(row)
        except FileNotFoundError:
            raise HTTPException(status_code=410, detail="El archivo ya no está disponible") from None
        return FileResponse(path, filename=row["name"])

    if settings.frontend_directory and settings.frontend_directory.is_dir():
        app.mount("/", StaticFiles(directory=settings.frontend_directory, html=True), name="frontend")

    return app


app = create_app()
