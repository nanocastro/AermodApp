import { describe, expect, it } from "vitest";
import { destinationPoint } from "./geo";

describe("marcador geográfico del máximo", () => {
  it("ubica el impacto a la distancia y rumbo indicados", () => {
    const source: [number, number] = [-33.064167, -68.973611];
    const north = destinationPoint(...source, 500, 0);
    const south = destinationPoint(...source, 500, 180);

    expect(north[0]).toBeGreaterThan(source[0]);
    expect(south[0]).toBeLessThan(source[0]);
    expect(north[1]).toBeCloseTo(source[1], 5);
    expect(south[1]).toBeCloseTo(source[1], 5);
  });
});
