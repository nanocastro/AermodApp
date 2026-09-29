from __future__ import annotations

import unittest

from aermod_screening.terrain import copernicus_tile_name, copernicus_tiles_for_domain, copernicus_url, generate_aermap_input, utm_zone


class TerrainDataTests(unittest.TestCase):
    def test_mendoza_copernicus_tile(self) -> None:
        tile = copernicus_tile_name(-32.888355, -68.838844)
        self.assertEqual(tile, "Copernicus_DSM_COG_10_S33_00_W069_00_DEM")
        self.assertTrue(copernicus_url(-32.888355, -68.838844).endswith(f"/{tile}/{tile}.tif"))

    def test_mendoza_is_utm_zone_19_south(self) -> None:
        self.assertEqual(utm_zone(-68.838844), 19)

    def test_cordoba_copernicus_tile_and_utm_zone(self) -> None:
        self.assertEqual(
            copernicus_tile_name(-31.42, -64.19),
            "Copernicus_DSM_COG_10_S32_00_W065_00_DEM",
        )
        self.assertEqual(utm_zone(-64.19), 20)

    def test_domain_near_tile_edge_uses_adjacent_tiles(self) -> None:
        tiles = {copernicus_tile_name(*point) for point in copernicus_tiles_for_domain(-33.064167, -68.973611, 5000)}
        self.assertEqual(tiles, {
            "Copernicus_DSM_COG_10_S34_00_W070_00_DEM",
            "Copernicus_DSM_COG_10_S34_00_W069_00_DEM",
        })

    def test_generates_southern_hemisphere_aermap_input(self) -> None:
        generated = generate_aermap_input("terrain.tif", latitude_deg=-32.888355, longitude_deg=-68.838844)
        self.assertIn("DATATYPE NED", generated)
        self.assertIn(" -19 0", generated)
        self.assertIn("LOCATION SOURCE POINT 515073", generated)
        self.assertEqual(generated.count("DISCCART"), 32)
