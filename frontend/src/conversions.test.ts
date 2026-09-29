import { describe, expect, it } from "vitest";
import { EPA_DEFAULTS } from "./types";
import { emissionToGramsPerSecond, lengthToMeters, temperatureToKelvin, toHourlyScenarioDefinition, toMultiSourceHourlyScenarioDefinition, toScenarioDefinition, validateStep } from "./conversions";

describe("conversiones canónicas", () => {
  it("convierte unidades de ingeniería", () => {
    expect(emissionToGramsPerSecond(3.6, "kg/h")).toBeCloseTo(1);
    expect(lengthToMeters(100, "cm")).toBeCloseTo(1);
    expect(lengthToMeters(10, "ft")).toBeCloseTo(3.048);
    expect(temperatureToKelvin(20, "°C")).toBeCloseTo(293.15);
  });

  it("reproduce el escenario EPA", () => {
    const scenario = toScenarioDefinition(EPA_DEFAULTS);
    expect(scenario.source.emission_rate_g_s).toBe(1);
    expect(scenario.source.stack_height_m).toBe(61);
    expect(scenario.meteorology.surface_roughness_m).toBe(0.128);
    expect(scenario.meteorology.roughness_candidates_m).toEqual([]);
  });

  it("detecta un intervalo inválido", () => {
    const invalid = { ...EPA_DEFAULTS, searchStart: 2000, searchEnd: 1000 };
    expect(validateStep(2, invalid).length).toBeGreaterThan(0);
  });

  it("genera un escenario horario separado sin parámetros de screening", () => {
    const data = {
      ...EPA_DEFAULTS,
      runMode: "hourly" as const,
      hourlyStation: "mendoza-aero" as const,
      hourlyYear: 2024,
      ambientBoundaryDistance: 100,
      searchStart: 200,
      searchEnd: 5000,
      searchStep: 100,
      directionStep: 10,
    };
    const scenario = toHourlyScenarioDefinition(data);
    expect(scenario.run_mode).toBe("hourly");
    expect(scenario.meteorology).toEqual({ station: "mendoza-aero", year: 2024 });
    expect(scenario.receptors.direction_step_deg).toBe(10);
    expect("minimum_wind_speed_m_s" in scenario.meteorology).toBe(false);
    expect(validateStep(2, data)).toEqual([]);
    expect(validateStep(1, data)).toContain("El mapa de contornos horario requiere latitud y longitud de la fuente.");
    expect(validateStep(1, { ...data, latitude: -32.9, longitude: -68.8 })).toEqual([]);
  });

  it("serializa y valida downwash en el modo horario de fuente única", () => {
    const data = {
      ...EPA_DEFAULTS,
      runMode: "hourly" as const,
      latitude: -31.470714,
      longitude: -64.191139,
      downwashEnabled: true,
      buildingId: "BLDG1",
      buildingHeight: 20,
      buildingLength: 40,
      buildingWidth: 25,
      buildingCenterEast: 25,
      buildingCenterNorth: 0,
      buildingRotation: 0,
    };
    const scenario = toHourlyScenarioDefinition(data);
    expect(scenario.downwash.enabled).toBe(true);
    expect(scenario.downwash.buildings).toHaveLength(1);
    expect(scenario.downwash.buildings[0]).toMatchObject({
      building_id: "BLDG1",
      height_m: 20,
    });
    expect(scenario.downwash.buildings[0].vertices.slice(0, 2)).toEqual([
      { east_m: 5, north_m: -12.5 },
      { east_m: 45, north_m: -12.5 },
    ]);
    expect(validateStep(2, data)).toEqual([]);
    expect(validateStep(2, { ...data, buildingId: "ID MUY LARGO" })).toContain(
      "El ID del edificio debe comenzar con una letra y tener hasta 8 caracteres.",
    );
  });

  it("valida y conserva coordenadas WGS84", () => {
    const located = { ...EPA_DEFAULTS, latitude: -32.8895, longitude: -68.8458 };
    const scenario = toScenarioDefinition(located);
    expect(scenario.source.latitude_deg).toBe(-32.8895);
    expect(scenario.source.longitude_deg).toBe(-68.8458);
    expect(validateStep(1, located)).toEqual([]);
    expect(validateStep(1, { ...located, longitude: Number.NaN })).toContain(
      "Ingresá latitud y longitud juntas, o dejá ambas vacías.",
    );
  });

  it("genera y valida un escenario horario multifuente", () => {
    const data = { ...EPA_DEFAULTS, runMode: "multi_source_hourly" as const };
    const scenario = toMultiSourceHourlyScenarioDefinition(data);
    expect(scenario.run_mode).toBe("multi_source_hourly");
    expect(scenario.sources).toHaveLength(2);
    expect(scenario.sources[0]).toMatchObject({ source_id: "STACK1", emission_rate_g_s: 1, latitude_deg: -31.43028 });
    expect(scenario.sources[1]).toMatchObject({ source_id: "STACK2", emission_rate_g_s: 0.5, longitude_deg: -64.2055 });
    expect(scenario.terrain).toEqual({ mode: "flat", provider: null, compare_with_flat: false });
    expect(validateStep(1, data)).toEqual([]);
    expect(validateStep(2, data)).toEqual([]);

    const duplicate = {
      ...data,
      multiSources: data.multiSources.map((source) => ({ ...source, sourceId: "STACK1" })),
    };
    expect(validateStep(1, duplicate)).toContain("Cada fuente debe tener un ID único.");
    const invalid = {
      ...data,
      multiSources: data.multiSources.map((source, index) => index === 1 ? { ...source, latitude: 100 } : source),
    };
    expect(validateStep(1, invalid).some((message) => message.includes("coordenadas decimales válidas"))).toBe(true);
    const complex = toMultiSourceHourlyScenarioDefinition({
      ...data, terrainMode: "complex", terrainProvider: "copernicus",
    });
    expect(complex.terrain).toEqual({
      mode: "complex", provider: "copernicus", compare_with_flat: false,
    });
  });
});
