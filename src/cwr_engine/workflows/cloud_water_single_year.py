from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil
import tempfile
from typing import Any
from uuid import uuid4

from cwr_engine.business_metrics.cloud_water import (
    build_cloud_water_business_metrics,
)
from cwr_report.profiles.cloud_water_single_year import (
    IMAGE_SLOTS,
    _image_width_overrides,
    build_cloud_water_single_year_report,
)


WORKFLOW_NAME = "cloud_water_single_year"


@dataclass(frozen=True)
class CloudWaterSingleYearWorkflowSpec:
    task_id: str
    year: int
    region_name: str
    product_source: dict[str, Any]
    region_spec: dict[str, Any]
    template: Path
    output_root: Path
    report_filename: str
    artifact_name: str
    image_width_inches: float
    image_widths_inches: dict[str, float]


def build_cloud_water_single_year_workflow(spec_path: Path) -> Path:
    spec = load_cloud_water_single_year_workflow_spec(spec_path)
    output_parent = spec.output_root.parent
    output_parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix=f".{spec.output_root.name}-staging-",
        dir=output_parent,
    ) as raw_temp:
        temp = Path(raw_temp)
        staged_output = temp / "output"
        metrics_spec_path = temp / "business-metrics.json"
        profile_spec_path = temp / "report-profile.json"

        metrics_spec_path.write_text(
            json.dumps(
                _metrics_spec_payload(spec, staged_output),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        report_inputs_path = build_cloud_water_business_metrics(
            metrics_spec_path
        )

        staged_report = staged_output / "report" / spec.report_filename
        profile_spec_path.write_text(
            json.dumps(
                {
                    "profile": WORKFLOW_NAME,
                    "report_inputs": str(report_inputs_path),
                    "template": str(spec.template),
                    "output": str(staged_report),
                    "image_width_inches": spec.image_width_inches,
                    "image_widths_inches": spec.image_widths_inches,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        build_cloud_water_single_year_report(profile_spec_path)
        _finalize_report_inputs(
            report_inputs_path,
            staged_output,
            spec.output_root,
            spec.report_filename,
        )
        _publish_directory(staged_output, spec.output_root)

    return spec.output_root / "report" / spec.report_filename


def load_cloud_water_single_year_workflow_spec(
    path: Path,
) -> CloudWaterSingleYearWorkflowSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version", 1) != 1:
        raise ValueError("schema_version must be 1")
    if payload.get("workflow") != WORKFLOW_NAME:
        raise ValueError(f"workflow must be {WORKFLOW_NAME}")

    base = path.parent
    task_id = _required_text(payload, "task_id")
    year = payload.get("year")
    if not isinstance(year, int) or isinstance(year, bool):
        raise ValueError("year must be an integer")
    region_name = _required_text(payload, "region_name")
    product_source = _product_source(base, payload.get("product_source"))
    region_spec = _region_spec(base, payload.get("region_spec"))
    template = _existing_file(base, payload, "template")
    output_root = _path(base, payload, "output_root")
    if output_root.exists() and not output_root.is_dir():
        raise ValueError(f"output_root is not a directory: {output_root}")

    report_filename = payload.get(
        "report_filename",
        f"{year}-cloud-water-single-year.docx",
    )
    if (
        not isinstance(report_filename, str)
        or not report_filename.strip()
        or Path(report_filename).name != report_filename
        or Path(report_filename).suffix.lower() != ".docx"
    ):
        raise ValueError("report_filename must be a .docx filename")
    final_report = output_root / "report" / report_filename
    if final_report.resolve() == template.resolve():
        raise ValueError("workflow report must not overwrite the template")

    artifact_name = payload.get("artifact_name", WORKFLOW_NAME)
    if (
        not isinstance(artifact_name, str)
        or not artifact_name.strip()
        or Path(artifact_name).name != artifact_name
    ):
        raise ValueError("artifact_name must be a non-empty filename stem")
    width = payload.get("image_width_inches", 4.0)
    if (
        not isinstance(width, (int, float))
        or isinstance(width, bool)
        or width <= 0
    ):
        raise ValueError("image_width_inches must be positive")
    width_overrides = _image_width_overrides(
        payload.get("image_widths_inches", {}),
        IMAGE_SLOTS,
    )

    return CloudWaterSingleYearWorkflowSpec(
        task_id=task_id,
        year=year,
        region_name=region_name,
        product_source=product_source,
        region_spec=region_spec,
        template=template,
        output_root=output_root,
        report_filename=report_filename,
        artifact_name=artifact_name,
        image_width_inches=float(width),
        image_widths_inches=width_overrides,
    )


def _metrics_spec_payload(
    spec: CloudWaterSingleYearWorkflowSpec,
    staged_output: Path,
) -> dict[str, Any]:
    return {
        "metric_profile": WORKFLOW_NAME,
        "task_id": spec.task_id,
        "year": spec.year,
        "region_name": spec.region_name,
        "product_source": spec.product_source,
        "region_spec": spec.region_spec,
        "output_root": str(staged_output),
        "artifact_name": spec.artifact_name,
    }


def _finalize_report_inputs(
    path: Path,
    staged_output: Path,
    final_output: Path,
    report_filename: str,
) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload = _rebase_paths(payload, staged_output, final_output)
    payload["inputs"]["workflow"] = WORKFLOW_NAME
    payload["artifacts"].append(
        {
            "kind": "docx_report",
            "name": Path(report_filename).stem,
            "profile": WORKFLOW_NAME,
            "schema_version": 1,
            "path": str(final_output / "report" / report_filename),
        }
    )
    steps = payload["runtime"]["workflow_steps"]
    executed = payload["runtime"]["executed_steps"]
    if "docx_report" not in steps:
        steps.append("docx_report")
    if "docx_report" not in executed:
        executed.append("docx_report")
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _rebase_paths(value: Any, source_root: Path, target_root: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: _rebase_paths(item, source_root, target_root)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _rebase_paths(item, source_root, target_root) for item in value
        ]
    if not isinstance(value, str):
        return value
    try:
        relative = Path(value).resolve().relative_to(source_root.resolve())
    except (OSError, ValueError):
        return value
    return str(target_root / relative)


def _publish_directory(staged: Path, target: Path) -> None:
    backup: Path | None = None
    if target.exists():
        backup = target.parent / f".{target.name}-backup-{uuid4().hex}"
        target.replace(backup)
    try:
        staged.replace(target)
    except Exception:
        if backup is not None and backup.exists():
            backup.replace(target)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _path(base: Path, payload: dict[str, Any], key: str) -> Path:
    raw = _required_text(payload, key)
    path = Path(raw)
    return path if path.is_absolute() else (base / path).resolve()


def _existing_file(
    base: Path,
    payload: dict[str, Any],
    key: str,
) -> Path:
    path = _path(base, payload, key)
    if not path.is_file():
        raise ValueError(f"{key} does not exist: {path}")
    return path


def _product_source(base: Path, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("product_source must be an object")
    raw_root = value.get("root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise ValueError("product_source.root must be a non-empty path")
    root = Path(raw_root)
    root = root if root.is_absolute() else (base / root).resolve()
    if not root.is_dir():
        raise ValueError(f"product_source.root does not exist: {root}")
    return {**value, "root": str(root)}


def _region_spec(base: Path, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("region_spec must be an object")
    kind = value.get("kind")
    region_payload = value.get("payload")
    if kind not in {"shp", "existing_mask", "bbox"}:
        raise ValueError("region_spec.kind must be shp, existing_mask, or bbox")
    if not isinstance(region_payload, dict):
        raise ValueError("region_spec.payload must be an object")
    resolved = dict(region_payload)
    if kind in {"shp", "existing_mask"}:
        raw_path = region_payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("region_spec.payload.path must be a non-empty path")
        region_path = Path(raw_path)
        if not region_path.is_absolute():
            region_path = (base / region_path).resolve()
        if not region_path.is_file():
            raise ValueError(f"region_spec path does not exist: {region_path}")
        resolved["path"] = str(region_path)
    return {"kind": kind, "payload": resolved}
