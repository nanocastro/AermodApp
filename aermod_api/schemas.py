from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from aermod_screening.models import ScreeningResult, ScreeningScenario
from aermod_hourly.models import HourlyResult, HourlyScenario
from aermod_multisource import MultiSourceHourlyResult, MultiSourceHourlyScenario


ScenarioDefinition = ScreeningScenario | HourlyScenario | MultiSourceHourlyScenario
RunResult = ScreeningResult | HourlyResult | MultiSourceHourlyResult


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProjectCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    responsible: str = Field(default="", max_length=120)


class ProjectRead(ProjectCreate):
    id: str
    created_at: datetime


class ScenarioCreate(ApiModel):
    name: str = Field(min_length=1, max_length=120)
    definition: ScenarioDefinition


class ScenarioRead(ScenarioCreate):
    id: str
    project_id: str
    created_at: datetime


class RunRead(ApiModel):
    id: str
    scenario_id: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    result: RunResult | None
    progress_current: int = 0
    progress_total: int = 0
    progress_label: str = ""


class ArtifactRead(ApiModel):
    id: str
    run_id: str
    name: str
    kind: str
    size_bytes: int
    sha256: str


class HealthRead(ApiModel):
    status: Literal["ok"]
    database: Literal["ok"]
    aermod_available: bool
    aermet_available: bool
    makemet_available: bool
    aermap_available: bool
    bpipprm_available: bool
    earthdata_configured: bool
    cds_configured: bool


class CredentialStatusRead(ApiModel):
    earthdata_configured: bool
    cds_configured: bool
    storage: Literal["credential_manager", "local_file"]


class CredentialsUpdate(ApiModel):
    earthdata_username: str = Field(default="", max_length=120)
    earthdata_password: str = Field(default="", max_length=500)
    cdsapi_key: str = Field(default="", max_length=1000)

    @model_validator(mode="after")
    def earthdata_fields_are_a_pair(self) -> "CredentialsUpdate":
        if bool(self.earthdata_username) != bool(self.earthdata_password):
            raise ValueError("Usuario y contraseña Earthdata deben ingresarse juntos")
        if not self.earthdata_username and not self.cdsapi_key:
            raise ValueError("Ingresá al menos una credencial para actualizar")
        return self


class TerrainPreparationRead(ApiModel):
    scenario_id: str
    status: Literal["prepared"]
    provider: Literal["copernicus", "ign"]
    latitude_deg: float
    longitude_deg: float
    utm_zone: int
    utm_hemisphere: Literal["north", "south"]
    source_sha256: str
    prepared_sha256: str
    source_elevation_m: float | None
    source_elevations_m: dict[str, float] | None = None
    receptor_count: int
    warnings: list[str]


class SurfaceEstimateRequest(ApiModel):
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)


class RoughnessSectorRead(ApiModel):
    direction_deg: int
    roughness_m: float
    pixel_count: int


class SurfaceEstimateRead(ApiModel):
    latitude_deg: float
    longitude_deg: float
    period_start: str
    period_end: str
    albedo: float
    albedo_valid_count: int
    albedo_expected_count: int
    albedo_missing_count: int
    albedo_coverage_percent: float
    bowen_ratio: float
    bowen_valid_count: int
    bowen_expected_count: int
    bowen_missing_count: int
    bowen_coverage_percent: float
    minimum_coverage_percent: float
    meets_minimum_coverage: bool
    surface_roughness_m: float
    selected_roughness_direction_deg: int
    roughness_season: str
    roughness_sectors: list[RoughnessSectorRead]
    roughness_candidates_m: list[float]
    providers: dict[str, str]
    warnings: list[str]


class StationEstimateRequest(ApiModel):
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)


class StationStatisticsRead(ApiModel):
    observation_count: int
    expected_hour_count: int
    coverage_percent: float
    temperature_mean_c: float
    temperature_min_c: float
    temperature_max_c: float
    wind_mean_m_s: float
    wind_min_observed_m_s: float
    wind_p01_m_s: float
    wind_p05_m_s: float
    wind_p95_m_s: float
    wind_p99_m_s: float
    makemet_minimum_wind_m_s: float


class StationRead(StationStatisticsRead):
    code: str
    name: str
    latitude_deg: float
    longitude_deg: float
    elevation_m: float
    distance_to_source_km: float


class StationEstimateRead(ApiModel):
    region: Literal["Mendoza", "Córdoba"]
    period_start: str
    period_end: str
    source: str
    stations: list[StationRead]
    combined: StationStatisticsRead
    warnings: list[str]


class EnvironmentJobCreate(ApiModel):
    kind: Literal["surface", "stations"]
    latitude_deg: float = Field(ge=-90, le=90)
    longitude_deg: float = Field(ge=-180, le=180)


class EnvironmentJobRead(ApiModel):
    id: str
    kind: Literal["surface", "stations"]
    latitude_deg: float
    longitude_deg: float
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    error: str | None
    result: dict | None
    progress_current: int
    progress_total: int
    progress_label: str
