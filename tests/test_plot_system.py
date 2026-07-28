import json
from pathlib import Path

import matplotlib.image as mpimg
import numpy as np
import pytest
import xarray as xr

from cwr_engine.pipeline import run_task


def _write_plot_task(tmp_path: Path, outputs: list[dict]) -> Path:
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
            "time": np.array(
                ["2025-01-01", "2025-02-01"],
                dtype="datetime64[ns]",
            ),
            "lat": [30.0, 31.0],
            "lon": [100.0, 101.0],
        },
    ).to_netcdf(tmp_path / "monthly.nc", engine="scipy")
    task_path = tmp_path / "plot_task.json"
    task_path.write_text(
        json.dumps(
            {
                "task_id": "plot-system",
                "data_source": {
                    "name": "nc",
                    "root": "monthly.nc",
                    "engine": "scipy",
                    "time_scale": "month",
                },
                "time_slices": [
                    {"scale": "month", "year": 2025, "month": 1},
                    {"scale": "month", "year": 2025, "month": 2},
                ],
                "region_spec": {
                    "kind": "bbox",
                    "payload": {
                        "min_lon": 100.0,
                        "max_lon": 100.0,
                        "min_lat": 30.0,
                        "max_lat": 31.0,
                    },
                },
                "variables": ["temp"],
                "operators": ["mean", "max"],
                "outputs": outputs,
                "workflow_steps": [
                    "prepare",
                    "mask",
                    "subset",
                    "transform",
                    "stat",
                    "plot",
                    "report_inputs",
                ],
                "reuse_policy": {},
                "output_root": "artifacts/runs/plot-system",
            }
        ),
        encoding="utf-8",
    )
    return task_path


def test_plot_registry_dispatches_all_standard_figure_types(tmp_path: Path):
    task_path = _write_plot_task(
        tmp_path,
        outputs=[
            {
                "kind": "figure_timeseries",
                "name": "series",
                "params": {
                    "title": "Series {variable}",
                    "figsize": [5, 3],
                    "dpi": 90,
                    "line_color": "#0b6e4f",
                    "ylabel": "Temperature",
                },
            },
            {
                "kind": "figure_distribution",
                "name": "spatial",
                "params": {
                    "title": "{label} {variable} {operator}",
                    "figsize": [4, 3],
                    "dpi": 100,
                    "cmap": "viridis",
                    "vmin": 0,
                    "vmax": 10,
                    "colorbar_label": "degC",
                },
            },
            {
                "kind": "figure_bar_compare",
                "name": "compare",
                "params": {
                    "title": "{variable} {operator}",
                    "figsize": [5, 3],
                    "dpi": 90,
                    "bar_color": "#c65d2e",
                    "ylabel": "Temperature",
                },
            },
            {"kind": "report_inputs", "name": "report_inputs"},
        ],
    )

    report_path = run_task(task_path, tmp_path / "result")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    mask_bundle = json.loads(
        (tmp_path / "result" / "mask" / "mask_bundle.json").read_text(
            encoding="utf-8"
        )
    )
    assert mask_bundle["spatial_bounds"] == {
        "min_lon": 100.0,
        "max_lon": 100.0,
        "min_lat": 30.0,
        "max_lat": 31.0,
    }
    figure_artifacts = [
        item for item in report["artifacts"] if item["kind"].startswith("figure_")
    ]
    assert len(figure_artifacts) == 7
    assert {
        Path(item["path"]).name for item in figure_artifacts
    } == {
        "series_temp.png",
        "spatial_2025-01_temp_mean.png",
        "spatial_2025-01_temp_max.png",
        "spatial_2025-02_temp_mean.png",
        "spatial_2025-02_temp_max.png",
        "compare_temp_mean.png",
        "compare_temp_max.png",
    }
    for artifact in figure_artifacts:
        image = mpimg.imread(artifact["path"])
        assert image.shape[0] > 100
        assert image.shape[1] > 100
    distribution = next(
        item
        for item in figure_artifacts
        if Path(item["path"]).name == "spatial_2025-01_temp_mean.png"
    )
    assert distribution == {
        "kind": "figure_distribution",
        "path": str(
            tmp_path
            / "result"
            / "plot"
            / "spatial_2025-01_temp_mean.png"
        ),
        "variable": "temp",
        "operator": "mean",
        "label": "2025-01",
    }


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"unknown": 1}, "Unsupported plot parameter"),
        ({"figsize": [5, 0]}, "figsize values must be positive"),
        ({"title": "{label}"}, "Unsupported title field"),
        ({"title": "{variable"}, "Invalid title template"),
        ({"line_color": "not-a-color"}, "Invalid color"),
    ],
)
def test_invalid_plot_parameters_fail_before_output_creation(
    tmp_path: Path,
    params: dict,
    message: str,
):
    task_path = _write_plot_task(
        tmp_path,
        outputs=[
            {
                "kind": "figure_timeseries",
                "name": "series",
                "params": params,
            }
        ],
    )

    with pytest.raises(ValueError, match=message):
        run_task(task_path, tmp_path / "result")
    assert not (tmp_path / "result").exists()
