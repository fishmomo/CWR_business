import csv
import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from cwr_engine.cli import main
from cwr_engine.workflows.daily_precipitation_request import (
    build_daily_precipitation_request_set,
    load_daily_precipitation_request_set,
)


def _write_products(tmp_path: Path) -> None:
    source = tmp_path / "products"
    source.mkdir()
    for day, sp_value in enumerate((4.0, 8.0, 12.0), start=1):
        values = np.full((2, 2), sp_value)
        xr.Dataset(
            data_vars={
                "SP": (("lat", "lon"), values),
                "GMh": (("lat", "lon"), values * 2.0),
                "CWR": (("lat", "lon"), np.full((2, 2), 2.0)),
                "dxy": (("lat", "lon"), np.full((2, 2), 10.0)),
            },
            coords={
                "time": np.datetime64(f"2025-01-{day:02d}"),
                "lat": [40.0, 41.0],
                "lon": [100.0, 101.0],
            },
        ).to_netcdf(
            source
            / f"ResultGrid_D_2025-01-{day:02d}-00_2025-01-{day + 1:02d}-00.nc",
            engine="scipy",
        )


def _payload(tmp_path: Path) -> dict:
    return {
        "schema_version": 1,
        "request_set": "daily_precipitation_analysis",
        "request_set_id": "synthetic-daily-precipitation",
        "shared_request": {
            "data_source": {
                "kind": "netcdf",
                "root": str(tmp_path / "products"),
                "engine": "scipy",
            },
            "region": {
                "kind": "bbox",
                "min_lon": 100.0,
                "max_lon": 101.0,
                "min_lat": 40.0,
                "max_lat": 41.0,
            },
        },
        "requests": {
            "daily": {
                "request_id": "synthetic-daily-standard",
                "period": {
                    "scale": "day",
                    "date_range": ["2025-01-01", "2025-01-03"],
                },
                "variables": ["Ps", "GMh", "CWR"],
                "operators": ["sum"],
                "results": [
                    {"scope": "region", "format": "csv", "name": "daily_regional"},
                    {"scope": "grid", "format": "netcdf", "name": "daily_grids"},
                ],
            }
        },
        "product": {
            "region_name": "synthetic region",
            "output_prefix": "synthetic_2025",
        },
        "output_root": str(tmp_path / "run"),
    }


def _write_spec(tmp_path: Path, mutate=None) -> Path:
    _write_products(tmp_path)
    payload = _payload(tmp_path)
    if mutate:
        mutate(payload)
    path = tmp_path / "request-set.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_daily_precipitation_request_runs_shared_pipeline_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _write_spec(tmp_path)
    import cwr_engine.data_sources.netcdf as netcdf
    import cwr_engine.pipeline as pipeline

    original_load = netcdf.load_single_netcdf_file
    original_mask = pipeline.mask.run
    counts = {"loads": 0, "masks": 0}

    def count_load(*args, **kwargs):
        counts["loads"] += 1
        return original_load(*args, **kwargs)

    def count_mask(*args, **kwargs):
        counts["masks"] += 1
        return original_mask(*args, **kwargs)

    monkeypatch.setattr(netcdf, "load_single_netcdf_file", count_load)
    monkeypatch.setattr(pipeline.mask, "run", count_mask)

    assert main(["--request", str(spec_path)]) == 0

    output = tmp_path / "run"
    with (
        output
        / "daily_precipitation"
        / "synthetic_2025_daily_precipitation_pe.csv"
    ).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 3
    assert float(rows[0]["precipitation_mm"]) == pytest.approx(0.4)
    assert float(rows[0]["precipitation_efficiency_pct"]) == pytest.approx(50.0)

    classes = xr.load_dataset(
        output
        / "precipitation_classes"
        / "synthetic_2025_precipitation_class_distribution.nc",
        engine="h5netcdf",
    )
    assert classes.attrs["sample_days"] == 3
    assert np.all(classes["light_days"].values == 3)
    assert np.allclose(classes["light_cwr_mm"].values, 0.6)
    assert counts == {"loads": 3, "masks": 1}
    assert (output / "standard_request" / "export" / "daily_grids.nc").exists()
    assert (output / "report_inputs" / "request_set_manifest.json").exists()
    assert not any(
        "-staging-" in path.read_text(encoding="utf-8")
        for path in output.rglob("*.json")
    )


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload["requests"]["daily"]["period"].update(
                {"date_range": ["2025-12-31", "2026-01-01"]}
            ),
            "exactly one year",
        ),
        (
            lambda payload: payload["requests"]["daily"].update(
                {"variables": ["Ps", "CWR"]}
            ),
            "variables must be exactly",
        ),
        (
            lambda payload: payload["product"].update({"unknown": True}),
            "not a recognized field",
        ),
    ],
)
def test_daily_precipitation_request_rejects_invalid_protocol(
    tmp_path: Path,
    mutate,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        load_daily_precipitation_request_set(_write_spec(tmp_path, mutate))


def test_daily_precipitation_request_missing_day_preserves_output(tmp_path: Path) -> None:
    spec_path = _write_spec(tmp_path)
    output = tmp_path / "run"
    output.mkdir()
    marker = output / "accepted.txt"
    marker.write_text("accepted", encoding="utf-8")
    next((tmp_path / "products").glob("ResultGrid_D_2025-01-02-*.nc")).unlink()

    with pytest.raises(ValueError, match="Missing day source periods"):
        build_daily_precipitation_request_set(spec_path)

    assert list(output.iterdir()) == [marker]


def test_daily_precipitation_request_publish_failure_preserves_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    spec_path = _write_spec(tmp_path)
    output = tmp_path / "run"
    output.mkdir()
    marker = output / "accepted.txt"
    marker.write_text("accepted", encoding="utf-8")
    import cwr_engine.workflows.daily_precipitation_request as request

    monkeypatch.setattr(
        request,
        "publish_directory",
        lambda *_: (_ for _ in ()).throw(OSError("publish failed")),
    )
    with pytest.raises(OSError, match="publish failed"):
        build_daily_precipitation_request_set(spec_path)

    assert list(output.iterdir()) == [marker]
