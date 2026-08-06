import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from cwr_engine.business_metrics.cloud_water_multi_year import (
    _extrema,
    _trend,
    build_cloud_water_multi_year_business_metrics,
    derive_cloud_water_multi_year_business_metrics,
    load_cloud_water_multi_year_metrics_spec,
)


def _write_products(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "products"
    (root / "Y").mkdir(parents=True)
    (root / "M").mkdir()
    lat = [31.0, 30.0]
    lon = [100.0, 101.0]
    shape = (2, 2)

    for year in range(2021, 2026):
        year_offset = float(year - 2021)
        annual = _product_dataset(
            lat,
            lon,
            shape,
            sp=10.0 + year_offset,
            mc=7.0 + year_offset,
        )
        annual.to_netcdf(
            root / "Y" / f"ResultGrid_Y_{year}-01-01-00_next.nc",
            engine="scipy",
        )
        for month in range(1, 13):
            monthly = _product_dataset(
                lat,
                lon,
                shape,
                sp=float(month) + year_offset,
                mc=2.0 + year_offset,
            )
            monthly.to_netcdf(
                root / "M" / f"ResultGrid_M_{year}-{month:02d}-01-00_next.nc",
                engine="scipy",
            )

    mask_path = tmp_path / "mask.nc"
    xr.Dataset(
        {"ind_area_bool": (("lat", "lon"), np.ones(shape, dtype=bool))},
        coords={"lat": lat, "lon": lon},
    ).to_netcdf(mask_path, engine="scipy")
    return root, mask_path


def _product_dataset(
    lat: list[float],
    lon: list[float],
    shape: tuple[int, int],
    *,
    sp: float,
    mc: float,
) -> xr.Dataset:
    values = {
        "SP": sp,
        "Mv0": 2.0,
        "MvT": 3.0,
        "aveMv": 4.0,
        "Mh0": 5.0,
        "aveMh": 6.0,
        "MC": mc,
        "ME": 8.0,
        "GMv": 100.0,
        "GMh": 20.0,
        "CWR": 10.0,
        "CEv": 25.0,
        "PEh": 50.0,
        "dxy": 100.0,
    }
    for component in ("qv", "qc"):
        for flow, value in (("In", 1.0), ("Out", 0.5)):
            for side in "WENS":
                values[f"{component}_QData{flow}_{side}Temp"] = value
    return xr.Dataset(
        {
            name: (("latitude", "longitude"), np.full(shape, value))
            for name, value in values.items()
        },
        coords={"latitude": lat, "longitude": lon},
    )


def _write_spec(tmp_path: Path, root: Path, mask_path: Path) -> Path:
    spec_path = tmp_path / "multi-year-metrics.json"
    spec_path.write_text(
        json.dumps(
            {
                "metric_profile": "cloud_water_multi_year",
                "task_id": "synthetic-2021-2025",
                "start_year": 2021,
                "end_year": 2025,
                "region_name": "合成测试区",
                "product_source": {"root": str(root), "engine": "scipy"},
                "region_spec": {
                    "kind": "existing_mask",
                    "payload": {"path": str(mask_path)},
                },
                "output_root": "multi-year-run",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return spec_path


def test_multi_year_metrics_use_equal_year_means_and_complete_catalog(
    tmp_path: Path,
):
    root, mask_path = _write_products(tmp_path)
    spec = load_cloud_water_multi_year_metrics_spec(
        _write_spec(tmp_path, root, mask_path)
    )

    metrics, spatial = derive_cloud_water_multi_year_business_metrics(spec)

    assert metrics["year_count"] == 5
    assert metrics["source"]["annual_product_count"] == 5
    assert metrics["source"]["monthly_product_count"] == 60
    assert len(metrics["monthly_climatology"]) == 12
    assert len(metrics["seasonal_climatology"]) == 4
    assert metrics["monthly_climatology"][0]["SP"] == pytest.approx(12.0)
    annual_sp = [row["values"]["SP"] for row in metrics["annual_series"]]
    assert metrics["multi_year_mean"]["values"]["SP"] == pytest.approx(
        np.mean(annual_sp)
    )
    assert metrics["interannual"]["GMh"]["trend"]["significant"] is True
    assert metrics["interannual"]["GMh"]["trend"]["wording"] == "显著增加"
    assert spatial.sizes["season"] == 4
    assert bool(spatial["ind_area_bool"].all().item())
    assert np.isfinite(spatial["annual_mean_sp_mm"]).all().item()


def test_multi_year_display_ties_and_trend_wording():
    years = np.arange(2021, 2026)
    extrema = _extrema(years, np.array([1.01, 1.04, 2.0, 3.0, 3.04]))
    assert extrema["minimum"]["years"] == [2021, 2022]
    assert extrema["maximum"]["years"] == [2024, 2025]
    assert _trend(years, np.arange(5.0))["wording"] == "显著增加"
    assert _trend(years, np.ones(5))["wording"] == "基本稳定"
    nonsignificant = _trend(years, np.array([1.0, 3.0, 2.0, 5.0, 4.0]))
    assert nonsignificant["significant"] is False
    assert nonsignificant["wording"] == "增加"


def test_multi_year_missing_month_fails_without_output(tmp_path: Path):
    root, mask_path = _write_products(tmp_path)
    (root / "M" / "ResultGrid_M_2023-07-01-00_next.nc").unlink()
    spec_path = _write_spec(tmp_path, root, mask_path)

    with pytest.raises(ValueError, match="2023-07"):
        build_cloud_water_multi_year_business_metrics(spec_path)

    assert not (tmp_path / "multi-year-run").exists()


def test_multi_year_period_must_contain_at_least_five_years(tmp_path: Path):
    root, mask_path = _write_products(tmp_path)
    spec_path = _write_spec(tmp_path, root, mask_path)
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    payload["start_year"] = 2022
    spec_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="at least five years"):
        load_cloud_water_multi_year_metrics_spec(spec_path)
