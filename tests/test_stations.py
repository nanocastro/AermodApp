import unittest

from aermod_api.stations import (
    haversine_distance_km,
    nearest_station_region,
    parse_smn_hourly,
    station_statistics,
)


class StationTests(unittest.TestCase):
    def test_parses_rows_with_and_without_pressure(self) -> None:
        text = """FECHA     HORA  TEMP   HUM   PNM    DD    FF     NOMBRE
         [HOA]  [ºC]   [%]  [hPa]  [gr] [km/hr]
01062026     0  11.6   72  1019.2  230    7     MENDOZA AERO
01062026     0  10.0   83          250    9     MENDOZA OBSERVATORIO
"""
        rows = parse_smn_hourly(text, {"MENDOZA AERO", "MENDOZA OBSERVATORIO"})
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[1]["wind_speed_km_h"], 9)

    def test_station_statistics_convert_wind_and_apply_floor(self) -> None:
        rows = [
            {"temperature_c": 5, "wind_speed_km_h": 0},
            {"temperature_c": 15, "wind_speed_km_h": 3.6},
        ]
        result = station_statistics(rows, 4)
        self.assertEqual(result["temperature_mean_c"], 10)
        self.assertEqual(result["coverage_percent"], 50)
        self.assertEqual(result["makemet_minimum_wind_m_s"], .5)

    def test_station_distance_is_plausible_for_mendoza(self) -> None:
        distance = haversine_distance_km(-33.064167, -68.973611, -32.83, -68.78)
        self.assertGreater(distance, 25)
        self.assertLess(distance, 40)

    def test_selects_nearest_supported_station_region(self) -> None:
        self.assertEqual(nearest_station_region(-31.42, -64.19)["name"], "Córdoba")
        self.assertEqual(nearest_station_region(-32.89, -68.85)["name"], "Mendoza")

    def test_parses_cordoba_station_names_from_smn_files(self) -> None:
        text = """FECHA     HORA  TEMP   HUM   PNM    DD    FF     NOMBRE
         [HOA]  [ºC]   [%]  [hPa]  [gr] [km/hr]
01062026     0  12.0   70  1015.0  180   10     CORDOBA AERO
01062026     0  11.0   75          200    8     CORDOBA OBSERVATORIO
"""
        rows = parse_smn_hourly(text, {"CORDOBA AERO", "CORDOBA OBSERVATORIO"})
        self.assertEqual([row["station"] for row in rows], ["CORDOBA AERO", "CORDOBA OBSERVATORIO"])


if __name__ == "__main__":
    unittest.main()
