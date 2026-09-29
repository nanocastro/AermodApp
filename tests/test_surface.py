from datetime import date
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx

from aermod_api.config import Settings
from aermod_api.surface import (
    aersurface_like_directional_roughness,
    SurfaceService,
    coverage_quality,
    directional_roughness,
    last_complete_months,
    representative_roughness_candidates,
    roughness_for_class,
    roughness_season_for_month,
    worldcover_tile,
)


class SurfaceTests(unittest.TestCase):
    def test_last_two_complete_months(self) -> None:
        self.assertEqual(last_complete_months(date(2026, 8, 3)),
                         (date(2026, 6, 1), date(2026, 7, 31)))

    def test_mendoza_worldcover_tile(self) -> None:
        self.assertEqual(worldcover_tile(-33.064167, -68.973611), "S36W069")

    def test_cordoba_worldcover_tile(self) -> None:
        self.assertEqual(worldcover_tile(-31.42, -64.19), "S33W066")

    def test_directional_roughness_has_36_sectors(self) -> None:
        points = []
        for direction in range(0, 360, 10):
            # 500 m from the origin in every sector, class 50 (built-up).
            import math
            points.append((math.sin(math.radians(direction)) * 500 / 111_320,
                           math.cos(math.radians(direction)) * 500 / 111_320, 50))
        sectors = directional_roughness(points, 0, 0)
        self.assertEqual(len(sectors), 36)
        self.assertTrue(all(item["roughness_m"] == .3 for item in sectors))

    def test_aersurface_like_roughness_has_twelve_thirty_degree_sectors(self) -> None:
        import math

        points = []
        for sector_start in range(0, 360, 30):
            for land_class, direction in ((40, sector_start + 5), (10, sector_start + 10)):
                distance = 500
                points.append((
                    math.sin(math.radians(direction)) * distance / 111_320,
                    math.cos(math.radians(direction)) * distance / 111_320,
                    land_class,
                ))
        sectors = aersurface_like_directional_roughness(points, 0, 0)
        self.assertEqual(len(sectors), 12)
        self.assertAlmostEqual(sectors[0]["roughness_m"], math.sqrt(.04 * 1.1), places=6)
        self.assertEqual(sectors[0]["sector_start_deg"], 0)
        self.assertEqual(sectors[0]["sector_end_deg"], 30)
        self.assertEqual(sectors[0]["class_pixel_counts"], {"tree_cover": 1, "cropland": 1})

    def test_aersurface_like_roughness_rejects_ten_degree_sectors(self) -> None:
        with self.assertRaisesRegex(ValueError, "al menos 30"):
            aersurface_like_directional_roughness([], 0, 0, sector_width_deg=10)

    def test_airport_uses_epa_developed_override(self) -> None:
        self.assertEqual(roughness_for_class(50, "winter_no_snow"), .3)
        self.assertEqual(roughness_for_class(50, "winter_no_snow", airport=True), .06)

    def test_argentina_months_use_southern_hemisphere_seasons(self) -> None:
        self.assertEqual(
            roughness_season_for_month(1, southern_hemisphere=True),
            "midsummer_lush",
        )
        self.assertEqual(
            roughness_season_for_month(7, southern_hemisphere=True),
            "winter_no_snow",
        )
        self.assertEqual(
            roughness_season_for_month(10, southern_hemisphere=True),
            "transitional_spring",
        )

    def test_coverage_quality_requires_more_than_fifty_percent(self) -> None:
        accepted = coverage_quality(51, 100)
        rejected = coverage_quality(50, 100)
        self.assertTrue(accepted["meets_minimum"])
        self.assertFalse(rejected["meets_minimum"])
        self.assertEqual(rejected["missing_count"], 50)

    def test_roughness_candidates_preserve_extremes(self) -> None:
        sectors = [{"roughness_m": value} for value in (.03, .08, .12, .2, .35, .5, .7, .857)]
        self.assertEqual(
            representative_roughness_candidates(sectors),
            [.03, .12, .35, .5, .857],
        )

    def test_appeears_timeout_identifies_provider(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            service = SurfaceService(Settings(
                database_path=root / "database.sqlite3",
                runs_directory=root / "runs",
                aermod_executable=root / "aermod",
                makemet_executable=root / "makemet",
                surface_directory=root / "surface",
                earthdata_username="user",
                earthdata_password="password",
            ))
            output = root / "surface"
            output.mkdir()
            with patch("aermod_api.surface.httpx.Client") as client:
                client.return_value.__enter__.return_value.post.side_effect = httpx.ReadTimeout(
                    "timed out"
                )
                with self.assertRaisesRegex(TimeoutError, "NASA AppEEARS"):
                    service._albedo(0, 0, date(2026, 6, 1), date(2026, 7, 31), output)


if __name__ == "__main__":
    unittest.main()
