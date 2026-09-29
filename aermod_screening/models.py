from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PointSource(StrictModel):
    source_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,7}$")
    emission_rate_g_s: float = Field(gt=0)
    stack_height_m: float = Field(gt=0)
    stack_temperature_k: float = Field(gt=0)
    exit_velocity_m_s: float = Field(gt=0)
    stack_diameter_m: float = Field(gt=0)
    latitude_deg: float | None = Field(default=None, ge=-90, le=90)
    longitude_deg: float | None = Field(default=None, ge=-180, le=180)

    @model_validator(mode="after")
    def coordinates_are_a_pair(self) -> "PointSource":
        if (self.latitude_deg is None) != (self.longitude_deg is None):
            raise ValueError("latitude_deg y longitude_deg deben informarse juntas")
        return self


class ScreeningMeteorology(StrictModel):
    minimum_wind_speed_m_s: float = Field(gt=0)
    anemometer_height_m: float = Field(gt=0)
    minimum_temperature_k: float = Field(gt=0)
    maximum_temperature_k: float = Field(gt=0)
    albedo: float = Field(ge=0, le=1)
    bowen_ratio: float = Field(gt=0)
    surface_roughness_m: float = Field(gt=0)
    roughness_candidates_m: list[float] = Field(default_factory=list, max_length=5)
    wind_direction_deg: float = Field(ge=0, le=360, default=270)
    adjust_friction_velocity: bool = False
    observations_source: str | None = None
    observations_period_start: str | None = None
    observations_period_end: str | None = None
    observations_selection: str | None = None

    @model_validator(mode="after")
    def temperatures_are_ordered(self) -> "ScreeningMeteorology":
        if self.minimum_temperature_k >= self.maximum_temperature_k:
            raise ValueError("minimum_temperature_k debe ser menor que maximum_temperature_k")
        if any(value <= 0 for value in self.roughness_candidates_m):
            raise ValueError("roughness_candidates_m debe contener valores mayores que cero")
        if self.roughness_candidates_m != sorted(set(self.roughness_candidates_m)):
            raise ValueError("roughness_candidates_m debe estar ordenado y no contener duplicados")
        if self.roughness_candidates_m and not any(
            abs(value - self.surface_roughness_m) <= 1e-9 for value in self.roughness_candidates_m
        ):
            raise ValueError("surface_roughness_m debe pertenecer a roughness_candidates_m")
        observation_fields = (
            self.observations_source, self.observations_period_start,
            self.observations_period_end, self.observations_selection,
        )
        if any(value is not None for value in observation_fields) and not all(observation_fields):
            raise ValueError("La procedencia meteorológica observada debe informarse completa")
        return self


class ReceptorConfiguration(StrictModel):
    ambient_boundary_distance_m: float = Field(gt=0)
    search_start_m: float = Field(gt=0)
    search_end_m: float = Field(gt=0)
    search_step_m: float = Field(gt=0)
    base_elevation_m: float = 0
    receptor_height_m: float = Field(ge=0, default=0)

    @model_validator(mode="after")
    def search_range_is_valid(self) -> "ReceptorConfiguration":
        if self.search_start_m > self.search_end_m:
            raise ValueError("search_start_m debe ser menor o igual que search_end_m")
        return self

    def distances(self) -> list[float]:
        count = int(round((self.search_end_m - self.search_start_m) / self.search_step_m))
        values = [self.search_start_m + index * self.search_step_m for index in range(count + 1)]
        if not values or abs(values[-1] - self.search_end_m) > 1e-6:
            raise ValueError("El intervalo de receptores debe ser divisible por search_step_m")
        return [self.ambient_boundary_distance_m, *values]


class TerrainConfiguration(StrictModel):
    mode: Literal["flat", "complex"] = "flat"
    provider: Literal["copernicus", "ign"] | None = None
    compare_with_flat: bool = False

    @model_validator(mode="after")
    def provider_matches_mode(self) -> "TerrainConfiguration":
        if self.mode == "complex" and self.provider is None:
            raise ValueError("provider es obligatorio para terreno complejo")
        if self.mode == "flat" and self.provider is not None:
            raise ValueError("provider debe omitirse para terreno plano")
        if self.mode == "flat" and self.compare_with_flat:
            raise ValueError("compare_with_flat solo se admite para terreno complejo")
        return self


class BuildingVertex(StrictModel):
    east_m: float
    north_m: float


class Building(StrictModel):
    building_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,7}$")
    height_m: float = Field(gt=0)
    base_elevation_m: float = 0
    vertices: list[BuildingVertex] = Field(min_length=3, max_length=20)


class DownwashConfiguration(StrictModel):
    enabled: bool = False
    buildings: list[Building] = Field(default_factory=list, max_length=50)

    @model_validator(mode="after")
    def buildings_match_enabled(self) -> "DownwashConfiguration":
        if self.enabled and not self.buildings:
            raise ValueError("downwash requiere al menos un edificio")
        if not self.enabled and self.buildings:
            raise ValueError("los edificios requieren downwash habilitado")
        return self


class ScreeningScenario(StrictModel):
    name: str = Field(min_length=1, max_length=68)
    pollutant_id: str = Field(default="OTHER", pattern=r"^[A-Za-z0-9_]{1,8}$")
    dispersion_mode: Literal["rural", "urban"] = "rural"
    urban_population: int | None = Field(default=None, gt=0)
    source: PointSource
    meteorology: ScreeningMeteorology
    receptors: ReceptorConfiguration
    terrain: TerrainConfiguration = Field(default_factory=TerrainConfiguration)
    downwash: DownwashConfiguration = Field(default_factory=DownwashConfiguration)

    @model_validator(mode="after")
    def urban_mode_has_population(self) -> "ScreeningScenario":
        if self.dispersion_mode == "urban" and self.urban_population is None:
            raise ValueError("urban_population es obligatorio para el modo urbano")
        if self.dispersion_mode == "rural" and self.urban_population is not None:
            raise ValueError("urban_population debe omitirse para el modo rural")
        if self.terrain.mode == "complex" and self.source.latitude_deg is None:
            raise ValueError("terreno complejo requiere coordenadas de la fuente")
        self.receptors.distances()
        return self


class ConcentrationPoint(StrictModel):
    distance_m: float
    concentration_1h_ug_m3: float


class SectorResult(StrictModel):
    wind_direction_deg: float
    maximum_1h_ug_m3: float
    maximum_distance_m: float


class RoughnessSensitivityResult(StrictModel):
    roughness_m: float
    maximum_1h_ug_m3: float
    maximum_distance_m: float
    maximum_direction_deg: float | None = None


class MeteorologicalCondition(StrictModel):
    synthetic_date: str
    wind_direction_deg: float
    wind_speed_m_s: float
    temperature_k: float
    friction_velocity_m_s: float
    convective_velocity_m_s: float | None
    mixing_height_m: float | None
    stability: Literal["estable", "neutral", "convectiva"]


class ScreeningResult(StrictModel):
    status: Literal["completed"]
    maximum_1h_ug_m3: float
    maximum_distance_m: float
    maximum_direction_deg: float | None = None
    maximum_sectors_deg: list[float] = Field(default_factory=list)
    scaled_3h_ug_m3: float
    scaled_8h_ug_m3: float
    scaled_24h_ug_m3: float
    scaled_annual_ug_m3: float
    aermod_finished_successfully: bool
    no_fatal_errors: bool
    concentration_by_distance: list[ConcentrationPoint]
    sector_results: list[SectorResult] = Field(default_factory=list)
    maximum_condition: MeteorologicalCondition | None = None
    without_downwash_maximum_1h_ug_m3: float | None = None
    downwash_difference_1h_ug_m3: float | None = None
    downwash_change_percent: float | None = None
    downwash_ratio: float | None = None
    roughness_candidates_m: list[float] = Field(default_factory=list)
    selected_surface_roughness_m: float | None = None
    roughness_sensitivity: list[RoughnessSensitivityResult] = Field(default_factory=list)
    flat_terrain_maximum_1h_ug_m3: float | None = None
    flat_terrain_maximum_distance_m: float | None = None
    flat_terrain_maximum_direction_deg: float | None = None
    terrain_difference_1h_ug_m3: float | None = None
    terrain_change_percent: float | None = None
    complex_to_flat_ratio: float | None = None
