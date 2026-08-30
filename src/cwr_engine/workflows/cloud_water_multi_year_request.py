from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import tempfile
from typing import Any

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
from cwr_engine.data_sources.netcdf import PreparedNetcdfSource
from cwr_engine.models.region import MaskBundle
from cwr_engine.models.task import EngineTask
from cwr_engine.workflows.cloud_water_request_contract import (
    REQUEST_SET_SCHEMA_VERSION,
    concat_dated,
    merge_request_member,
    prepared_source,
    product_source_from_data_source,
    region_spec_from_task,
    required_text,
    resolve_path,
    resolve_request_product,
    run_standard_request,
    validate_request_members,
    validate_request_set_header,
    validate_shared_request,
    write_mask_bundle,
)
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

        run_standard_request(
            annual_task,
            spec_path,
            prepared.annual_prepared.dataset,
            prepared.mask,
            prepared.mask_bundle,
            staged_output / "standard_requests" / "annual",
        )
        run_standard_request(
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
    validate_request_set_header(payload, REQUEST_SET_NAME)
    shared = validate_shared_request(payload["shared_request"])
    requests = validate_request_members(
        payload["requests"],
        unknown_message="Unsupported request-set member field: {field}",
    )

    annual = parse_business_request(merge_request_member(shared, requests["annual"]))
    monthly = parse_business_request(merge_request_member(shared, requests["monthly"]))
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
    product = resolve_request_product(payload["product"], base, IMAGE_SLOTS)
    output_root = resolve_path(payload["output_root"], base, "output_root")
    return CloudWaterMultiYearRequestSet(
        request_set_id=required_text(payload, "request_set_id", "request set"),
        years=years,
        annual_request=annual,
        monthly_request=monthly,
        product=product,
        output_root=output_root,
    )



def _prepare_multi_year_inputs(
    annual_task: EngineTask,
    monthly_task: EngineTask,
    years: list[int],
    base: Path,
    staged_output: Path,
) -> PreparedCloudWaterMultiYear:
    product_source = product_source_from_data_source(annual_task.data_source, base)
    region_spec = region_spec_from_task(annual_task)
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

    mask_bundle = write_mask_bundle(mask, region_spec, staged_output)
    annual_files = [item.annual_path for item in yearly]
    monthly_files = [
        item.monthly_paths[month] for item in yearly for month in range(1, 13)
    ]
    annual_dataset = concat_dated(
        [
            (item.annual_dataset, f"{item.year}-01-01")
            for item in yearly
        ]
    )
    monthly_dataset = concat_dated(
        [
            (item.monthly_datasets[month], f"{item.year}-{month:02d}-01")
            for item in yearly
            for month in range(1, 13)
        ]
    )
    return PreparedCloudWaterMultiYear(
        annual_prepared=prepared_source(annual_dataset, annual_files, "year"),
        monthly_prepared=prepared_source(monthly_dataset, monthly_files, "month"),
        yearly=yearly,
        derived=derived,
        mask=mask,
        mask_bundle=mask_bundle,
        product_source=product_source,
        region_spec=region_spec,
    )
