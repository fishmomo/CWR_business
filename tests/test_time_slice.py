from cwr_engine.models.time_slice import normalize_time_slice


def test_normalize_year_slice():
    item = normalize_time_slice({"scale": "year", "year": 2025})
    assert item.start == "2025-01-01"
    assert item.end == "2025-12-31"
    assert item.label == "2025"


def test_normalize_month_slice():
    item = normalize_time_slice({"scale": "month", "year": 2025, "month": 2})
    assert item.start == "2025-02-01"
    assert item.end == "2025-02-28"
    assert item.label == "2025-02"


def test_normalize_day_slice():
    item = normalize_time_slice({"scale": "day", "day": "2025-02-03"})
    assert item.start == "2025-02-03"
    assert item.end == "2025-02-03"
    assert item.label == "2025-02-03"
