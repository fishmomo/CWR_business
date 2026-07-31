import json
from pathlib import Path

import pytest

from cwr_engine.cli import main
from cwr_engine.workflows import cloud_water_single_year as workflow


def _write_workflow_spec(tmp_path: Path) -> Path:
    product_root = tmp_path / "products"
    product_root.mkdir()
    region = tmp_path / "region.shp"
    region.touch()
    template = tmp_path / "template.docx"
    template.touch()
    spec_path = tmp_path / "workflow.json"
    spec_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "workflow": "cloud_water_single_year",
                "task_id": "workflow-2025",
                "year": 2025,
                "region_name": "测试区域",
                "product_source": {
                    "root": str(product_root),
                    "engine": "scipy",
                },
                "region_spec": {
                    "kind": "shp",
                    "payload": {"path": str(region)},
                },
                "template": str(template),
                "output_root": "published-run",
                "report_filename": "report.docx",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return spec_path


def _fake_metrics_builder(spec_path: Path) -> Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    output_root = Path(spec["output_root"])
    metrics = output_root / "business_metrics" / "metrics.json"
    spatial = output_root / "spatial_composite" / "spatial.nc"
    images = [
        output_root / "profile_image" / f"target_image{index}.png"
        for index in range(1, 6)
    ]
    report_inputs = output_root / "report_inputs" / "report_inputs.json"
    for path in [metrics, spatial, *images, report_inputs]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"artifact")
    report_inputs.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task": {
                    "task_id": spec["task_id"],
                    "status": "success",
                    "output_root": str(output_root),
                },
                "inputs": {},
                "artifacts": [
                    {"kind": "business_metrics", "path": str(metrics)},
                    {"kind": "spatial_composite", "path": str(spatial)},
                    *[
                        {
                            "kind": "profile_image",
                            "name": f"target_image{index}",
                            "path": str(path),
                        }
                        for index, path in enumerate(images, start=1)
                    ],
                ],
                "runtime": {
                    "workflow_steps": [
                        "business_metrics",
                        "profile_figures",
                        "report_inputs",
                    ],
                    "executed_steps": [
                        "business_metrics",
                        "profile_figures",
                        "report_inputs",
                    ],
                },
                "stats": [],
            }
        ),
        encoding="utf-8",
    )
    return report_inputs


def _fake_report_builder(spec_path: Path) -> Path:
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    output = Path(spec["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"docx")
    return output


def test_workflow_publishes_complete_run_with_final_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    spec_path = _write_workflow_spec(tmp_path)
    monkeypatch.setattr(
        workflow,
        "build_cloud_water_business_metrics",
        _fake_metrics_builder,
    )
    monkeypatch.setattr(
        workflow,
        "build_cloud_water_single_year_report",
        _fake_report_builder,
    )

    assert main(["--workflow-spec", str(spec_path)]) == 0

    output = tmp_path / "published-run"
    report = output / "report" / "report.docx"
    assert capsys.readouterr().out.strip() == str(report)
    assert report.read_bytes() == b"docx"
    report_inputs = json.loads(
        (output / "report_inputs" / "report_inputs.json").read_text(
            encoding="utf-8"
        )
    )
    assert report_inputs["task"]["output_root"] == str(output)
    assert report_inputs["inputs"]["workflow"] == "cloud_water_single_year"
    assert len(report_inputs["artifacts"]) == 8
    assert report_inputs["artifacts"][-1]["kind"] == "docx_report"
    for artifact in report_inputs["artifacts"]:
        artifact_path = Path(artifact["path"])
        assert artifact_path.is_relative_to(output)
        assert artifact_path.is_file()
    assert report_inputs["runtime"]["executed_steps"][-1] == "docx_report"
    assert not list(tmp_path.glob(".published-run-staging-*"))
    assert not list(tmp_path.glob(".published-run-backup-*"))


def test_workflow_failure_preserves_existing_published_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    spec_path = _write_workflow_spec(tmp_path)
    published = tmp_path / "published-run"
    published.mkdir()
    marker = published / "accepted.txt"
    marker.write_text("accepted", encoding="utf-8")
    monkeypatch.setattr(
        workflow,
        "build_cloud_water_business_metrics",
        _fake_metrics_builder,
    )

    def fail_report(_: Path) -> Path:
        raise ValueError("report assembly failed")

    monkeypatch.setattr(
        workflow,
        "build_cloud_water_single_year_report",
        fail_report,
    )

    with pytest.raises(ValueError, match="report assembly failed"):
        workflow.build_cloud_water_single_year_workflow(spec_path)

    assert marker.read_text(encoding="utf-8") == "accepted"
    assert list(published.iterdir()) == [marker]
    assert not list(tmp_path.glob(".published-run-staging-*"))
    assert not list(tmp_path.glob(".published-run-backup-*"))
