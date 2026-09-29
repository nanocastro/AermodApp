import tempfile
import unittest
from pathlib import Path

from aermod_hourly.aermet import (
    generate_aermet_input,
    summarize_report_file,
    summarize_surface_file,
)
from aermod_hourly.noaa import noaa_urls
from aermod_hourly.stations import HOURLY_STATIONS


class HourlyMeteorologyTests(unittest.TestCase):
    def test_noaa_urls_use_selected_year_and_station(self) -> None:
        station = HOURLY_STATIONS["cordoba-aero"]
        urls = noaa_urls(station, 2024)
        self.assertTrue(urls["surface_isd_gzip"].endswith("/2024/873440-99999-2024.gz"))
        self.assertTrue(urls["upper_igra_zip"].endswith("/ARM00087344-data.txt.zip"))

    def test_generates_aermet_2024_with_seasonal_surface_characteristics(self) -> None:
        generated = generate_aermet_input(HOURLY_STATIONS["cordoba-aero"], 2024)
        self.assertIn("DATA input/cordoba-aero-2024.isd ISHD", generated)
        self.assertIn("DATA input/cordoba-aero-igra.txt IGRA", generated)
        self.assertIn("XDATES 2024/1/1 TO 2024/12/31", generated)
        self.assertIn("FREQ_SECT SEASONAL 12", generated)
        self.assertIn("SECTOR 12 330 360", generated)
        self.assertIn("SITE_CHAR 1 1 0.126806 0.337240 0.050092", generated)
        self.assertIn("SITE_CHAR 3 1 0.126806 0.337240 0.017852", generated)
        self.assertEqual(generated.count("SITE_CHAR "), 48)

    def test_surface_configuration_is_centered_on_each_airport(self) -> None:
        cordoba = generate_aermet_input(HOURLY_STATIONS["cordoba-aero"], 2024)
        mendoza = generate_aermet_input(HOURLY_STATIONS["mendoza-aero"], 2024)
        self.assertIn("LOCATION 87344 31.3240S 64.2080W 3 488.9", cordoba)
        self.assertIn("LOCATION 87418 32.8320S 68.7930W 3 704.1", mendoza)
        self.assertIn("SITE_CHAR 1 1 0.177927 0.775123 0.130378", mendoza)

    def test_summarizes_usable_and_calm_hours(self) -> None:
        header = "header\n"
        usable_calm = "24 1 1 1 1 1.0 1 1 1 1 1 1 1 1 1 0.0 0.0 A B\n"
        missing = "24 1 1 2 1 -999.0 1 1 1 1 1 1 1 1 1 999.0 999.0 C D\n"
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "test.sfc"
            path.write_text(header + usable_calm + missing, encoding="ascii")
            result = summarize_surface_file(path)
        self.assertEqual(result["total_hours"], 2)
        self.assertEqual(result["usable_hours"], 1)
        self.assertEqual(result["calm_hours"], 1)
        self.assertEqual(result["usable_percent"], 50)

    def test_reads_quality_counts_from_aermet_report(self) -> None:
        report = """
 NUMBER OF DAYS WITH NO SOUNDINGS:    6
 NUMBER OF TOTAL CALMS:    989
 NUMBER OF VARIABLE WINDS:    326
 ERROR MESSAGES        0 MESSAGES
 WARNING MESSAGES      308 MESSAGES
"""
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "report.txt"
            path.write_text(report, encoding="ascii")
            result = summarize_report_file(path)
        self.assertEqual(result["days_without_soundings"], 6)
        self.assertEqual(result["calm_hours"], 989)
        self.assertEqual(result["variable_wind_hours"], 326)
        self.assertEqual(result["error_messages"], 0)


if __name__ == "__main__":
    unittest.main()
