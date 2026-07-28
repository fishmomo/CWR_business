import numpy as np
import xarray as xr

from cwr_engine.precipitation import classify_precipitation_cwr


def test_classify_precipitation_cwr_counts_days_and_accumulates_cwr():
    precipitation = xr.DataArray(
        np.array([[[0.0, 10.0]], [[5.0, 30.0]], [[60.0, 25.0]]]),
        dims=("time", "latitude", "longitude"),
        coords={"time": ["2025-01-01", "2025-01-02", "2025-01-03"], "latitude": [30.0], "longitude": [100.0, 101.0]},
    )
    cwr = precipitation * 2
    mask = xr.DataArray([[True, False]], dims=("latitude", "longitude"), coords={"latitude": [30.0], "longitude": [100.0, 101.0]})

    result = classify_precipitation_cwr(precipitation, cwr, mask)

    assert result.attrs["sample_days"] == 3
    assert result["light_days"].sel(latitude=30.0, longitude=100.0).item() == 1
    assert result["heavy_days"].sel(latitude=30.0, longitude=100.0).item() == 1
    assert result["light_cwr_mm"].sel(latitude=30.0, longitude=100.0).item() == 10
    assert result["heavy_cwr_mm"].sel(latitude=30.0, longitude=100.0).item() == 120
    assert np.isnan(result["small_days"].sel(latitude=30.0, longitude=101.0).item())
