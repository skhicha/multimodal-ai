"""Automated geospatial plausibility check at ingest (Stage 0 Geo-QA).

Flags inland/out-of-bounds hydrophone coordinates before they ever reach the
map UI. NOAA's IOOS repository has documented real cases of ~1-degree
longitude errors (~75 km) landing a hydrophone station inland — this check
exists specifically to catch that class of metadata bug automatically.
"""

from dataclasses import dataclass

# Known sanctuary station registry: (expected_lat, expected_lon, tolerance_deg).
# Minimal seed set; extended via scripts/seed_sanctsound.py in production.
KNOWN_STATIONS: dict[str, tuple[float, float, float]] = {
    "OC02": (47.9, -124.8, 0.5),  # Olympic Coast
}


@dataclass
class GeoQaResult:
    flag: str | None  # None | "OUT_OF_RANGE" | "STATION_MISMATCH"
    detail: str | None = None


def check_coordinates(
    *, latitude: float, longitude: float, station_code: str | None
) -> GeoQaResult:
    if not (-90.0 <= latitude <= 90.0) or not (-180.0 <= longitude <= 180.0):
        return GeoQaResult(
            flag="OUT_OF_RANGE", detail=f"({latitude}, {longitude}) outside valid range"
        )

    if station_code and station_code in KNOWN_STATIONS:
        expected_lat, expected_lon, tolerance = KNOWN_STATIONS[station_code]
        if abs(latitude - expected_lat) > tolerance or abs(longitude - expected_lon) > tolerance:
            return GeoQaResult(
                flag="STATION_MISMATCH",
                detail=(
                    f"({latitude}, {longitude}) deviates >{tolerance}° from registered "
                    f"station {station_code} at ({expected_lat}, {expected_lon})"
                ),
            )

    return GeoQaResult(flag=None)
