from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water import (
    PROFILE_NAME,
    CloudWaterMetricsSpec,
    build_cloud_water_metrics,
    write_cloud_water_business_metrics,
)
from cwr_engine.business_metrics.cloud_water_config import (
    existing_file,
    required_text,
    resolve_path,
)
from cwr_engine.business_metrics.cloud_water_core import (
    CloudWaterYearResult,
    PreparedCloudWaterYear,
    derive_cloud_water_year_from_prepared,
    prepare_cloud_water_year,
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
from cwr_engine.registries.variables import build_variable_registry
from cwr_engine.steps.mask import _derive_bounds, compile_shp_mask
from cwr_engine.workflows.cloud_water_shared import (
    finalize_report_inputs,
    publish_directory,
    rebase_request_set_outputs,
    verify_request_set_manifest_paths,
    write_request_set_manifest,
)
from cwr_report.profiles.cloud_water_single_year import (
    IMAGE_SLOTS,
    build_cloud_water_single_year_report,
)
from cwr_report.profiles.cloud_water_shared import image_width_overrides


REQUEST_SET_SCHEMA_VERSION = 1
REQUEST_SET_NAME = "cloud_water_single_year"


@dataclass(frozen=True)
class CloudWaterSingleYearRequestSet:
    request_set_id: str
    year: int
    shared_request: dict[str, Any]
    annual_request: BusinessRequest
    monthly_request: BusinessRequest
    product: dict[str, Any]
    output_root: Path


def build_cloud_water_single_year_request_set(spec_path: Path) -> Path:
    spec = load_request_set(spec_path)
    base = spec_path.parent

    output_parent = spec.output_root.parent
    output_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{spec.output_root.name}-staging-",
        dir=output_parent,
    ) as raw_temp:
        staging = Path(raw_temp) / "output"
        staged_output_root = staging / spec.output_root.name

        annual_engine_task = compile_business_request(
            spec.annual_request,
            spec_path,
            output_root=staged_output_root / "standard_requests" / "annual",
        )
        monthly_engine_task = compile_business_request(
            spec.monthly_request,
            spec_path,
            output_root=staged_output_root / "standard_requests" / "monthly",
        )

        prepared = _prepare_cloud_water_year_inputs(
            annual_engine_task,
            monthly_engine_task,
            spec.year,
            base,
            staged_output_root,
        )

        annual_manifest = _run_standard_request(
            annual_engine_task,
            spec_path,
            prepared.annual_prepared.dataset,
            prepared.mask,
            prepared.mask_bundle,
            staged_output_root / "standard_requests" / "annual",
        )
        monthly_manifest = _run_standard_request(
            monthly_engine_task,
            spec_path,
            prepared.monthly_prepared.dataset,
            prepared.mask,
            prepared.mask_bundle,
            staged_output_root / "standard_requests" / "monthly",
        )

        cloud_water_result = derive_cloud_water_year_from_prepared(
            prepared.to_cloud_water_prepared()
        )

        metrics_spec = CloudWaterMetricsSpec(
            task_id=spec.request_set_id,
            year=spec.year,
            region_name=spec.product["region_name"],
            product_source=prepared.product_source,
            region_spec=prepared.region_spec,
            output_root=staged_output_root,
            artifact_name=REQUEST_SET_NAME,
        )
        metrics, spatial = build_cloud_water_metrics(metrics_spec, cloud_water_result)
        report_inputs_path = write_cloud_water_business_metrics(
            metrics_spec,
            metrics,
            spatial,
            request_set_id=spec.request_set_id,
            request_set_manifest=(
                staged_output_root / "report_inputs" / "request_set_manifest.json"
            ),
        )

        request_set_manifest_path = staged_output_root / "report_inputs" / "request_set_manifest.json"
        write_request_set_manifest(
            path=request_set_manifest_path,
            request_set_id=spec.request_set_id,
            request_set=REQUEST_SET_NAME,
            members=[
                {
                    "role": "annual",
                    "request_id": spec.annual_request.request_id,
                    "manifest": str(staged_output_root / "standard_requests" / "annual" / "report_inputs" / "request_manifest.json"),
                },
                {
                    "role": "monthly",
                    "request_id": spec.monthly_request.request_id,
                    "manifest": str(staged_output_root / "standard_requests" / "monthly" / "report_inputs" / "request_manifest.json"),
                },
            ],
            product_report_inputs=report_inputs_path,
        )

        staged_report = staged_output_root / "report" / spec.product["report_filename"]
        profile_spec_path = staging / "report-profile.json"
        profile_spec_path.write_text(
            json.dumps(
                {
                    "profile": REQUEST_SET_NAME,
                    "report_inputs": str(report_inputs_path),
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
        build_cloud_water_single_year_report(profile_spec_path)

        verify_request_set_manifest_paths(staged_output_root)
        rebase_request_set_outputs(
            staged_output_root,
            spec.output_root,
        )
        finalize_report_inputs(
            report_inputs_path,
            staged_output_root,
            spec.output_root,
            spec.product["report_filename"],
            workflow_name=REQUEST_SET_NAME,
        )
        publish_directory(staged_output_root, spec.output_root)

    return spec.output_root / "report" / spec.product["report_filename"]


def load_request_set(path: Path) -> CloudWaterSingleYearRequestSet:
    payload = json.loads(path.read_text(encoding="utf-8"))
    base = path.parent
    _validate_request_set_payload(payload, base)

    shared = payload["shared_request"]
    product = _resolve_product(payload["product"], base)

    annual_payload = _merge_member(shared, payload["requests"]["annual"], "annual")
    monthly_payload = _merge_member(shared, payload["requests"]["monthly"], "monthly")

    annual_request = parse_business_request(annual_payload)
    monthly_request = parse_business_request(monthly_payload)

    output_root = resolve_path(base, payload, "output_root")

    year = annual_request.period["years"][0]

    return CloudWaterSingleYearRequestSet(
        request_set_id=payload["request_set_id"],
        year=year,
        shared_request=shared,
        annual_request=annual_request,
        monthly_request=monthly_request,
        product=product,
        output_root=output_root,
    )


def _validate_request_set_payload(payload: dict[str, Any], base: Path) -> None:
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
        raise ValueError(f"schema_version must be {REQUEST_SET_SCHEMA_VERSION}")
    if payload.get("request_set") != REQUEST_SET_NAME:
        raise ValueError(f"request_set must be {REQUEST_SET_NAME}")

    request_set_id = payload.get("request_set_id")
    if (
        not isinstance(request_set_id, str)
        or not request_set_id.strip()
    ):
        raise ValueError("request_set_id must be a non-empty string")

    shared = payload.get("shared_request")
    if not isinstance(shared, dict):
        raise ValueError("shared_request must be an object")
    _validate_known_fields(shared, {"data_source", "region"}, "shared_request")
    if "data_source" not in shared or "region" not in shared:
        raise ValueError("shared_request must contain data_source and region")

    _validate_data_source(shared["data_source"])
    _validate_region(shared["region"])

    requests = payload.get("requests")
    if not isinstance(requests, dict):
        raise ValueError("requests must be an object")
    if set(requests) != {"annual", "monthly"}:
        raise ValueError("requests must contain exactly annual and monthly")

    _validate_member(requests["annual"], "annual")
    _validate_member(requests["monthly"], "monthly")

    year = _validate_annual_period(requests["annual"])
    _validate_monthly_period(requests["monthly"], year)

    product = payload.get("product")
    if not isinstance(product, dict):
        raise ValueError("product must be an object")
    _validate_known_fields(
        product,
        {"region_name", "template", "report_filename", "image_width_inches", "image_widths_inches"},
        "product",
    )
    _validate_product(product, base)


def _validate_annual_period(member: dict[str, Any]) -> int:
    period = member.get("period")
    if (
        not isinstance(period, dict)
        or period.get("scale") != "year"
    ):
        raise ValueError("annual.period must be {'scale': 'year', 'years': [year]}")
    years = period.get("years")
    if (
        not isinstance(years, list)
        or len(years) != 1
        or not isinstance(years[0], int)
        or isinstance(years[0], bool)
    ):
        raise ValueError("annual.period.years must contain exactly one integer year")
    return years[0]


def _validate_monthly_period(member: dict[str, Any], year: int) -> None:
    period = member.get("period")
    if (
        not isinstance(period, dict)
        or period.get("scale") != "month"
        or period.get("years") != [year]
        or period.get("months") != list(range(1, 13))
    ):
        raise ValueError(
            "monthly.period must include exactly year and months 1..12"
        )


def _resolve_product(product: dict[str, Any], base: Path) -> dict[str, Any]:
    """Resolve and normalize product fields. Returns a new dict with resolved paths/defaults."""
    required = {"region_name", "template", "report_filename"}
    missing = sorted(required - set(product))
    if missing:
        raise ValueError(f"product missing {missing[0]}")

    template = Path(product["template"])
    template = template if template.is_absolute() else (base / template).resolve()
    if not template.is_file():
        raise ValueError(f"template does not exist: {template}")

    report_filename = product["report_filename"]
    if (
        not isinstance(report_filename, str)
        or not report_filename.strip()
        or Path(report_filename).name != report_filename
        or Path(report_filename).suffix.lower() != ".docx"
    ):
        raise ValueError("report_filename must be a .docx filename")

    width = product.get("image_width_inches", 4.0)
    if (
        not isinstance(width, (int, float))
        or isinstance(width, bool)
        or width <= 0
    ):
        raise ValueError("image_width_inches must be positive")

    image_widths_inches = product.get("image_widths_inches", {})
    if not isinstance(image_widths_inches, dict):
        raise ValueError("image_widths_inches must be an object")
    for key, value in image_widths_inches.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"image_widths_inches.{key} must be positive")

    # Build a normalized copy with resolved template path and default widths
    resolved = dict(product)
    resolved["template"] = str(template)
    resolved.setdefault("image_width_inches", 4.0)
    resolved.setdefault("image_widths_inches", {})
    return resolved


def _validate_product(product: dict[str, Any], base: Path) -> None:
    # _resolve_product performs all validation; result is discarded here
    _resolve_product(product, base)


def _validate_known_fields(payload: dict[str, Any], allowed: set[str], context: str) -> None:
    """Reject unknown fields in a nested object."""
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"{unknown[0]} is not a recognized field in {context}")


def _validate_data_source(data_source: dict[str, Any]) -> None:
    if not isinstance(data_source, dict):
        raise ValueError("shared_request.data_source must be an object")
    _validate_known_fields(
        data_source,
        {"kind", "root", "engine", "coordinate_map", "variable_map"},
        "shared_request.data_source",
    )


def _validate_region(region: dict[str, Any]) -> None:
    if not isinstance(region, dict):
        raise ValueError("shared_request.region must be an object")
    if "kind" not in region:
        raise ValueError("shared_request.region must contain 'kind'")
    kind = region["kind"]
    if kind not in {"shp", "existing_mask", "bbox"}:
        raise ValueError(f"Unsupported region kind: {kind}")


def _validate_member(member: dict[str, Any], role: str) -> None:
    if not isinstance(member, dict):
        raise ValueError(f"requests.{role} must be an object")
    _validate_known_fields(
        member,
        {"request_id", "period", "variables", "operators", "results"},
        f"requests.{role}",
    )


def _merge_member(
    shared: dict[str, Any],
    member: dict[str, Any],
    role: str,
) -> dict[str, Any]:
    merged = {
        "schema_version": REQUEST_SET_SCHEMA_VERSION,
        "request_id": member["request_id"],
        "data_source": shared["data_source"],
        "region": shared["region"],
        "period": member["period"],
        "variables": member["variables"],
        "operators": member["operators"],
        "results": member["results"],
    }
    if role == "monthly":
        merged["request_id"] = member["request_id"]
    return merged


@dataclass(frozen=True)
class _PreparedInputs:
    annual_prepared: PreparedNetcdfSource
    monthly_prepared: PreparedNetcdfSource
    cloud_water_prepared: PreparedCloudWaterYear
    mask: xr.DataArray
    mask_bundle: MaskBundle
    product_source: dict[str, Any]
    region_spec: dict[str, Any]

    def to_cloud_water_prepared(self) -> PreparedCloudWaterYear:
        return self.cloud_water_prepared


def _prepare_cloud_water_year_inputs(
    annual_task: EngineTask,
    monthly_task: EngineTask,
    year: int,
    base: Path,
    staged_output_root: Path,
) -> _PreparedInputs:
    product_source = _data_source_to_product_source(annual_task.data_source, base)
    region_spec = _region_spec_to_cloud_water_format(annual_task.region_spec)

    cloud_water_prepared = prepare_cloud_water_year(
        product_source, region_spec, year
    )
    annual_dataset = cloud_water_prepared.annual_dataset
    monthly_dataset = _combine_monthly_datasets(
        cloud_water_prepared.monthly_datasets, year
    )

    lat_values = annual_dataset["lat"].values
    lon_values = annual_dataset["lon"].values
    mask = cloud_water_prepared.mask

    grid_definition = {
        "lat": "lat",
        "lon": "lon",
        "shape": [int(mask.sizes["lat"]), int(mask.sizes["lon"])],
    }
    spatial_bounds = _derive_bounds(mask)
    signature = build_mask_signature(
        {"kind": region_spec["kind"], "payload": region_spec["payload"]},
        grid_definition,
    )

    mask_dir = staged_output_root / "mask"
    mask_dir.mkdir(parents=True, exist_ok=True)
    mask_bundle_path = mask_dir / "mask_bundle.json"
    mask_bundle = MaskBundle(
        mask_path=str(mask_bundle_path),
        preview_path=str(mask_dir / "mask_preview.png"),
        grid_definition=grid_definition,
        spatial_bounds=spatial_bounds,
        signature=signature,
    )
    mask_bundle_path.write_text(
        json.dumps(
            {
                "mask_path": mask_bundle.mask_path,
                "preview_path": mask_bundle.preview_path,
                "grid_definition": mask_bundle.grid_definition,
                "spatial_bounds": mask_bundle.spatial_bounds,
                "signature": mask_bundle.signature,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    annual_prepared = PreparedNetcdfSource(
        dataset=_annual_with_time(annual_dataset, year),
        trace={
            "file_count": 1,
            "first_file": str(cloud_water_prepared.annual_path),
            "last_file": str(cloud_water_prepared.annual_path),
            "time_scale": "year",
        },
        files=[cloud_water_prepared.annual_path],
    )
    monthly_prepared = PreparedNetcdfSource(
        dataset=monthly_dataset,
        trace={
            "file_count": 12,
            "first_file": str(cloud_water_prepared.monthly_paths[1]),
            "last_file": str(cloud_water_prepared.monthly_paths[12]),
            "time_scale": "month",
        },
        files=[cloud_water_prepared.monthly_paths[m] for m in range(1, 13)],
    )

    return _PreparedInputs(
        annual_prepared=annual_prepared,
        monthly_prepared=monthly_prepared,
        cloud_water_prepared=cloud_water_prepared,
        mask=mask,
        mask_bundle=mask_bundle,
        product_source=product_source,
        region_spec=region_spec,
    )


def _combine_monthly_datasets(
    monthly_datasets: dict[int, xr.Dataset],
    year: int,
) -> xr.Dataset:
    ordered = [monthly_datasets[month] for month in range(1, 13)]
    if len(ordered) == 1:
        return ordered[0]
    combined = xr.concat(
        ordered,
        dim="time",
        data_vars="all",
        coords="minimal",
        compat="override",
        join="exact",
    )
    dates = np.array([f"{year}-{month:02d}-01" for month in range(1, 13)], dtype="datetime64")
    combined = combined.assign_coords(time=dates)
    return combined.sortby("time")


def _annual_with_time(annual_dataset: xr.Dataset, year: int) -> xr.Dataset:
    dataset = annual_dataset.expand_dims("time")
    dates = np.array([f"{year}-01-01"], dtype="datetime64")
    return dataset.assign_coords(time=dates)


def _data_source_to_product_source(
    data_source: dict[str, Any],
    base: Path,
) -> dict[str, Any]:
    root = Path(data_source["root"])
    product_source = {
        "root": root if root.is_absolute() else (base / root).resolve(),
    }
    # Note: 'pattern' is intentionally excluded — product discovery uses
    # hardcoded annual_pattern/monthly_pattern and ignores this field.
    for key in ("engine", "coordinate_map", "variable_map"):
        if key in data_source:
            product_source[key] = data_source[key]
    return product_source


def _region_spec_to_cloud_water_format(region_spec) -> dict[str, Any]:
    payload = dict(region_spec.payload)
    return {"kind": region_spec.kind, "payload": payload}


def _run_standard_request(
    task: EngineTask,
    task_path: Path,
    prepared_dataset: xr.Dataset,
    mask: xr.DataArray,
    mask_bundle: MaskBundle,
    output_root: Path,
) -> Path:
    return run_engine_task_from_prepared(
        task=task,
        task_path=task_path,
        prepared_dataset=prepared_dataset,
        mask_data=mask,
        mask_bundle=mask_bundle,
        output_root=output_root,
    )
