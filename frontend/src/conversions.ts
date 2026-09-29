import type { HourlyScenarioDefinition, MultiSourceHourlyScenarioDefinition, ScreeningScenarioDefinition, WizardData } from "./types";

export function emissionToGramsPerSecond(value: number, unit: WizardData["emissionUnit"]): number {
  return unit === "kg/h" ? value / 3.6 : value;
}

export function lengthToMeters(value: number, unit: "m" | "ft" | "cm"): number {
  if (unit === "ft") return value * 0.3048;
  if (unit === "cm") return value / 100;
  return value;
}

export function temperatureToKelvin(value: number, unit: WizardData["temperatureUnit"]): number {
  return unit === "°C" ? value + 273.15 : value;
}

export function velocityToMetersPerSecond(value: number, unit: WizardData["velocityUnit"]): number {
  return unit === "km/h" ? value / 3.6 : value;
}

export function toScenarioDefinition(data: WizardData): ScreeningScenarioDefinition {
  const angle = data.buildingRotation * Math.PI / 180;
  const corners = [[-data.buildingLength / 2, -data.buildingWidth / 2], [data.buildingLength / 2, -data.buildingWidth / 2], [data.buildingLength / 2, data.buildingWidth / 2], [-data.buildingLength / 2, data.buildingWidth / 2]];
  return {
    name: data.scenarioName,
    pollutant_id: data.pollutantId,
    dispersion_mode: data.dispersionMode,
    urban_population: data.dispersionMode === "urban" ? data.urbanPopulation : null,
    source: {
      source_id: data.sourceId,
      emission_rate_g_s: emissionToGramsPerSecond(data.emissionRate, data.emissionUnit),
      stack_height_m: lengthToMeters(data.stackHeight, data.heightUnit),
      stack_temperature_k: temperatureToKelvin(data.stackTemperature, data.temperatureUnit),
      exit_velocity_m_s: velocityToMetersPerSecond(data.exitVelocity, data.velocityUnit),
      stack_diameter_m: lengthToMeters(data.stackDiameter, data.diameterUnit),
      latitude_deg: Number.isFinite(data.latitude) ? data.latitude : null,
      longitude_deg: Number.isFinite(data.longitude) ? data.longitude : null,
    },
    meteorology: {
      minimum_wind_speed_m_s: data.minimumWindSpeed,
      anemometer_height_m: data.anemometerHeight,
      minimum_temperature_k: data.minimumTemperature,
      maximum_temperature_k: data.maximumTemperature,
      albedo: data.albedo,
      bowen_ratio: data.bowenRatio,
      surface_roughness_m: data.surfaceRoughness,
      roughness_candidates_m: data.roughnessCandidates,
      wind_direction_deg: data.windDirection,
      adjust_friction_velocity: data.adjustFrictionVelocity,
      observations_source: data.observationsSource,
      observations_period_start: data.observationsPeriodStart,
      observations_period_end: data.observationsPeriodEnd,
      observations_selection: data.observationsSelection,
    },
    receptors: {
      ambient_boundary_distance_m: data.ambientBoundaryDistance,
      search_start_m: data.searchStart,
      search_end_m: data.searchEnd,
      search_step_m: data.searchStep,
      base_elevation_m: data.baseElevation,
      receptor_height_m: data.receptorHeight,
    },
    terrain: {
      mode: data.terrainMode,
      provider: data.terrainMode === "complex" ? data.terrainProvider : null,
      compare_with_flat: data.terrainMode === "complex" && data.compareTerrainWithFlat,
    },
    downwash: {
      enabled: data.downwashEnabled,
      buildings: data.downwashEnabled ? [{ building_id: data.buildingId, height_m: data.buildingHeight, base_elevation_m: data.buildingBaseElevation,
        vertices: corners.map(([east, north]) => ({ east_m: data.buildingCenterEast + east * Math.cos(angle) - north * Math.sin(angle), north_m: data.buildingCenterNorth + east * Math.sin(angle) + north * Math.cos(angle) })) }] : [],
    },
  };
}

export function toHourlyScenarioDefinition(data: WizardData): HourlyScenarioDefinition {
  const screening = toScenarioDefinition(data);
  const source = screening.source;
  return {
    run_mode: "hourly",
    name: data.scenarioName,
    pollutant_id: data.pollutantId,
    dispersion_mode: data.dispersionMode,
    urban_population: data.dispersionMode === "urban" ? data.urbanPopulation : null,
    source,
    meteorology: { station: data.hourlyStation, year: data.hourlyYear },
    receptors: {
      ambient_boundary_distance_m: data.ambientBoundaryDistance,
      search_start_m: data.searchStart,
      search_end_m: data.searchEnd,
      search_step_m: data.searchStep,
      direction_step_deg: data.directionStep,
      receptor_height_m: data.receptorHeight,
    },
    terrain: {
      mode: data.terrainMode,
      provider: data.terrainMode === "complex" ? data.terrainProvider : null,
      compare_with_flat: false,
    },
    downwash: screening.downwash,
  };
}

export function toMultiSourceHourlyScenarioDefinition(data: WizardData): MultiSourceHourlyScenarioDefinition {
  return {
    run_mode: "multi_source_hourly",
    name: data.scenarioName,
    pollutant_id: data.pollutantId,
    dispersion_mode: data.dispersionMode,
    urban_population: data.dispersionMode === "urban" ? data.urbanPopulation : null,
    sources: data.multiSources.map((source) => ({
      source_id: source.sourceId,
      emission_rate_g_s: source.emissionRate,
      stack_height_m: source.stackHeight,
      stack_temperature_k: source.stackTemperature,
      exit_velocity_m_s: source.exitVelocity,
      stack_diameter_m: source.stackDiameter,
      latitude_deg: source.latitude,
      longitude_deg: source.longitude,
    })),
    meteorology: { station: data.hourlyStation, year: data.hourlyYear },
    receptors: {
      ambient_boundary_distance_m: data.ambientBoundaryDistance,
      search_start_m: data.searchStart,
      search_end_m: data.searchEnd,
      search_step_m: data.searchStep,
      direction_step_deg: data.directionStep,
      receptor_height_m: data.receptorHeight,
    },
    terrain: {
      mode: data.terrainMode,
      provider: data.terrainMode === "complex" ? data.terrainProvider : null,
      compare_with_flat: false,
    },
  };
}

export function validateStep(step: number, data: WizardData): string[] {
  const errors: string[] = [];
  if (step === 0) {
    if (!data.projectName.trim()) errors.push("Ingresá un nombre de proyecto.");
    if (!data.scenarioName.trim()) errors.push("Ingresá un nombre de escenario.");
  }
  if (step === 1) {
    if (data.runMode === "multi_source_hourly") {
      if (!/^[A-Za-z0-9_]{1,8}$/.test(data.pollutantId)) errors.push("El contaminante admite hasta 8 letras, números o guion bajo.");
      if (data.multiSources.length < 2) errors.push("La modalidad multifuente requiere al menos dos fuentes.");
      const identifiers = data.multiSources.map((source) => source.sourceId);
      if (new Set(identifiers).size !== identifiers.length) errors.push("Cada fuente debe tener un ID único.");
      data.multiSources.forEach((source, index) => {
        if (!/^[A-Za-z][A-Za-z0-9_]{0,7}$/.test(source.sourceId)) errors.push(`Fuente ${index + 1}: el ID debe comenzar con una letra y tener hasta 8 caracteres.`);
        if ([source.emissionRate, source.stackHeight, source.stackTemperature, source.exitVelocity, source.stackDiameter].some((value) => !Number.isFinite(value) || value <= 0)) errors.push(`Fuente ${index + 1}: todos los parámetros físicos deben ser mayores que cero.`);
        if (!Number.isFinite(source.latitude) || source.latitude < -90 || source.latitude > 90 || !Number.isFinite(source.longitude) || source.longitude < -180 || source.longitude > 180) errors.push(`Fuente ${index + 1}: ingresá coordenadas decimales válidas.`);
      });
      return errors;
    }
    if (!/^[A-Za-z][A-Za-z0-9_]{0,7}$/.test(data.sourceId)) {
      errors.push("El ID debe comenzar con una letra y tener hasta 8 caracteres.");
    }
    if (!/^[A-Za-z0-9_]{1,8}$/.test(data.pollutantId)) {
      errors.push("El contaminante admite hasta 8 letras, números o guion bajo.");
    }
    const canonical = toScenarioDefinition(data).source;
    const physicalValues = [
      canonical.emission_rate_g_s,
      canonical.stack_height_m,
      canonical.stack_temperature_k,
      canonical.exit_velocity_m_s,
      canonical.stack_diameter_m,
    ];
    if (physicalValues.some((value) => !Number.isFinite(value) || value <= 0)) {
      errors.push("Todos los parámetros físicos de la fuente deben ser mayores que cero.");
    }
    const hasLatitude = Number.isFinite(data.latitude);
    const hasLongitude = Number.isFinite(data.longitude);
    if (hasLatitude !== hasLongitude) errors.push("Ingresá latitud y longitud juntas, o dejá ambas vacías.");
    if (data.runMode === "hourly" && (!hasLatitude || !hasLongitude)) errors.push("El mapa de contornos horario requiere latitud y longitud de la fuente.");
    if (hasLatitude && (data.latitude < -90 || data.latitude > 90)) errors.push("La latitud debe estar entre −90 y 90°.");
    if (hasLongitude && (data.longitude < -180 || data.longitude > 180)) errors.push("La longitud debe estar entre −180 y 180°.");
  }
  if (step === 2) {
    if (data.runMode !== "screening") {
      if (data.hourlyYear !== 2024) errors.push("El conjunto horario disponible corresponde a 2024.");
      if (360 % data.directionStep !== 0) errors.push("El paso angular debe dividir exactamente 360°.");
      if (data.dispersionMode === "urban" && data.urbanPopulation <= 0) errors.push("Ingresá la población para el modo urbano.");
      if (data.searchStart > data.searchEnd || data.searchStep <= 0) errors.push("Revisá el intervalo y el paso de receptores.");
      const intervals = (data.searchEnd - data.searchStart) / data.searchStep;
      if (Math.abs(intervals - Math.round(intervals)) > 1e-6) errors.push("El intervalo de receptores debe ser divisible por el paso.");
      if (data.runMode === "hourly" && data.downwashEnabled) {
        if (!/^[A-Za-z][A-Za-z0-9_]{0,7}$/.test(data.buildingId)) errors.push("El ID del edificio debe comenzar con una letra y tener hasta 8 caracteres.");
        if ([data.buildingHeight, data.buildingLength, data.buildingWidth].some((value) => !Number.isFinite(value) || value <= 0)) errors.push("Altura, largo y ancho del edificio deben ser mayores que cero.");
      }
      return errors;
    }
    if (data.downwashEnabled) {
      if (!/^[A-Za-z][A-Za-z0-9_]{0,7}$/.test(data.buildingId)) errors.push("El ID del edificio debe comenzar con una letra y tener hasta 8 caracteres.");
      if ([data.buildingHeight, data.buildingLength, data.buildingWidth].some((value) => !Number.isFinite(value) || value <= 0)) errors.push("Altura, largo y ancho del edificio deben ser mayores que cero.");
    }
    if (data.terrainMode === "complex" && (!Number.isFinite(data.latitude) || !Number.isFinite(data.longitude))) {
      errors.push("El terreno complejo requiere latitud y longitud de la fuente.");
    }
    if (data.minimumTemperature >= data.maximumTemperature) {
      errors.push("La temperatura mínima debe ser menor que la máxima.");
    }
    if (data.albedo < 0 || data.albedo > 1) errors.push("El albedo debe estar entre 0 y 1.");
    if (data.bowenRatio <= 0 || data.surfaceRoughness <= 0) {
      errors.push("Bowen y rugosidad deben ser mayores que cero.");
    }
    if (data.dispersionMode === "urban" && data.urbanPopulation <= 0) {
      errors.push("Ingresá la población para el modo urbano.");
    }
    if (data.searchStart > data.searchEnd || data.searchStep <= 0) {
      errors.push("Revisá el intervalo y el paso de receptores.");
    }
    const intervals = (data.searchEnd - data.searchStart) / data.searchStep;
    if (Math.abs(intervals - Math.round(intervals)) > 1e-6) {
      errors.push("El intervalo de receptores debe ser divisible por el paso.");
    }
  }
  return errors;
}

export function warnings(data: WizardData): string[] {
  const notices: string[] = [];
  if (data.runMode === "multi_source_hourly") {
    data.multiSources.forEach((source) => {
      if (source.stackHeight > 300) notices.push(`${source.sourceId}: la altura supera 300 m.`);
      if (source.stackTemperature < 273.15) notices.push(`${source.sourceId}: la temperatura de salida es inferior a 0 °C.`);
      if (source.exitVelocity > 50) notices.push(`${source.sourceId}: la velocidad de salida supera 50 m/s.`);
    });
    if (data.searchStep > 50) notices.push("Un paso grande puede omitir el máximo de concentración.");
    return notices;
  }
  const source = toScenarioDefinition(data).source;
  if (source.stack_height_m > 300) notices.push("La altura supera 300 m; verificá la unidad ingresada.");
  if (source.stack_temperature_k < 273.15) notices.push("La temperatura de salida es inferior a 0 °C.");
  if (source.exit_velocity_m_s > 50) notices.push("La velocidad de salida supera 50 m/s.");
  if (data.searchStep > 50) notices.push("Un paso grande puede omitir el máximo de concentración.");
  return notices;
}
