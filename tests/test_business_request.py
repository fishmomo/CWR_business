import csv
import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from cwr_engine.business_request import (
    compile_business_request,
    load_business_request,
)
from cwr_engine.cli import main


def _base_request() -> dict:
    return {
        "schema_version": 1,
        "request_id": "monthly-analysis",
        "data_source": {
            "kind": "netcdf",
            "root": "catalog",
            "engine": "scipy",
        },
        "region": {
            "kind": "bbox",
            "min_lon": 100.0,
            "max_lon": 101.0,
            "min_lat": 30.0,
            "max_lat": 31.0,
        },
        "period": {
            "scale": "month",
            "years": [2025],
            "months": [1, 2],
        },
        "variables": ["temp", "precip"],
        "operators": ["mean", "max"],
        "results": [
            {"scope": "region", "format": "csv", "name": "regional"},
            {"scope": "grid", "format": "netcdf", "name": "gridded"},
            {
                "scope": "region",
                "format": "figure",
                "plot": "time_series",
                "name": "series",
            },
            {
                "scope": "grid",
                "format": "figure",
                "plot": "distribution",
                "name": "maps",
            },
        ],
        "output_root": "outputs/monthly-analysis",
    }


def _write_request(tmp_path: Path, payload: dict | None = None) -> Path:
    request_path = tmp_path / "request.json"
    request_path.write_text(
        json.dumps(payload or _base_request()),
        encoding="utf-8",
    )
    return request_path


def _write_monthly_catalog(tmp_path: Path) -> None:
    catalog = tmp_path / "catalog" / "M"
    catalog.mkdir(parents=True)
    for month, offset in ((1, 0.0), (2, 4.0)):
        values = np.arange(1.0, 5.0).reshape(2, 2) + offset
        xr.Dataset(
            data_vars={
                "temp": (("lat", "lon"), values),
                "precip": (("lat", "lon"), values * 10),
            },
            coords={
                "time": np.datetime64(f"2025-{month:02d}-01"),
                "lat": [30.0, 31.0],
                "lon": [100.0, 101.0],
            },
        ).to_netcdf(
            catalog
            / f"ResultGrid_M_2025-{month:02d}-01-00_2025-{month + 1:02d}-01-00.nc",
            engine="scipy",
        )


@pytest.mark.parametrize(
    ("period", "labels"),
    [
        (
            {"scale": "year", "year_range": [2023, 2025]},
            ["2023", "2024", "2025"],
        ),
        (
            {"scale": "month", "years": [2024, 2025], "months": [1, 6]},
            ["2024-01", "2024-06", "2025-01", "2025-06"],
        ),
        (
            {"scale": "month", "items": ["2025-02", "2024-12"]},
            ["2024-12", "2025-02"],
        ),
        (
            {"scale": "day", "date_range": ["2025-01-30", "2025-02-01"]},
            ["2025-01-30", "2025-01-31", "2025-02-01"],
        ),
    ],
)
def test_compiler_normalizes_business_periods(
    tmp_path: Path,
    period: dict,
    labels: list[str],
):
    payload = _base_request()
    payload["period"] = period
    request_path = _write_request(tmp_path, payload)

    request = load_business_request(request_path)
    task = compile_business_request(request, request_path)

    assert [item.label for item in task.time_slices] == labels
    assert task.data_source["time_scale"] == period["scale"]


def test_compiler_maps_business_outputs_and_internal_steps(tmp_path: Path):
    request_path = _write_request(tmp_path)

    request = load_business_request(request_path)
    task = compile_business_request(request, request_path)

    assert task.data_source["root"] == str((tmp_path / "catalog").resolve())
    assert [item.kind for item in task.outputs] == [
        "region_table",
        "grid_nc",
        "figure_timeseries",
        "figure_distribution",
        "report_inputs",
    ]
    assert task.workflow_steps == [
        "prepare",
        "mask",
        "subset",
        "transform",
        "stat",
        "plot",
        "export",
        "report_inputs",
    ]
    assert task.output_root == str(
        (tmp_path / "outputs" / "monthly-analysis").resolve()
    )


@pytest.mark.parametrize(
    "region",
    [
        {"kind": "shp", "path": "region.shp"},
        {"kind": "existing_mask", "path": "mask.nc", "variable": "mask"},
        {
            "kind": "bbox",
            "min_lon": 100.0,
            "max_lon": 101.0,
            "min_lat": 30.0,
            "max_lat": 31.0,
        },
    ],
)
def test_every_region_input_compiles_to_the_mandatory_mask_stage(
    tmp_path: Path,
    region: dict,
):
    payload = _base_request()
    payload["region"] = region
    request_path = _write_request(tmp_path, payload)

    request = load_business_request(request_path)
    task = compile_business_request(request, request_path)

    assert task.region_spec.kind == region["kind"]
    assert "mask" in task.workflow_steps
    if "path" in region:
        assert task.region_spec.payload["path"] == str(
            (tmp_path / region["path"]).resolve()
        )


def test_cli_executes_business_request_and_preserves_grid_periods(
    tmp_path: Path,
):
    _write_monthly_catalog(tmp_path)
    request_path = _write_request(tmp_path)
    output_root = tmp_path / "result"

    code = main(
        [
            "--request",
            str(request_path),
            "--output-root",
            str(output_root),
        ]
    )

    assert code == 0
    manifest_path = output_root / "report_inputs" / "request_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["task"]["task_id"] == "monthly-analysis"
    assert manifest["inputs"]["time_slices"][1]["label"] == "2025-02"

    with (output_root / "export" / "regional.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.reader(handle))
    assert rows[1:5] == [
        ["2025-01", "temp", "mean", "2.50"],
        ["2025-01", "temp", "max", "4.00"],
        ["2025-02", "temp", "mean", "6.50"],
        ["2025-02", "temp", "max", "8.00"],
    ]

    grid = xr.load_dataset(output_root / "export" / "gridded.nc", engine="h5netcdf")
    assert list(grid["period"].values) == ["2025-01", "2025-02"]
    assert grid["temp_mean"].dims == ("period", "lat", "lon")
    assert set(grid.data_vars) == {
        "temp_mean",
        "temp_max",
        "precip_mean",
        "precip_max",
    }
    assert (output_root / "plot" / "series_temp.png").exists()
    assert (output_root / "plot" / "maps_2025-02_precip_max.png").exists()


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (
            lambda payload: payload.pop("region"),
            "region must be an object",
        ),
        (
            lambda payload: payload["period"].update({"items": ["2025-01"]}),
            "month period requires either items",
        ),
        (
            lambda payload: payload["results"].append(
                {"scope": "grid", "format": "csv"}
            ),
            "Unsupported result combination",
        ),
        (
            lambda payload: payload.update({"unknown": True}),
            "Unsupported business request field",
        ),
    ],
)
def test_invalid_request_fails_before_output_creation(
    tmp_path: Path,
    mutate,
    message: str,
):
    payload = _base_request()
    mutate(payload)
    request_path = _write_request(tmp_path, payload)
    output_root = tmp_path / "result"

    with pytest.raises(ValueError, match=message):
        main(
            [
                "--request",
                str(request_path),
                "--output-root",
                str(output_root),
            ]
        )

    assert not output_root.exists()


def test_all_standard_cloud_water_variable_names_are_registered(tmp_path: Path):
    payload = _base_request()
    payload["variables"] = [
        "GMv",
        "GMh",
        "Dv",
        "Dh",
        "CWR",
        "CEv",
        "PEv",
        "PEh",
        "Qvi",
        "Qvo",
        "Qhi",
        "Qho",
        "Cvh",
        "Ps",
        "RTv",
        "RTh",
    ]
    request_path = _write_request(tmp_path, payload)

    request = load_business_request(request_path)

    assert request.variables == payload["variables"]


def test_standard_cloud_water_aliases_and_net_transport_execute(tmp_path: Path):
    catalog = tmp_path / "catalog" / "Y"
    catalog.mkdir(parents=True)
    source_values = {
        "GMv": 10.0,
        "GMh": 20.0,
        "INv": 7.0,
        "OTv": 2.0,
        "INh": 8.0,
        "OTh": 3.0,
        "CWR": 4.0,
        "CEv": 5.0,
        "PEv": 6.0,
        "PEh": 7.0,
        "MC": 8.0,
        "SP": 9.0,
        "RCv": 10.0,
        "RCh": 11.0,
    }
    xr.Dataset(
        data_vars={
            name: (("lat", "lon"), np.full((2, 2), value))
            for name, value in source_values.items()
        },
        coords={
            "time": np.datetime64("2025-01-01"),
            "lat": [30.0, 31.0],
            "lon": [100.0, 101.0],
        },
    ).to_netcdf(
        catalog / "ResultGrid_Y_2025-01-01-00_2026-01-01-00.nc",
        engine="scipy",
    )
    payload = _base_request()
    payload["period"] = {"scale": "year", "years": [2025]}
    payload["variables"] = [
        "GMv",
        "GMh",
        "Dv",
        "Dh",
        "CWR",
        "CEv",
        "PEv",
        "PEh",
        "Qvi",
        "Qvo",
        "Qhi",
        "Qho",
        "Cvh",
        "Ps",
        "RTv",
        "RTh",
    ]
    payload["operators"] = ["mean"]
    payload["results"] = [
        {"scope": "region", "format": "csv", "name": "all_variables"}
    ]
    request_path = _write_request(tmp_path, payload)
    output_root = tmp_path / "result"

    assert main(
        ["--request", str(request_path), "--output-root", str(output_root)]
    ) == 0

    with (output_root / "export" / "all_variables.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    values = {row["variable"]: float(row["value"]) for row in rows}
    assert values == {
        "GMv": 10.0,
        "GMh": 20.0,
        "Dv": 5.0,
        "Dh": 5.0,
        "CWR": 4.0,
        "CEv": 5.0,
        "PEv": 6.0,
        "PEh": 7.0,
        "Qvi": 7.0,
        "Qvo": 2.0,
        "Qhi": 8.0,
        "Qho": 3.0,
        "Cvh": 8.0,
        "Ps": 9.0,
        "RTv": 10.0,
        "RTh": 11.0,
    }
