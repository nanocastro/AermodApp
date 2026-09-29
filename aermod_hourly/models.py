from __future__ import annotations

import math
from typing import Literal

from pydantic import Field, model_validator

from aermod_screening.models import (
    DownwashConfiguration,
    PointSource,
    StrictModel,
    TerrainConfiguration,
)


class HourlyMeteorology(StrictModel):
    station: Literal["cordoba-aero", "mendoza-aero"]
    year: int = Field(default=2024, ge=1900, le=2100)


class HourlyReceptorConfiguration(StrictModel):
    ambient_boundary_distance_m: float = Field(gt=0)
    search_start_m: float = Field(gt=0)
    search_end_m: float = Field(gt=0)
    search_step_m: float = Field(gt=0)
    direction_step_deg: int = Field(default=10, ge=1, le=90)
    receptor_height_m: float = Field(default=0, ge=0)

    @model_validator(mode="after")
    def grid_is_valid(self) -> "HourlyReceptorConfiguration":
        if self.search_start_m > self.search_end_m:
            raise ValueError("search_start_m debe ser menor o igual que search_end_m")
        if 360 % self.direction_step_deg:
            raise ValueError("direction_step_deg debe dividir exactamente 360")
        self.distances()
        return self

    def distances(self) -> list[float]:
        count = int(round((self.search_end_m - self.search_start_m) / self.search_step_m))
        values = [self.search_start_m + index * self.search_step_m for index in range(count + 1)]
        if not values or abs(values[-1] - self.search_end_m) > 1e-6:
            raise ValueError("El intervalo de receptores debe ser divisible por search_step_m")
        return list(dict.fromkeys([self.ambient_boundary_distance_m, *values]))

    def receptors(self) -> list[tuple[float, float]]:
        result = []
        for distance in self.distances():
            for bearing in range(0, 360, self.direction_step_deg):
                radians = math.radians(bearing)
                result.append((distance * math.sin(radians), distance * math.cos(radians)))
        return result


class HourlyScenario(StrictModel):
    run_mode: Literal["hourly"] = "hourly"
    name: str = Field(min_length=1, max_length=68)
    pollutant_id: str = Field(default="OTHER", pattern=r"^[A-Za-z0-9_]{1,8}$")
    dispersion_mode: Literal["rural", "urban"] = "rural"
    urban_population: int | None = Field(default=None, gt=0)
    source: PointSource
    meteorology: HourlyMeteorology
    receptors: HourlyReceptorConfiguration
    terrain: TerrainConfiguration = Field(default_factory=TerrainConfiguration)
    downwash: DownwashConfiguration = Field(default_factory=DownwashConfiguration)

    @model_validator(mode="after")
    def scenario_is_consistent(self) -> "HourlyScenario":
        if self.dispersion_mode == "urban" and self.urban_population is None:
            raise ValueError("urban_population es obligatorio para el modo urbano")
        if self.dispersion_mode == "rural" and self.urban_population is not None:
            raise ValueError("urban_population debe omitirse para el modo rural")
        if self.terrain.mode == "complex" and self.source.latitude_deg is None:
            raise ValueError("El terreno complejo requiere coordenadas de fuente")
        return self


class HourlyMaximum(StrictModel):
    concentration_ug_m3: float = Field(ge=0)
    aermod_timestamp: str
    hour_ending_local: str
    x_m: float
    y_m: float
    distance_m: float = Field(ge=0)
    bearing_deg: float = Field(ge=0, lt=360)


class HourlyPeriodMaximum(StrictModel):
    averaging_period: Literal["1h", "3h", "8h", "24h", "annual"]
    concentration_ug_m3: float = Field(ge=0)
    aermod_timestamp: str | None = None
    hour_ending_local: str | None = None
    x_m: float
    y_m: float
    distance_m: float = Field(ge=0)
    bearing_deg: float = Field(ge=0, lt=360)


class HourlyConcentrationPoint(StrictModel):
    x_m: float
    y_m: float
    concentration_1h_ug_m3: float = Field(ge=0)
    aermod_timestamp: str


class HourlyMeteorologicalCondition(StrictModel):
    aermod_timestamp: str
    hour_ending_local: str
    wind_direction_deg: float = Field(ge=0, le=999)
    wind_speed_m_s: float = Field(ge=0)
    temperature_k: float
    friction_velocity_m_s: float
    convective_velocity_m_s: float | None
    surface_heat_flux_w_m2: float
    convective_mixing_height_m: float | None
    mechanical_mixing_height_m: float | None
    monin_obukhov_length_m: float | None
    relative_humidity_percent: float | None
    station_pressure_mb: float | None
    boundary_layer_regime: Literal["estable", "neutral", "convectiva"]


class HourlyDownwashComparison(StrictModel):
    averaging_period: Literal["1h", "3h", "8h", "24h", "annual"]
    with_downwash_ug_m3: float = Field(ge=0)
    without_downwash_ug_m3: float = Field(ge=0)
    difference_ug_m3: float
    change_percent: float | None = None
    ratio: float | None = None


class HourlyResult(StrictModel):
    status: Literal["completed"]
    run_mode: Literal["hourly"] = "hourly"
    station: Literal["cordoba-aero", "mendoza-aero"]
    year: int
    receptor_count: int = Field(gt=0)
    terrain_mode: Literal["flat", "complex"] = "flat"
    source_elevation_m: float | None = None
    downwash_enabled: bool = False
    downwash_comparison: list[HourlyDownwashComparison] = Field(default_factory=list)
    maximum_1h: HourlyMaximum
    period_maxima: list[HourlyPeriodMaximum] = Field(default_factory=list)
    maximum_condition: HourlyMeteorologicalCondition | None = None
    maximum_1h_by_receptor: list[HourlyConcentrationPoint] = Field(default_factory=list)
    meteorology_total_hours: int
    meteorology_usable_hours: int
    meteorology_usable_percent: float
    aermod_finished_successfully: bool
    no_fatal_errors: bool
