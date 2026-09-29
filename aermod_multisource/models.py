from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from aermod_hourly.models import (
    HourlyConcentrationPoint,
    HourlyMaximum,
    HourlyMeteorologicalCondition,
    HourlyMeteorology,
    HourlyPeriodMaximum,
    HourlyReceptorConfiguration,
)
from aermod_screening.models import PointSource, StrictModel, TerrainConfiguration
from aermod_screening.terrain import utm_zone


class MultiSourceHourlyScenario(StrictModel):
    run_mode: Literal["multi_source_hourly"] = "multi_source_hourly"
    name: str = Field(min_length=1, max_length=68)
    pollutant_id: str = Field(default="OTHER", pattern=r"^[A-Za-z0-9_]{1,8}$")
    dispersion_mode: Literal["rural", "urban"] = "rural"
    urban_population: int | None = Field(default=None, gt=0)
    sources: list[PointSource] = Field(min_length=2, max_length=100)
    meteorology: HourlyMeteorology
    receptors: HourlyReceptorConfiguration
    terrain: TerrainConfiguration = Field(default_factory=TerrainConfiguration)

    @model_validator(mode="after")
    def scenario_is_consistent(self) -> "MultiSourceHourlyScenario":
        if self.dispersion_mode == "urban" and self.urban_population is None:
            raise ValueError("urban_population es obligatorio para el modo urbano")
        if self.dispersion_mode == "rural" and self.urban_population is not None:
            raise ValueError("urban_population debe omitirse para el modo rural")
        identifiers = [source.source_id for source in self.sources]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("Los identificadores de fuente deben ser únicos")
        if any(source.latitude_deg is None or source.longitude_deg is None for source in self.sources):
            raise ValueError("Todas las fuentes multifuente requieren latitud y longitud")
        zones = {utm_zone(source.longitude_deg) for source in self.sources if source.longitude_deg is not None}
        hemispheres = {source.latitude_deg >= 0 for source in self.sources if source.latitude_deg is not None}
        if len(zones) != 1 or len(hemispheres) != 1:
            raise ValueError("Todas las fuentes deben pertenecer a la misma zona UTM y hemisferio")
        return self


class MultiSourcePosition(StrictModel):
    source_id: str
    latitude_deg: float
    longitude_deg: float
    x_m: float
    y_m: float
    elevation_m: float | None = None


class MultiSourceHourlyResult(StrictModel):
    status: Literal["completed"]
    run_mode: Literal["multi_source_hourly"] = "multi_source_hourly"
    station: Literal["cordoba-aero", "mendoza-aero"]
    year: int
    source_count: int = Field(ge=2)
    receptor_count: int = Field(gt=0)
    domain_center_latitude_deg: float
    domain_center_longitude_deg: float
    utm_zone: int = Field(ge=1, le=60)
    utm_hemisphere: Literal["north", "south"]
    source_positions: list[MultiSourcePosition]
    terrain_mode: Literal["flat", "complex"] = "flat"
    maximum_1h: HourlyMaximum
    period_maxima: list[HourlyPeriodMaximum] = Field(default_factory=list)
    maximum_condition: HourlyMeteorologicalCondition | None = None
    maximum_1h_by_receptor: list[HourlyConcentrationPoint] = Field(default_factory=list)
    meteorology_total_hours: int
    meteorology_usable_hours: int
    meteorology_usable_percent: float
    aermod_finished_successfully: bool
    no_fatal_errors: bool
