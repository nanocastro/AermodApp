import type { SurfaceEstimate } from "./types";

export function representativeRoughnessCandidates(estimate: SurfaceEstimate, limit = 5): number[] {
  if (estimate.roughness_candidates_m.length) return estimate.roughness_candidates_m.slice(0, limit);
  const values = [...new Set(
    estimate.roughness_sectors
      .map((sector) => sector.roughness_m)
      .filter(Number.isFinite),
  )].sort((left, right) => left - right);

  if (values.length <= limit) return values;

  return Array.from({ length: limit }, (_, index) => {
    const position = Math.round(index * (values.length - 1) / (limit - 1));
    return values[position];
  });
}

export function localSurfaceHelp(estimate: SurfaceEstimate) {
  const candidates = representativeRoughnessCandidates(estimate);
  const minimumRoughness = candidates[0];
  const maximumRoughness = candidates[candidates.length - 1];

  return {
    albedo: `Promedio de ${estimate.albedo_valid_count} observaciones válidas de MODIS MCD43A3 entre ${estimate.period_start} y ${estimate.period_end}; expresa la fracción de radiación solar reflejada.`,
    bowen: `Cociente entre los flujos acumulados de calor sensible y latente para ${estimate.bowen_valid_count} horas válidas de ERA5-Land; valores menores indican una superficie relativamente más húmeda.`,
    roughness: minimumRoughness === undefined || maximumRoughness === undefined
      ? "Longitud de rugosidad aerodinámica estimada con ESA WorldCover alrededor de la fuente."
      : `Longitud de rugosidad aerodinámica estimada con ESA WorldCover. Los ${candidates.length} candidatos representativos varían entre ${minimumRoughness.toFixed(4)} y ${maximumRoughness.toFixed(4)} m; se aplicó provisionalmente el máximo sectorial (${estimate.selected_roughness_direction_deg}°).`,
  };
}
