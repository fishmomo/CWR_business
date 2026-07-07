import json
import csv
from pathlib import Path

from cwr_engine import __version__
from cwr_engine.cli import main
from cwr_engine.pipeline import run_task


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
    assert rows[1] == ["temp", "mean", "11.50"]


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
