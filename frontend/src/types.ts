export type Project = {
  id: string;
  name: string;
  description: string;
  responsible: string;
  created_at: string;
};

export type ScreeningScenarioDefinition = {
  name: string;
  pollutant_id: string;
  dispersion_mode: "rural" | "urban";
  urban_population?: number | null;
  source: {
    source_id: string;
    emission_rate_g_s: number;
    stack_height_m: number;
    stack_temperature_k: number;
    exit_velocity_m_s: number;
    stack_diameter_m: number;
    latitude_deg?: number | null;
    longitude_deg?: number | null;
  };
  meteorology: {
    minimum_wind_speed_m_s: number;
    anemometer_height_m: number;
    minimum_temperature_k: number;
    maximum_temperature_k: number;
    albedo: number;
    bowen_ratio: number;
    surface_roughness_m: number;
    roughness_candidates_m: number[];
    wind_direction_deg: number;
    adjust_friction_velocity: boolean;
    observations_source?: string | null;
    observations_period_start?: string | null;
    observations_period_end?: string | null;
    observations_selection?: string | null;
  };
  receptors: {
    ambient_boundary_distance_m: number;
    search_start_m: number;
    search_end_m: number;
    search_step_m: number;
    base_elevation_m: number;
    receptor_height_m: number;
  };
  terrain: { mode: "flat" | "complex"; provider?: "copernicus" | "ign" | null; compare_with_flat?: boolean };
  downwash: { enabled: boolean; buildings: { building_id: string; height_m: number; base_elevation_m: number; vertices: { east_m: number; north_m: number }[] }[] };
};

export type HourlyScenarioDefinition = {
  run_mode: "hourly";
  name: string;
  pollutant_id: string;
  dispersion_mode: "rural" | "urban";
  urban_population?: number | null;
  source: ScreeningScenarioDefinition["source"];
  meteorology: {
    station: "cordoba-aero" | "mendoza-aero";
    year: number;
  };
  receptors: {
    ambient_boundary_distance_m: number;
    search_start_m: number;
    search_end_m: number;
    search_step_m: number;
    direction_step_deg: number;
    receptor_height_m: number;
  };
  terrain: { mode: "flat" | "complex"; provider?: "copernicus" | "ign" | null; compare_with_flat?: boolean };
  downwash: ScreeningScenarioDefinition["downwash"];
};

export type MultiSourceHourlyScenarioDefinition = {
  run_mode: "multi_source_hourly";
  name: string;
  pollutant_id: string;
  dispersion_mode: "rural" | "urban";
  urban_population?: number | null;
  sources: ScreeningScenarioDefinition["source"][];
  meteorology: HourlyScenarioDefinition["meteorology"];
  receptors: HourlyScenarioDefinition["receptors"];
  terrain: HourlyScenarioDefinition["terrain"];
};

export type ScenarioDefinition = ScreeningScenarioDefinition | HourlyScenarioDefinition | MultiSourceHourlyScenarioDefinition;

export function isHourlyDefinition(definition: ScenarioDefinition): definition is HourlyScenarioDefinition {
  return "run_mode" in definition && definition.run_mode === "hourly";
}

export function isMultiSourceHourlyDefinition(definition: ScenarioDefinition): definition is MultiSourceHourlyScenarioDefinition {
  return "run_mode" in definition && definition.run_mode === "multi_source_hourly";
}

export type TerrainPreparation = {
  scenario_id: string; status: "prepared"; provider: "copernicus" | "ign";
  latitude_deg: number; longitude_deg: number; utm_zone: number;
  utm_hemisphere: "north" | "south"; source_sha256: string; prepared_sha256: string;
  source_elevation_m: number | null; source_elevations_m?: Record<string, number> | null;
  receptor_count: number; warnings: string[];
};

export type SurfaceEstimate = {
  latitude_deg: number; longitude_deg: number; period_start: string; period_end: string;
  albedo: number; albedo_valid_count: number; albedo_expected_count: number;
  albedo_missing_count: number; albedo_coverage_percent: number;
  bowen_ratio: number; bowen_valid_count: number; bowen_expected_count: number;
  bowen_missing_count: number; bowen_coverage_percent: number;
  minimum_coverage_percent: number; meets_minimum_coverage: boolean;
  surface_roughness_m: number; selected_roughness_direction_deg: number;
  roughness_season: string;
  roughness_sectors: { direction_deg: number; roughness_m: number; pixel_count: number }[];
  roughness_candidates_m: number[];
  providers: Record<string, string>; warnings: string[];
};

export type StationStatistics = {
  observation_count: number; expected_hour_count: number; coverage_percent: number;
  temperature_mean_c: number; temperature_min_c: number; temperature_max_c: number;
  wind_mean_m_s: number; wind_min_observed_m_s: number; wind_p01_m_s: number;
  wind_p05_m_s: number; wind_p95_m_s: number; wind_p99_m_s: number;
  makemet_minimum_wind_m_s: number;
};

export type StationEstimate = {
  region?: "Mendoza" | "Córdoba"; period_start: string; period_end: string; source: string;
  stations: (StationStatistics & { code: string; name: string; latitude_deg: number; longitude_deg: number; elevation_m: number; distance_to_source_km: number })[];
  combined: StationStatistics;
  warnings: string[];
};

export type EnvironmentJob = {
  id: string; kind: "surface" | "stations"; latitude_deg: number; longitude_deg: number;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string; started_at: string | null; finished_at: string | null;
  error: string | null; result: Record<string, unknown> | null;
  progress_current: number; progress_total: number; progress_label: string;
};

export type CredentialStatus = {
  earthdata_configured: boolean;
  cds_configured: boolean;
  storage: "credential_manager" | "local_file";
};

export type Scenario = {
  id: string;
  project_id: string;
  name: string;
  definition: ScenarioDefinition;
  created_at: string;
};

export type ConcentrationPoint = {
  distance_m: number;
  concentration_1h_ug_m3: number;
};

export type ScreeningResult = {
  status: "completed";
  maximum_1h_ug_m3: number;
  maximum_distance_m: number;
  maximum_direction_deg?: number | null;
  maximum_sectors_deg?: number[];
  roughness_candidates_m?: number[];
  selected_surface_roughness_m?: number | null;
  roughness_sensitivity?: { roughness_m: number; maximum_1h_ug_m3: number; maximum_distance_m: number; maximum_direction_deg?: number | null }[];
  scaled_3h_ug_m3: number;
  scaled_8h_ug_m3: number;
  scaled_24h_ug_m3: number;
  scaled_annual_ug_m3: number;
  aermod_finished_successfully: boolean;
  no_fatal_errors: boolean;
  concentration_by_distance: ConcentrationPoint[];
  sector_results?: { wind_direction_deg: number; maximum_1h_ug_m3: number; maximum_distance_m: number }[];
  maximum_condition?: {
    synthetic_date: string; wind_direction_deg: number; wind_speed_m_s: number;
    temperature_k: number; friction_velocity_m_s: number; convective_velocity_m_s: number | null;
    mixing_height_m: number | null; stability: "estable" | "neutral" | "convectiva";
  } | null;
  without_downwash_maximum_1h_ug_m3?: number | null;
  downwash_difference_1h_ug_m3?: number | null;
  downwash_change_percent?: number | null;
  downwash_ratio?: number | null;
  flat_terrain_maximum_1h_ug_m3?: number | null;
  flat_terrain_maximum_distance_m?: number | null;
  flat_terrain_maximum_direction_deg?: number | null;
  terrain_difference_1h_ug_m3?: number | null;
  terrain_change_percent?: number | null;
  complex_to_flat_ratio?: number | null;
};

export type HourlyResult = {
  status: "completed";
  run_mode: "hourly";
  station: "cordoba-aero" | "mendoza-aero";
  year: number;
  receptor_count: number;
  terrain_mode?: "flat" | "complex";
  source_elevation_m?: number | null;
  downwash_enabled?: boolean;
  downwash_comparison?: {
    averaging_period: "1h" | "3h" | "8h" | "24h" | "annual";
    with_downwash_ug_m3: number;
    without_downwash_ug_m3: number;
    difference_ug_m3: number;
    change_percent: number | null;
    ratio: number | null;
  }[];
  maximum_1h: {
    concentration_ug_m3: number;
    aermod_timestamp: string;
    hour_ending_local: string;
    x_m: number;
    y_m: number;
    distance_m: number;
    bearing_deg: number;
  };
  period_maxima?: {
    averaging_period: "1h" | "3h" | "8h" | "24h" | "annual";
    concentration_ug_m3: number;
    aermod_timestamp: string | null;
    hour_ending_local: string | null;
    x_m: number;
    y_m: number;
    distance_m: number;
    bearing_deg: number;
  }[];
  maximum_condition?: {
    aermod_timestamp: string;
    hour_ending_local: string;
    wind_direction_deg: number;
    wind_speed_m_s: number;
    temperature_k: number;
    friction_velocity_m_s: number;
    convective_velocity_m_s: number | null;
    surface_heat_flux_w_m2: number;
    convective_mixing_height_m: number | null;
    mechanical_mixing_height_m: number | null;
    monin_obukhov_length_m: number | null;
    relative_humidity_percent: number | null;
    station_pressure_mb: number | null;
    boundary_layer_regime: "estable" | "neutral" | "convectiva";
  } | null;
  maximum_1h_by_receptor?: {
    x_m: number;
    y_m: number;
    concentration_1h_ug_m3: number;
    aermod_timestamp: string;
  }[];
  meteorology_total_hours: number;
  meteorology_usable_hours: number;
  meteorology_usable_percent: number;
  aermod_finished_successfully: boolean;
  no_fatal_errors: boolean;
};

export type MultiSourceHourlyResult = Omit<HourlyResult, "run_mode" | "terrain_mode" | "source_elevation_m"> & {
  run_mode: "multi_source_hourly";
  source_count: number;
  domain_center_latitude_deg: number;
  domain_center_longitude_deg: number;
  utm_zone: number;
  utm_hemisphere: "north" | "south";
  source_positions: {
    source_id: string;
    latitude_deg: number;
    longitude_deg: number;
    x_m: number;
    y_m: number;
    elevation_m?: number | null;
  }[];
  terrain_mode: "flat" | "complex";
};

export function isHourlyResult(result: ScreeningResult | HourlyResult | MultiSourceHourlyResult): result is HourlyResult {
  return "run_mode" in result && result.run_mode === "hourly";
}

export function isMultiSourceHourlyResult(result: ScreeningResult | HourlyResult | MultiSourceHourlyResult): result is MultiSourceHourlyResult {
  return "run_mode" in result && result.run_mode === "multi_source_hourly";
}

export type Run = {
  id: string;
  scenario_id: string;
  status: "pending" | "running" | "completed" | "failed";
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error: string | null;
  result: ScreeningResult | HourlyResult | MultiSourceHourlyResult | null;
  progress_current: number;
  progress_total: number;
  progress_label: string;
};

export type Artifact = {
  id: string;
  run_id: string;
  name: string;
  kind: string;
  size_bytes: number;
  sha256: string;
};

export type WizardData = {
  runMode: "screening" | "hourly" | "multi_source_hourly";
  multiSources: {
    sourceId: string;
    emissionRate: number;
    stackHeight: number;
    stackTemperature: number;
    exitVelocity: number;
    stackDiameter: number;
    latitude: number;
    longitude: number;
  }[];
  hourlyStation: "cordoba-aero" | "mendoza-aero";
  hourlyYear: number;
  directionStep: number;
  projectName: string;
  projectDescription: string;
  responsible: string;
  scenarioName: string;
  pollutantId: string;
  sourceId: string;
  emissionRate: number;
  emissionUnit: "g/s" | "kg/h";
  stackHeight: number;
  heightUnit: "m" | "ft";
  stackTemperature: number;
  temperatureUnit: "K" | "°C";
  exitVelocity: number;
  velocityUnit: "m/s" | "km/h";
  stackDiameter: number;
  diameterUnit: "m" | "cm";
  latitude: number;
  longitude: number;
  dispersionMode: "rural" | "urban";
  urbanPopulation: number;
  minimumWindSpeed: number;
  anemometerHeight: number;
  minimumTemperature: number;
  maximumTemperature: number;
  albedo: number;
  bowenRatio: number;
  surfaceRoughness: number;
  roughnessCandidates: number[];
  windDirection: number;
  adjustFrictionVelocity: boolean;
  observationsSource: string | null;
  observationsPeriodStart: string | null;
  observationsPeriodEnd: string | null;
  observationsSelection: string | null;
  ambientBoundaryDistance: number;
  searchStart: number;
  searchEnd: number;
  searchStep: number;
  baseElevation: number;
  receptorHeight: number;
  terrainMode: "flat" | "complex";
  terrainProvider: "copernicus" | "ign";
  compareTerrainWithFlat: boolean;
  downwashEnabled: boolean;
  buildingId: string;
  buildingHeight: number;
  buildingBaseElevation: number;
  buildingCenterEast: number;
  buildingCenterNorth: number;
  buildingLength: number;
  buildingWidth: number;
  buildingRotation: number;
};

export const EPA_DEFAULTS: WizardData = {
  runMode: "screening",
  multiSources: [
    { sourceId: "STACK1", emissionRate: 1, stackHeight: 50, stackTemperature: 400, exitVelocity: 10, stackDiameter: 2, latitude: -31.43028, longitude: -64.20778 },
    { sourceId: "STACK2", emissionRate: 0.5, stackHeight: 35, stackTemperature: 380, exitVelocity: 8, stackDiameter: 1.5, latitude: -31.4295, longitude: -64.2055 },
  ],
  hourlyStation: "cordoba-aero",
  hourlyYear: 2024,
  directionStep: 10,
  projectName: "Validación EPA",
  projectDescription: "Caso de referencia: fuente puntual, terreno plano y sin downwash.",
  responsible: "",
  scenarioName: "POINT, FLAT, NO DOWNWASH",
  pollutantId: "OTHER",
  sourceId: "SOURCE",
  emissionRate: 1,
  emissionUnit: "g/s",
  stackHeight: 61,
  heightUnit: "m",
  stackTemperature: 415,
  temperatureUnit: "K",
  exitVelocity: 11,
  velocityUnit: "m/s",
  stackDiameter: 5,
  diameterUnit: "m",
  latitude: Number.NaN,
  longitude: Number.NaN,
  dispersionMode: "rural",
  urbanPopulation: 100000,
  minimumWindSpeed: 0.5,
  anemometerHeight: 10,
  minimumTemperature: 270,
  maximumTemperature: 310,
  albedo: 0.14,
  bowenRatio: 0.63,
  surfaceRoughness: 0.128,
  roughnessCandidates: [],
  windDirection: 270,
  adjustFrictionVelocity: false,
  observationsSource: null,
  observationsPeriodStart: null,
  observationsPeriodEnd: null,
  observationsSelection: null,
  ambientBoundaryDistance: 50,
  searchStart: 1350,
  searchEnd: 1850,
  searchStep: 5,
  baseElevation: 25,
  receptorHeight: 0,
  terrainMode: "flat",
  terrainProvider: "copernicus",
  compareTerrainWithFlat: false,
  downwashEnabled: false,
  buildingId: "BUILDING",
  buildingHeight: 20,
  buildingBaseElevation: 25,
  buildingCenterEast: 25,
  buildingCenterNorth: 0,
  buildingLength: 40,
  buildingWidth: 25,
  buildingRotation: 0,
};
