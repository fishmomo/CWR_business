import json
import csv
from pathlib import Path

import numpy as np
import pytest
import shapefile
import xarray as xr

from cwr_engine import __version__
from cwr_engine.cli import main
from cwr_engine.pipeline import run_task


def _write_demo_task(tmp_path: Path, outputs: list[dict], workflow_steps: list[str]) -> Path:
    task_path = tmp_path / "task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "output-contract",
                "data_source": {"name": "demo", "root": "data/inputs/demo.nc"},
                "time_slices": [{"scale": "year", "year": 2025}],
                "region_spec": {
                    "kind": "bbox",
                    "payload": {"min_lon": 100.0, "max_lon": 110.0, "min_lat": 30.0, "max_lat": 35.0},
                },
                "variables": ["temp"],
                "operators": ["mean"],
                "outputs": outputs,
                "workflow_steps": workflow_steps,
                "reuse_policy": {},
                "output_root": "artifacts/runs/output-contract",
            }
        ),
        encoding="utf-8",
    )
    return task_path


def test_package_imports():
    assert __version__ == "0.1.0"


def test_pipeline_writes_report_inputs(tmp_path: Path):
    report_path = run_task(
        task_path=Path("tests/fixtures/minimal_task.json"),
        output_root=tmp_path,
    )
    assert report_path.name == "report_inputs.json"
    assert report_path.exists()


def test_report_inputs_contains_contract_fields(tmp_path: Path):
    report_path = run_task(
        task_path=Path("tests/fixtures/minimal_task.json"),
        output_root=tmp_path,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["task"]["task_id"] == "demo-run"
    assert payload["inputs"]["variables"] == ["temp"]
    assert payload["inputs"]["requested_outputs"][0]["kind"] == "region_table"
    assert "artifacts" in payload
    assert "runtime" in payload
    assert payload["runtime"]["executed_steps"] == [
        "prepare",
        "mask",
        "subset",
        "transform",
        "stat",
        "plot",
        "export",
    ]


def test_pipeline_emits_csv_and_png_artifacts(tmp_path: Path):
    report_path = run_task(
        task_path=Path("tests/fixtures/minimal_task.json"),
        output_root=tmp_path,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    kinds = {item["kind"] for item in payload["artifacts"]}
    assert "region_table" in kinds
    assert "figure_timeseries" in kinds


def test_pipeline_exports_computed_mean_value(tmp_path: Path):
    report_path = run_task(
        task_path=Path("tests/fixtures/minimal_task.json"),
        output_root=tmp_path,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    csv_path = next(Path(item["path"]) for item in payload["artifacts"] if item["kind"] == "region_table")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1] == ["2025", "temp", "mean", "11.50"]


def test_cli_returns_zero(tmp_path: Path):
    code = main(
        [
            "--task",
            "tests/fixtures/minimal_task.json",
            "--output-root",
            str(tmp_path),
        ]
    )
    assert code == 0


def test_csv_only_task_returns_output_root_without_report_inputs(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "region_table", "name": "annual_table"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "stat", "export"],
    )
    result = run_task(task_path, tmp_path / "result")
    assert result == tmp_path / "result"
    assert (result / "export" / "annual_table.csv").exists()
    assert not (result / "report_inputs").exists()


def test_unknown_output_kind_fails_before_creating_artifacts(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "not_supported", "name": "bad"}],
        workflow_steps=["prepare"],
    )
    with pytest.raises(ValueError, match="Unsupported output kind: not_supported"):
        run_task(task_path, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_requested_csv_name_controls_export_filename(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "region_table", "name": "annual_table"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "stat", "export"],
    )
    root = run_task(task_path, tmp_path / "result")
    assert (root / "export" / "annual_table.csv").exists()
    assert not (root / "export" / "region_table.csv").exists()


def test_grid_nc_request_exports_masked_grid(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "grid_nc", "name": "annual_grid"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "export"],
    )
    root = run_task(task_path, tmp_path / "result")
    dataset = xr.load_dataset(root / "export" / "annual_grid.nc", engine="scipy")
    assert list(dataset.data_vars) == ["temp"]
    assert dataset["temp"].dims == ("lat", "lon")


def test_figure_only_task_creates_only_requested_figure(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "figure_timeseries", "name": "annual_series"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "plot"],
    )
    root = run_task(task_path, tmp_path / "result")
    assert (root / "plot" / "annual_series.png").exists()
    assert not (root / "export").exists()
    assert not (root / "report_inputs").exists()


def test_report_inputs_uses_requested_name_and_indexes_created_artifacts(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[
            {"kind": "region_table", "name": "annual_table"},
            {"kind": "report_inputs", "name": "annual_report_inputs"},
        ],
        workflow_steps=["prepare", "mask", "subset", "transform", "stat", "export", "report_inputs"],
    )
    report_path = run_task(task_path, tmp_path / "result")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path.name == "annual_report_inputs.json"
    assert [item["kind"] for item in payload["artifacts"]] == ["region_table"]


def test_pipeline_loads_real_netcdf_task(tmp_path: Path):
    dataset_path = tmp_path / "sample.nc"
    xr.Dataset(
        data_vars={
            "temp": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[1.0, 2.0], [3.0, 4.0]],
                        [[5.0, 6.0], [7.0, 8.0]],
                    ]
                ),
            )
        },
        coords={
            "time": np.array(["2025-01-01", "2025-02-01"], dtype="datetime64[ns]"),
            "lat": [30.0, 31.0],
            "lon": [100.0, 101.0],
        },
    ).to_netcdf(dataset_path, engine="scipy")

    task_path = tmp_path / "netcdf_task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "netcdf-run",
                "data_source": {
                    "name": "nc",
                    "root": "sample.nc",
                    "engine": "scipy",
                },
                "time_slices": [{"scale": "year", "year": 2025}],
                "region_spec": {
                    "kind": "bbox",
                    "payload": {
                        "min_lon": 100.0,
                        "max_lon": 101.0,
                        "min_lat": 30.0,
                        "max_lat": 31.0,
                    },
                },
                "variables": ["temp"],
                "operators": ["mean"],
                "outputs": [
                    {"kind": "region_table", "name": "temp_year_mean"},
                    {"kind": "figure_timeseries", "name": "temp_series"},
                    {"kind": "report_inputs", "name": "report_inputs"},
                ],
                "workflow_steps": [
                    "prepare",
                    "mask",
                    "subset",
                    "transform",
                    "stat",
                    "plot",
                    "export",
                    "report_inputs",
                ],
                "reuse_policy": {
                    "mask": True,
                    "subset": True,
                    "stat": True,
                    "plot": True,
                },
                "output_root": str(tmp_path / "unused-output-root"),
            }
        ),
        encoding="utf-8",
    )

    report_path = run_task(task_path=task_path, output_root=tmp_path / "result")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    csv_path = next(Path(item["path"]) for item in payload["artifacts"] if item["kind"] == "region_table")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1] == ["2025", "temp", "mean", "4.50"]


def test_pipeline_uses_existing_mask_for_statistics(tmp_path: Path):
    dataset_path = tmp_path / "sample.nc"
    xr.Dataset(
        data_vars={
            "temp": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[1.0, 2.0], [3.0, 4.0]],
                        [[5.0, 6.0], [7.0, 8.0]],
                    ]
                ),
            )
        },
        coords={
            "time": np.array(["2025-01-01", "2025-02-01"], dtype="datetime64[ns]"),
            "lat": [30.0, 31.0],
            "lon": [100.0, 101.0],
        },
    ).to_netcdf(dataset_path, engine="scipy")

    mask_path = tmp_path / "mask.nc"
    xr.Dataset(
        data_vars={
            "mask": (
                ("lat", "lon"),
                np.array(
                    [
                        [1, 0],
                        [0, 0],
                    ]
                ),
            )
        },
        coords={
            "lat": [30.0, 31.0],
            "lon": [100.0, 101.0],
        },
    ).to_netcdf(mask_path, engine="scipy")

    task_path = tmp_path / "mask_task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "existing-mask-run",
                "data_source": {
                    "name": "nc",
                    "root": "sample.nc",
                    "engine": "scipy",
                },
                "time_slices": [{"scale": "year", "year": 2025}],
                "region_spec": {
                    "kind": "existing_mask",
                    "payload": {
                        "path": "mask.nc",
                        "variable": "mask",
                        "engine": "scipy",
                    },
                },
                "variables": ["temp"],
                "operators": ["mean"],
                "outputs": [
                    {"kind": "region_table", "name": "temp_year_mean"},
                    {"kind": "figure_timeseries", "name": "temp_series"},
                    {"kind": "report_inputs", "name": "report_inputs"},
                ],
                "workflow_steps": [
                    "prepare",
                    "mask",
                    "subset",
                    "transform",
                    "stat",
                    "plot",
                    "export",
                    "report_inputs",
                ],
                "reuse_policy": {
                    "mask": True,
                    "subset": True,
                    "stat": True,
                    "plot": True,
                },
                "output_root": str(tmp_path / "unused-output-root"),
            }
        ),
        encoding="utf-8",
    )

    report_path = run_task(task_path=task_path, output_root=tmp_path / "result")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    csv_path = next(Path(item["path"]) for item in payload["artifacts"] if item["kind"] == "region_table")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1] == ["2025", "temp", "mean", "3.00"]


def test_pipeline_builds_mask_from_shapefile(tmp_path: Path):
    dataset_path = tmp_path / "sample.nc"
    xr.Dataset(
        data_vars={
            "temp": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[1.0, 2.0], [3.0, 4.0]],
                        [[5.0, 6.0], [7.0, 8.0]],
                    ]
                ),
            )
        },
        coords={
            "time": np.array(["2025-01-01", "2025-02-01"], dtype="datetime64[ns]"),
            "lat": [30.0, 31.0],
            "lon": [100.0, 101.0],
        },
    ).to_netcdf(dataset_path, engine="scipy")

    shp_path = tmp_path / "region.shp"
    writer = shapefile.Writer(str(shp_path))
    writer.field("name", "C")
    writer.poly([[[99.5, 29.5], [100.5, 29.5], [100.5, 30.5], [99.5, 30.5], [99.5, 29.5]]])
    writer.record("demo")
    writer.close()
    shp_path.with_suffix(".prj").write_text(
        'GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,298.257223563]],'
        'PRIMEM["Greenwich",0],UNIT["degree",0.0174532925199433]]',
        encoding="utf-8",
    )

    task_path = tmp_path / "shp_task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "shp-run",
                "data_source": {
                    "name": "nc",
                    "root": "sample.nc",
                    "engine": "scipy",
                },
                "time_slices": [{"scale": "year", "year": 2025}],
                "region_spec": {
                    "kind": "shp",
                    "payload": {
                        "path": "region.shp",
                    },
                },
                "variables": ["temp"],
                "operators": ["mean"],
                "outputs": [
                    {"kind": "region_table", "name": "temp_year_mean"},
                    {"kind": "figure_timeseries", "name": "temp_series"},
                    {"kind": "report_inputs", "name": "report_inputs"},
                ],
                "workflow_steps": [
                    "prepare",
                    "mask",
                    "subset",
                    "transform",
                    "stat",
                    "plot",
                    "export",
                    "report_inputs",
                ],
                "reuse_policy": {
                    "mask": True,
                    "subset": True,
                    "stat": True,
                    "plot": True,
                },
                "output_root": str(tmp_path / "unused-output-root"),
            }
        ),
        encoding="utf-8",
    )

    report_path = run_task(task_path=task_path, output_root=tmp_path / "result")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    csv_path = next(Path(item["path"]) for item in payload["artifacts"] if item["kind"] == "region_table")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1] == ["2025", "temp", "mean", "3.00"]


def test_pipeline_outputs_one_stat_row_per_time_slice(tmp_path: Path):
    dataset_path = tmp_path / "sample.nc"
    xr.Dataset(
        data_vars={
            "temp": (
                ("time", "lat", "lon"),
                np.array(
                    [
                        [[1.0, 1.0], [1.0, 1.0]],
                        [[2.0, 2.0], [2.0, 2.0]],
                        [[3.0, 3.0], [3.0, 3.0]],
                        [[4.0, 4.0], [4.0, 4.0]],
                    ]
                ),
            )
        },
        coords={
            "time": np.array(["2025-01-01", "2025-02-01", "2025-03-01", "2025-04-01"], dtype="datetime64[ns]"),
            "lat": [30.0, 31.0],
            "lon": [100.0, 101.0],
        },
    ).to_netcdf(dataset_path, engine="scipy")

    task_path = tmp_path / "month_task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "month-run",
                "data_source": {
                    "name": "nc",
                    "root": "sample.nc",
                    "engine": "scipy",
                },
                "time_slices": [
                    {"scale": "month", "year": 2025, "month": 1},
                    {"scale": "month", "year": 2025, "month": 3},
                ],
                "region_spec": {
                    "kind": "bbox",
                    "payload": {
                        "min_lon": 100.0,
                        "max_lon": 101.0,
                        "min_lat": 30.0,
                        "max_lat": 31.0,
                    },
                },
                "variables": ["temp"],
                "operators": ["mean"],
                "outputs": [
                    {"kind": "region_table", "name": "temp_month_mean"},
                    {"kind": "figure_timeseries", "name": "temp_series"},
                    {"kind": "report_inputs", "name": "report_inputs"},
                ],
                "workflow_steps": [
                    "prepare",
                    "mask",
                    "subset",
                    "transform",
                    "stat",
                    "plot",
                    "export",
                    "report_inputs",
                ],
                "reuse_policy": {
                    "mask": True,
                    "subset": True,
                    "stat": True,
                    "plot": True,
                },
                "output_root": str(tmp_path / "unused-output-root"),
            }
        ),
        encoding="utf-8",
    )

    report_path = run_task(task_path=task_path, output_root=tmp_path / "result")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    csv_path = next(Path(item["path"]) for item in payload["artifacts"] if item["kind"] == "region_table")
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.reader(handle))
    assert rows[1] == ["2025-01", "temp", "mean", "1.00"]
    assert rows[2] == ["2025-03", "temp", "mean", "3.00"]
