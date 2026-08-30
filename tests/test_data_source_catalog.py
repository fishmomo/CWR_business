import csv
import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from cwr_engine.pipeline import run_task


def _write_product(
    path: Path,
    timestamp: str,
    gmv: np.ndarray,
    sp: np.ndarray,
    *,
    lat_name: str = "latitude",
    lon_name: str = "longitude",
    time_name: str = "time",
    lat_values: list[float] | None = None,
    lon_values: list[float] | None = None,
) -> None:
    xr.Dataset(
        data_vars={
            "GMv": ((lat_name, lon_name), gmv),
            "SP": ((lat_name, lon_name), sp),
        },
        coords={
            lat_name: lat_values or [31.0, 30.0],
            lon_name: lon_values or [101.0, 100.0],
            time_name: np.datetime64(timestamp),
        },
    ).to_netcdf(path, engine="scipy")


def _write_split_coordinate_product(path: Path) -> None:
    xr.Dataset(
        data_vars={
            "GMv": (
                ("y_coord", "x_coord"),
                np.ones((2, 2)),
            ),
            "SP": (
                ("y_coord", "x_coord"),
                np.ones((2, 2)),
            ),
        },
        coords={
            "y_coord": ("lat_index", [31.0, 30.0]),
            "x_coord": ("lon_index", [101.0, 100.0]),
            "valid_time": np.datetime64("2025-01-01"),
        },
    ).to_netcdf(path, engine="scipy")


def _write_task(
    tmp_path: Path,
    *,
    root: str,
    time_slices: list[dict],
    coordinate_map: dict[str, str] | None = None,
) -> Path:
    data_source = {
        "name": "nc",
        "root": root,
        "engine": "scipy",
        "time_scale": "month",
    }
    if coordinate_map:
        data_source["coordinate_map"] = coordinate_map
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "catalog-test",
                "data_source": data_source,
                "time_slices": time_slices,
                "region_spec": {
                    "kind": "bbox",
                    "payload": {
                        "min_lon": 100.0,
                        "max_lon": 101.0,
                        "min_lat": 30.0,
                        "max_lat": 31.0,
                    },
                },
                "variables": ["GMv", "Ps"],
                "operators": ["mean"],
                "outputs": [
                    {"kind": "region_table", "name": "monthly"},
                    {"kind": "grid_nc", "name": "monthly_grid"},
                    {"kind": "report_inputs", "name": "report_inputs"},
                ],
                "workflow_steps": [
                    "prepare",
                    "mask",
                    "subset",
                    "transform",
                    "stat",
                    "export",
                    "report_inputs",
                ],
                "reuse_policy": {},
                "output_root": "artifacts/runs/catalog-test",
            }
        ),
        encoding="utf-8",
    )
    return task_path


def test_catalog_loads_only_requested_files_and_normalizes_coordinates(
    tmp_path: Path,
):
    catalog = tmp_path / "catalog" / "M"
    catalog.mkdir(parents=True)
    _write_product(
        catalog / "ResultGrid_M_2025-01-01-00_2025-02-01-00.nc",
        "2025-01-01",
        np.array([[4.0, 3.0], [2.0, 1.0]]),
        np.array([[40.0, 30.0], [20.0, 10.0]]),
    )
    _write_product(
        catalog / "ResultGrid_M_2025-02-01-00_2025-03-01-00.nc",
        "2025-02-01",
        np.array([[8.0, 7.0], [6.0, 5.0]]),
        np.array([[80.0, 70.0], [60.0, 50.0]]),
    )
    # This malformed file is outside the request and must never be opened.
    (catalog / "ResultGrid_M_2025-03-01-00_2025-04-01-00.nc").write_text(
        "not a netcdf file",
        encoding="ascii",
    )
    task_path = _write_task(
        tmp_path,
        root="catalog",
        time_slices=[
            {"scale": "month", "year": 2025, "month": 1},
            {"scale": "month", "year": 2025, "month": 2},
        ],
    )

    report_path = run_task(task_path, tmp_path / "result")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["runtime"]["data_source"]["file_count"] == 2

    with (tmp_path / "result" / "export" / "monthly.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.reader(handle))
    assert rows[1:] == [
        ["2025-01", "GMv", "mean", "2.50"],
        ["2025-02", "GMv", "mean", "6.50"],
        ["2025-01", "Ps", "mean", "25.00"],
        ["2025-02", "Ps", "mean", "65.00"],
    ]

    grid = xr.load_dataset(
        tmp_path / "result" / "export" / "monthly_grid.nc",
        engine="h5netcdf",
    )
    assert list(grid.dims) == ["period", "lat", "lon"]
    assert list(grid["period"].values) == ["2025-01", "2025-02"]
    assert np.all(np.diff(grid["lat"].values) > 0)
    assert np.all(np.diff(grid["lon"].values) > 0)
    assert grid["Ps"].attrs["source_variable"] == "SP"


def test_catalog_supports_explicit_coordinate_mapping(tmp_path: Path):
    catalog = tmp_path / "M"
    catalog.mkdir()
    _write_split_coordinate_product(
        catalog / "ResultGrid_M_2025-01-01-00_2025-02-01-00.nc"
    )
    task_path = _write_task(
        tmp_path,
        root="M",
        time_slices=[{"scale": "month", "year": 2025, "month": 1}],
        coordinate_map={
            "time": "valid_time",
            "lat": "y_coord",
            "lon": "x_coord",
        },
    )

    report_path = run_task(task_path, tmp_path / "result")
    assert report_path.exists()


def test_catalog_reports_missing_requested_period(tmp_path: Path):
    catalog = tmp_path / "catalog" / "M"
    catalog.mkdir(parents=True)
    _write_product(
        catalog / "ResultGrid_M_2025-01-01-00_2025-02-01-00.nc",
        "2025-01-01",
        np.ones((2, 2)),
        np.ones((2, 2)),
    )
    task_path = _write_task(
        tmp_path,
        root="catalog",
        time_slices=[
            {"scale": "month", "year": 2025, "month": 1},
            {"scale": "month", "year": 2025, "month": 2},
        ],
    )

    with pytest.raises(ValueError, match="Missing month source periods: 2025-02-01"):
        run_task(task_path, tmp_path / "result")
    assert not (tmp_path / "result" / "export" / "monthly.csv").exists()


def test_catalog_rejects_duplicate_internal_times(tmp_path: Path):
    catalog = tmp_path / "catalog" / "M"
    catalog.mkdir(parents=True)
    _write_product(
        catalog / "ResultGrid_M_2025-01-01-00_2025-02-01-00.nc",
        "2025-01-01",
        np.ones((2, 2)),
        np.ones((2, 2)),
    )
    _write_product(
        catalog / "ResultGrid_M_2025-02-01-00_2025-03-01-00.nc",
        "2025-01-01",
        np.ones((2, 2)),
        np.ones((2, 2)),
    )
    task_path = _write_task(
        tmp_path,
        root="catalog",
        time_slices=[
            {"scale": "month", "year": 2025, "month": 1},
            {"scale": "month", "year": 2025, "month": 2},
        ],
    )

    with pytest.raises(ValueError, match="Duplicate source times: 2025-01-01"):
        run_task(task_path, tmp_path / "result")
    assert not (tmp_path / "result" / "export" / "monthly.csv").exists()


def test_catalog_requires_requested_variables_in_every_selected_file(
    tmp_path: Path,
):
    catalog = tmp_path / "catalog" / "M"
    catalog.mkdir(parents=True)
    _write_product(
        catalog / "ResultGrid_M_2025-01-01-00_2025-02-01-00.nc",
        "2025-01-01",
        np.ones((2, 2)),
        np.ones((2, 2)),
    )
    xr.Dataset(
        data_vars={"GMv": (("latitude", "longitude"), np.ones((2, 2)))},
        coords={
            "latitude": [31.0, 30.0],
            "longitude": [101.0, 100.0],
            "time": np.datetime64("2025-02-01"),
        },
    ).to_netcdf(
        catalog / "ResultGrid_M_2025-02-01-00_2025-03-01-00.nc",
        engine="scipy",
    )
    task_path = _write_task(
        tmp_path,
        root="catalog",
        time_slices=[
            {"scale": "month", "year": 2025, "month": 1},
            {"scale": "month", "year": 2025, "month": 2},
        ],
    )

    with pytest.raises(ValueError, match="No source field found for variable Ps"):
        run_task(task_path, tmp_path / "result")
    assert not (tmp_path / "result" / "export" / "monthly.csv").exists()


def test_catalog_rejects_incompatible_product_grids(tmp_path: Path):
    catalog = tmp_path / "catalog" / "M"
    catalog.mkdir(parents=True)
    _write_product(
        catalog / "ResultGrid_M_2025-01-01-00_2025-02-01-00.nc",
        "2025-01-01",
        np.ones((2, 2)),
        np.ones((2, 2)),
    )
    _write_product(
        catalog / "ResultGrid_M_2025-02-01-00_2025-03-01-00.nc",
        "2025-02-01",
        np.ones((2, 2)),
        np.ones((2, 2)),
        lat_values=[32.0, 30.0],
    )
    task_path = _write_task(
        tmp_path,
        root="catalog",
        time_slices=[
            {"scale": "month", "year": 2025, "month": 1},
            {"scale": "month", "year": 2025, "month": 2},
        ],
    )

    with pytest.raises(ValueError, match="Product files use incompatible grids"):
        run_task(task_path, tmp_path / "result")
    assert not (tmp_path / "result" / "export" / "monthly.csv").exists()
