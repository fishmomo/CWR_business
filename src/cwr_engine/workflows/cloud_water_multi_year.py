from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

from cwr_engine.business_metrics.cloud_water_config import (
    existing_file,
    normalize_product_source,
    normalize_region_spec,
    required_text,
    resolve_path,
)
from cwr_engine.business_metrics.cloud_water_multi_year import (
    build_cloud_water_multi_year_business_metrics,
)
from cwr_engine.workflows.cloud_water_shared import (
    finalize_report_inputs,
    publish_directory,
)
from cwr_report.profiles.cloud_water_multi_year import (
    IMAGE_SLOTS,
    build_cloud_water_multi_year_report,
)
from cwr_report.profiles.cloud_water_shared import image_width_overrides


WORKFLOW_NAME = "cloud_water_multi_year"


@dataclass(frozen=True)
class CloudWaterMultiYearWorkflowSpec:
    task_id: str
    start_year: int
    end_year: int
    region_name: str
    product_source: dict[str, Any]
    region_spec: dict[str, Any]
    template: Path
    output_root: Path
    report_filename: str
    artifact_name: str
    image_width_inches: float
    image_widths_inches: dict[str, float]


def build_cloud_water_multi_year_workflow(spec_path: Path) -> Path:
    spec = load_cloud_water_multi_year_workflow_spec(spec_path)
    output_parent = spec.output_root.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{spec.output_root.name}-staging-",
        dir=output_parent,
    ) as raw_temp:
        temp = Path(raw_temp)
        staged_output = temp / "output"
        metrics_spec = temp / "business-metrics.json"
        profile_spec = temp / "report-profile.json"
        metrics_spec.write_text(
            json.dumps(
                {
                    "metric_profile": WORKFLOW_NAME,
                    "task_id": spec.task_id,
                    "start_year": spec.start_year,
                    "end_year": spec.end_year,
                    "region_name": spec.region_name,
                    "product_source": spec.product_source,
                    "region_spec": spec.region_spec,
                    "output_root": str(staged_output),
                    "artifact_name": spec.artifact_name,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        report_inputs = build_cloud_water_multi_year_business_metrics(
            metrics_spec
        )
        staged_report = staged_output / "report" / spec.report_filename
        profile_spec.write_text(
            json.dumps(
                {
                    "profile": WORKFLOW_NAME,
                    "report_inputs": str(report_inputs),
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
        build_cloud_water_multi_year_report(profile_spec)
        finalize_report_inputs(
            report_inputs,
            staged_output,
            spec.output_root,
            spec.report_filename,
            workflow_name=WORKFLOW_NAME,
        )
        publish_directory(staged_output, spec.output_root)
    return spec.output_root / "report" / spec.report_filename


def load_cloud_water_multi_year_workflow_spec(
    path: Path,
) -> CloudWaterMultiYearWorkflowSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version", 1) != 1:
        raise ValueError("schema_version must be 1")
    if payload.get("workflow") != WORKFLOW_NAME:
        raise ValueError(f"workflow must be {WORKFLOW_NAME}")
    start_year = _year(payload, "start_year")
    end_year = _year(payload, "end_year")
    if end_year < start_year:
        raise ValueError("end_year must not be earlier than start_year")
    if end_year - start_year + 1 < 5:
        raise ValueError("Multi-year report requires at least five years")
    base = path.parent
    output_root = resolve_path(base, payload, "output_root")
    if output_root.exists() and not output_root.is_dir():
        raise ValueError(f"output_root is not a directory: {output_root}")
    template = existing_file(base, payload, "template")
    report_filename = payload.get(
        "report_filename",
        f"{start_year}-{end_year}-cloud-water-report.docx",
    )
    if (
        not isinstance(report_filename, str)
        or not report_filename.strip()
        or Path(report_filename).name != report_filename
        or Path(report_filename).suffix.lower() != ".docx"
    ):
        raise ValueError("report_filename must be a .docx filename")
    if (output_root / "report" / report_filename).resolve() == template.resolve():
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
    width_overrides = image_width_overrides(
        payload.get("image_widths_inches", {}),
        IMAGE_SLOTS,
    )
    product_source = normalize_product_source(
        base,
        payload.get("product_source"),
        serialize_root=True,
    )
    return CloudWaterMultiYearWorkflowSpec(
        task_id=required_text(payload, "task_id"),
        start_year=start_year,
        end_year=end_year,
        region_name=required_text(payload, "region_name"),
        product_source=product_source,
        region_spec=normalize_region_spec(base, payload.get("region_spec")),
        template=template,
        output_root=output_root,
        report_filename=report_filename,
        artifact_name=artifact_name,
        image_width_inches=float(width),
        image_widths_inches=width_overrides,
    )


def _year(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value
