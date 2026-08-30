from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water_core import (
    CloudWaterYearResult,
    PreparedCloudWaterYear,
    derive_cloud_water_year_from_prepared,
    prepare_cloud_water_year,
)
from cwr_engine.business_metrics.cloud_water_multi_year import (
    PROFILE_NAME,
    CloudWaterMultiYearMetricsSpec,
    derive_cloud_water_multi_year_from_results,
    write_cloud_water_multi_year_business_metrics,
)
from cwr_engine.business_request import (
    BusinessRequest,
    compile_business_request,
    parse_business_request,
)
from cwr_engine.cache import build_mask_signature
from cwr_engine.data_sources.netcdf import PreparedNetcdfSource
from cwr_engine.models.region import MaskBundle
from cwr_engine.models.task import EngineTask
from cwr_engine.pipeline import run_engine_task_from_prepared
from cwr_engine.steps.mask import _derive_bounds
from cwr_engine.workflows.cloud_water_shared import (
    finalize_report_inputs,
    publish_directory,
    rebase_request_set_outputs,
    verify_request_set_manifest_paths,
    write_request_set_manifest,
)
from cwr_report.profiles.cloud_water_multi_year import (
    IMAGE_SLOTS,
    build_cloud_water_multi_year_report,
)
from cwr_report.profiles.cloud_water_shared import image_width_overrides


REQUEST_SET_SCHEMA_VERSION = 1
REQUEST_SET_NAME = "cloud_water_multi_year"


@dataclass(frozen=True)
class CloudWaterMultiYearRequestSet:
    request_set_id: str
    years: list[int]
    annual_request: BusinessRequest
    monthly_request: BusinessRequest
    product: dict[str, Any]
    output_root: Path


@dataclass(frozen=True)
class PreparedCloudWaterMultiYear:
    annual_prepared: PreparedNetcdfSource
    monthly_prepared: PreparedNetcdfSource
    yearly: list[PreparedCloudWaterYear]
    derived: list[CloudWaterYearResult]
    mask: xr.DataArray
    mask_bundle: MaskBundle
    product_source: dict[str, Any]
    region_spec: dict[str, Any]


def build_cloud_water_multi_year_request_set(spec_path: Path) -> Path:
    spec = load_multi_year_request_set(spec_path)
    output_parent = spec.output_root.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{spec.output_root.name}-staging-",
        dir=output_parent,
    ) as raw_temp:
        staging = Path(raw_temp) / "output"
        staged_output = staging / spec.output_root.name
        annual_task = compile_business_request(
            spec.annual_request,
            spec_path,
            output_root=staged_output / "standard_requests" / "annual",
        )
        monthly_task = compile_business_request(
            spec.monthly_request,
            spec_path,
            output_root=staged_output / "standard_requests" / "monthly",
        )
        prepared = _prepare_multi_year_inputs(
            annual_task,
            monthly_task,
            spec.years,
            spec_path.parent,
            staged_output,
        )

        _run_standard_request(
            annual_task,
            spec_path,
            prepared.annual_prepared.dataset,
            prepared.mask,
            prepared.mask_bundle,
            staged_output / "standard_requests" / "annual",
        )
        _run_standard_request(
            monthly_task,
            spec_path,
            prepared.monthly_prepared.dataset,
            prepared.mask,
            prepared.mask_bundle,
            staged_output / "standard_requests" / "monthly",
        )

        metrics_spec = CloudWaterMultiYearMetricsSpec(
            task_id=spec.request_set_id,
            start_year=spec.years[0],
            end_year=spec.years[-1],
            region_name=spec.product["region_name"],
            product_source=prepared.product_source,
            region_spec=prepared.region_spec,
            output_root=staged_output,
            artifact_name=PROFILE_NAME,
        )
        metrics, spatial = derive_cloud_water_multi_year_from_results(
            metrics_spec,
            prepared.derived,
        )
        request_set_manifest_path = (
            staged_output / "report_inputs" / "request_set_manifest.json"
        )
        report_inputs = write_cloud_water_multi_year_business_metrics(
            metrics_spec,
            metrics,
            spatial,
            request_set_id=spec.request_set_id,
            request_set_manifest=request_set_manifest_path,
        )
        write_request_set_manifest(
            path=request_set_manifest_path,
            request_set_id=spec.request_set_id,
            request_set=REQUEST_SET_NAME,
            members=[
                {
                    "role": "annual",
                    "request_id": spec.annual_request.request_id,
                    "manifest": str(
                        staged_output
                        / "standard_requests"
                        / "annual"
                        / "report_inputs"
                        / "request_manifest.json"
                    ),
                },
                {
                    "role": "monthly",
                    "request_id": spec.monthly_request.request_id,
                    "manifest": str(
                        staged_output
                        / "standard_requests"
                        / "monthly"
                        / "report_inputs"
                        / "request_manifest.json"
                    ),
                },
            ],
            product_report_inputs=report_inputs,
        )

        staged_report = staged_output / "report" / spec.product["report_filename"]
        profile_spec = staging / "report-profile.json"
        profile_spec.write_text(
            json.dumps(
                {
                    "profile": REQUEST_SET_NAME,
                    "report_inputs": str(report_inputs),
                    "template": str(spec.product["template"]),
                    "output": str(staged_report),
                    "image_width_inches": spec.product["image_width_inches"],
                    "image_widths_inches": spec.product["image_widths_inches"],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        build_cloud_water_multi_year_report(profile_spec)

        verify_request_set_manifest_paths(staged_output)
        rebase_request_set_outputs(staged_output, spec.output_root)
        finalize_report_inputs(
            report_inputs,
            staged_output,
            spec.output_root,
            spec.product["report_filename"],
            workflow_name=REQUEST_SET_NAME,
        )
        publish_directory(staged_output, spec.output_root)
    return spec.output_root / "report" / spec.product["report_filename"]


def load_multi_year_request_set(path: Path) -> CloudWaterMultiYearRequestSet:
    payload = json.loads(path.read_text(encoding="utf-8"))
    _validate_top_level(payload)
    shared = payload["shared_request"]
    if set(shared) != {"data_source", "region"}:
        raise ValueError("shared_request must contain exactly data_source and region")
    requests = payload["requests"]
    if not isinstance(requests, dict) or set(requests) != {"annual", "monthly"}:
        raise ValueError("requests must contain exactly annual and monthly")

    annual = parse_business_request(_merge_member(shared, requests["annual"]))
    monthly = parse_business_request(_merge_member(shared, requests["monthly"]))
    years = annual.period["years"] if annual.period.get("scale") == "year" else []
    if len(years) < 5 or years != list(range(years[0], years[-1] + 1)):
        raise ValueError("annual period must contain at least five continuous years")
    expected_months = [
        f"{year}-{month:02d}" for year in years for month in range(1, 13)
    ]
    if monthly.period.get("scale") != "month" or monthly.period.get("items") != expected_months:
        raise ValueError("monthly period must cover months 1..12 for every annual year")
    if annual.data_source != monthly.data_source or annual.region != monthly.region:
        raise ValueError("annual and monthly members must share data source and region")

    base = path.parent
    product = _resolve_product(payload["product"], base)
    output_root = _resolve_path(payload["output_root"], base, "output_root")
    return CloudWaterMultiYearRequestSet(
        request_set_id=_required_text(payload, "request_set_id", "request set"),
        years=years,
        annual_request=annual,
        monthly_request=monthly,
        product=product,
        output_root=output_root,
    )


def _validate_top_level(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise ValueError("Request set must be a JSON object")
    allowed = {
        "schema_version",
        "request_set",
        "request_set_id",
        "shared_request",
        "requests",
        "product",
        "output_root",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"Unsupported request set field: {unknown[0]}")
    if payload.get("schema_version") != REQUEST_SET_SCHEMA_VERSION:
        raise ValueError("schema_version must be 1")
    if payload.get("request_set") != REQUEST_SET_NAME:
        raise ValueError(f"request_set must be {REQUEST_SET_NAME}")
    for key in ("shared_request", "requests", "product"):
        if not isinstance(payload.get(key), dict):
            raise ValueError(f"{key} must be an object")
    _required_text(payload, "request_set_id", "request set")
    _required_text(payload, "output_root", "request set")


def _merge_member(shared: dict[str, Any], member: Any) -> dict[str, Any]:
    if not isinstance(member, dict):
        raise ValueError("request-set members must be objects")
    allowed = {"request_id", "period", "variables", "operators", "results"}
    unknown = sorted(set(member) - allowed)
    if unknown:
        raise ValueError(f"Unsupported request-set member field: {unknown[0]}")
    return {
        "schema_version": REQUEST_SET_SCHEMA_VERSION,
        **member,
        "data_source": shared["data_source"],
        "region": shared["region"],
    }


def _resolve_product(product: dict[str, Any], base: Path) -> dict[str, Any]:
    allowed = {
        "region_name",
        "template",
        "report_filename",
        "image_width_inches",
        "image_widths_inches",
    }
    unknown = sorted(set(product) - allowed)
    if unknown:
        raise ValueError(f"Unsupported product field: {unknown[0]}")
    region_name = _required_text(product, "region_name", "product")
    template = _resolve_path(
        _required_text(product, "template", "product"), base, "product.template"
    )
    if not template.is_file():
        raise ValueError(f"template does not exist: {template}")
    report_filename = _required_text(product, "report_filename", "product")
    if Path(report_filename).name != report_filename or Path(report_filename).suffix.lower() != ".docx":
        raise ValueError("report_filename must be a .docx filename")
    width = product.get("image_width_inches", 4.0)
    if not isinstance(width, (int, float)) or isinstance(width, bool) or width <= 0:
        raise ValueError("image_width_inches must be positive")
    overrides = image_width_overrides(
        product.get("image_widths_inches", {}), IMAGE_SLOTS
    )
    return {
        "region_name": region_name,
        "template": template,
        "report_filename": report_filename,
        "image_width_inches": float(width),
        "image_widths_inches": overrides,
    }


def _prepare_multi_year_inputs(
    annual_task: EngineTask,
    monthly_task: EngineTask,
    years: list[int],
    base: Path,
    staged_output: Path,
) -> PreparedCloudWaterMultiYear:
    product_source = _product_source(annual_task.data_source, base)
    region_spec = {
        "kind": annual_task.region_spec.kind,
        "payload": dict(annual_task.region_spec.payload),
    }
    yearly: list[PreparedCloudWaterYear] = []
    derived: list[CloudWaterYearResult] = []
    reference_grid: xr.Dataset | None = None
    mask: xr.DataArray | None = None
    for year in years:
        prepared = prepare_cloud_water_year(
            product_source,
            region_spec,
            year,
            reference_grid=reference_grid,
            mask=mask,
        )
        reference_grid = prepared.reference_grid
        mask = prepared.mask
        yearly.append(prepared)
        derived.append(derive_cloud_water_year_from_prepared(prepared))
    if mask is None:
        raise ValueError("Multi-year request produced no region mask")

    mask_bundle = _write_mask_bundle(mask, region_spec, staged_output)
    annual_files = [item.annual_path for item in yearly]
    monthly_files = [
        item.monthly_paths[month] for item in yearly for month in range(1, 13)
    ]
    annual_dataset = _concat_dated(
        [
            (item.annual_dataset, f"{item.year}-01-01")
            for item in yearly
        ]
    )
    monthly_dataset = _concat_dated(
        [
            (item.monthly_datasets[month], f"{item.year}-{month:02d}-01")
            for item in yearly
            for month in range(1, 13)
        ]
    )
    return PreparedCloudWaterMultiYear(
        annual_prepared=_prepared_source(annual_dataset, annual_files, "year"),
        monthly_prepared=_prepared_source(monthly_dataset, monthly_files, "month"),
        yearly=yearly,
        derived=derived,
        mask=mask,
        mask_bundle=mask_bundle,
        product_source=product_source,
        region_spec=region_spec,
    )


def _concat_dated(items: list[tuple[xr.Dataset, str]]) -> xr.Dataset:
    datasets = [
        dataset.expand_dims(time=np.array([date], dtype="datetime64[D]"))
        for dataset, date in items
    ]
    return xr.concat(
        datasets,
        dim="time",
        data_vars="all",
        coords="minimal",
        compat="override",
        join="exact",
    ).sortby("time")


def _prepared_source(
    dataset: xr.Dataset,
    files: list[Path],
    scale: str,
) -> PreparedNetcdfSource:
    return PreparedNetcdfSource(
        dataset=dataset,
        trace={
            "file_count": len(files),
            "first_file": str(files[0]),
            "last_file": str(files[-1]),
            "time_scale": scale,
        },
        files=files,
    )


def _write_mask_bundle(
    mask: xr.DataArray,
    region_spec: dict[str, Any],
    output_root: Path,
) -> MaskBundle:
    mask_dir = output_root / "mask"
    mask_dir.mkdir(parents=True, exist_ok=True)
    path = mask_dir / "mask_bundle.json"
    grid = {
        "lat": "lat",
        "lon": "lon",
        "shape": [int(mask.sizes["lat"]), int(mask.sizes["lon"])],
    }
    bundle = MaskBundle(
        mask_path=str(path),
        preview_path=str(mask_dir / "mask_preview.png"),
        grid_definition=grid,
        spatial_bounds=_derive_bounds(mask),
        signature=build_mask_signature(region_spec, grid),
    )
    path.write_text(
        json.dumps(
            {
                "mask_path": bundle.mask_path,
                "preview_path": bundle.preview_path,
                "grid_definition": bundle.grid_definition,
                "spatial_bounds": bundle.spatial_bounds,
                "signature": bundle.signature,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return bundle


def _run_standard_request(
    task: EngineTask,
    task_path: Path,
    dataset: xr.Dataset,
    mask: xr.DataArray,
    mask_bundle: MaskBundle,
    output_root: Path,
) -> Path:
    return run_engine_task_from_prepared(
        task=task,
        task_path=task_path,
        prepared_dataset=dataset,
        mask_data=mask,
        mask_bundle=mask_bundle,
        output_root=output_root,
    )


def _product_source(data_source: dict[str, Any], base: Path) -> dict[str, Any]:
    root = Path(data_source["root"])
    result: dict[str, Any] = {
        "root": root if root.is_absolute() else (base / root).resolve()
    }
    for key in ("engine", "coordinate_map", "variable_map"):
        if key in data_source:
            result[key] = data_source[key]
    return result


def _required_text(payload: dict[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def _resolve_path(value: str, base: Path, field: str) -> Path:
    path = Path(value)
    resolved = path if path.is_absolute() else (base / path).resolve()
    if field == "output_root" and resolved.exists() and not resolved.is_dir():
        raise ValueError(f"output_root is not a directory: {resolved}")
    return resolved
