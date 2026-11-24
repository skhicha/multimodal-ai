from sonavault.slices.ingest.geo_qa import check_coordinates


def test_valid_coordinates_no_flag():
    result = check_coordinates(latitude=47.9, longitude=-124.8, station_code="OC02")
    assert result.flag is None


def test_out_of_range_latitude_flagged():
    result = check_coordinates(latitude=120.0, longitude=-124.8, station_code=None)
    assert result.flag == "OUT_OF_RANGE"


def test_out_of_range_longitude_flagged():
    result = check_coordinates(latitude=47.9, longitude=-200.0, station_code=None)
    assert result.flag == "OUT_OF_RANGE"


def test_station_mismatch_detects_one_degree_longitude_error():
    # Simulates the real NOAA IOOS bug: ~1 degree longitude discrepancy
    # landing a hydrophone station inland.
    result = check_coordinates(latitude=47.9, longitude=-123.8, station_code="OC02")
    assert result.flag == "STATION_MISMATCH"
    assert "OC02" in result.detail


def test_unknown_station_code_skips_mismatch_check():
    result = check_coordinates(latitude=10.0, longitude=10.0, station_code="UNKNOWN_STATION")
    assert result.flag is None
