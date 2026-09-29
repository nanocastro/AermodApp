from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HourlyStation:
    slug: str
    name: str
    surface_station_id: str
    surface_isd_id: str
    surface_latitude_deg: float
    surface_longitude_deg: float
    surface_elevation_m: float
    upper_station_id: str
    upper_igra_id: str
    upper_latitude_deg: float
    upper_longitude_deg: float
    upper_elevation_m: float
    utc_offset_hours: int
    anemometer_height_m: float
    albedo: float
    bowen_ratio: float
    roughness_by_season: dict[str, tuple[float, ...]]
    surface_parameter_period: tuple[str, str]


# Albedo and Bowen were estimated at each airport with the existing
# MODIS/ERA5-Land method for 2026-06-01 through 2026-07-31. They are retained
# as the agreed approximation for the 2024 pilot. Roughness is the airport
# WorldCover crosswalk aggregated into 12 sectors with the ZORAD-like method.
HOURLY_STATIONS = {
    "cordoba-aero": HourlyStation(
        slug="cordoba-aero",
        name="CORDOBA",
        surface_station_id="87344",
        surface_isd_id="873440-99999",
        surface_latitude_deg=-31.324,
        surface_longitude_deg=-64.208,
        surface_elevation_m=488.9,
        upper_station_id="00087344",
        upper_igra_id="ARM00087344",
        upper_latitude_deg=-31.2966,
        upper_longitude_deg=-64.2119,
        upper_elevation_m=493.0,
        utc_offset_hours=-3,
        anemometer_height_m=10.0,
        albedo=0.12680645161290321,
        bowen_ratio=0.3372397020311461,
        roughness_by_season={
            "winter": (0.0500915119, 0.0605945956, 0.0547038959, 0.0550197383, 0.0535038667, 0.0293905884, 0.0290359704, 0.0437755292, 0.0537097725, 0.0618825763, 0.0476658654, 0.0536833479),
            "spring": (0.0803062591, 0.0766350332, 0.0638691493, 0.0678785964, 0.0782215295, 0.0474726131, 0.0457053065, 0.0608826912, 0.0773972783, 0.0908756833, 0.0740775460, 0.0787432522),
            "summer": (0.0178524200, 0.0345561952, 0.0353121470, 0.0309246592, 0.0212582368, 0.0169489729, 0.0182701552, 0.0247804445, 0.0272425154, 0.0284819168, 0.0190258110, 0.0205892055),
            "autumn": (0.0803062591, 0.0766350332, 0.0638691493, 0.0678785964, 0.0782215295, 0.0474726131, 0.0457053065, 0.0608826912, 0.0773972783, 0.0908756833, 0.0740775460, 0.0787432522),
        },
        surface_parameter_period=("2026-06-01", "2026-07-31"),
    ),
    "mendoza-aero": HourlyStation(
        slug="mendoza-aero",
        name="MENDOZA",
        surface_station_id="87418",
        surface_isd_id="874180-99999",
        surface_latitude_deg=-32.832,
        surface_longitude_deg=-68.793,
        surface_elevation_m=704.1,
        upper_station_id="00087418",
        upper_igra_id="ARM00087418",
        upper_latitude_deg=-32.8438,
        upper_longitude_deg=-68.7963,
        upper_elevation_m=705.0,
        utc_offset_hours=-3,
        anemometer_height_m=10.0,
        albedo=0.17792682926829267,
        bowen_ratio=0.7751227187769562,
        roughness_by_season={
            "winter": (0.1303776744, 0.1585617179, 0.1457664943, 0.1711111983, 0.1999360153, 0.2164415573, 0.1525325464, 0.1577762641, 0.1060710213, 0.0772311244, 0.0939889475, 0.0903097144),
            "spring": (0.1305558152, 0.1586085154, 0.1477523776, 0.1805522202, 0.2102732609, 0.2204801081, 0.1585174666, 0.1599589118, 0.1074961466, 0.0780045592, 0.0953457932, 0.0906258323),
            "summer": (0.1299649811, 0.1584531106, 0.1402126179, 0.1517691205, 0.1828105395, 0.2090876060, 0.1389429839, 0.1523791916, 0.1020047746, 0.0750628113, 0.0908366499, 0.0895799574),
            "autumn": (0.1305558152, 0.1586085154, 0.1477523776, 0.1805522202, 0.2102732609, 0.2204801081, 0.1585174666, 0.1599589118, 0.1074961466, 0.0780045592, 0.0953457932, 0.0906258323),
        },
        surface_parameter_period=("2026-06-01", "2026-07-31"),
    ),
}
