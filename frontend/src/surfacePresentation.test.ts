import { describe, expect, it } from "vitest";
import { localSurfaceHelp, representativeRoughnessCandidates } from "./surfacePresentation";
import type { SurfaceEstimate } from "./types";

const estimate: SurfaceEstimate = {
  latitude_deg: -33.064167,
  longitude_deg: -68.973611,
  period_start: "2026-06-01",
  period_end: "2026-07-31",
  albedo: 0.1428,
  albedo_valid_count: 33,
  albedo_expected_count: 61,
  albedo_missing_count: 28,
  albedo_coverage_percent: 54.098,
  bowen_ratio: 0.1864,
  bowen_valid_count: 1419,
  bowen_expected_count: 1464,
  bowen_missing_count: 45,
  bowen_coverage_percent: 96.926,
  minimum_coverage_percent: 50,
  meets_minimum_coverage: true,
  surface_roughness_m: 0.857,
  selected_roughness_direction_deg: 180,
  roughness_season: "winter_no_snow",
  roughness_sectors: [0.03, 0.08, 0.12, 0.2, 0.35, 0.5, 0.7, 0.857].map((roughness_m, index) => ({
    direction_deg: index * 10,
    roughness_m,
    pixel_count: 10,
  })),
  roughness_candidates_m: [0.03, 0.12, 0.35, 0.5, 0.857],
  providers: {},
  warnings: [],
};

describe("presentación de parámetros locales", () => {
  it("genera cinco candidatos conservando los extremos", () => {
    expect(representativeRoughnessCandidates(estimate)).toEqual([0.03, 0.12, 0.35, 0.5, 0.857]);
  });

  it("explica los valores locales y el rango de rugosidad", () => {
    const help = localSurfaceHelp(estimate);
    expect(help.albedo).toContain("33 observaciones válidas");
    expect(help.bowen).toContain("1419 horas válidas");
    expect(help.roughness).toContain("5 candidatos representativos varían entre 0.0300 y 0.8570 m");
  });
});
