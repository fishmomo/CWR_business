from __future__ import annotations

from dataclasses import dataclass
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
from cwr_engine.data_sources.netcdf import PreparedNetcdfSource
from cwr_engine.models.region import MaskBundle
from cwr_engine.models.task import EngineTask
from cwr_engine.workflows.cloud_water_request_contract import (
    REQUEST_SET_SCHEMA_VERSION,
    merge_request_member,
    prepared_source,
    product_source_from_data_source,
    region_spec_from_task,
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
from cwr_report.profiles.cloud_water_single_year import (
    IMAGE_SLOTS,
    build_cloud_water_single_year_report,
)
from cwr_report.profiles.cloud_water_shared import image_width_overrides


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

        annual_manifest = run_standard_request(
            annual_engine_task,
            spec_path,
            prepared.annual_prepared.dataset,
            prepared.mask,
            prepared.mask_bundle,
            staged_output_root / "standard_requests" / "annual",
        )
        monthly_manifest = run_standard_request(
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
    validate_request_set_header(payload, REQUEST_SET_NAME)
    shared = validate_shared_request(payload["shared_request"])
    requests = validate_request_members(payload["requests"])
    year = _validate_annual_period(requests["annual"])
    _validate_monthly_period(requests["monthly"], year)
    product = resolve_request_product(payload["product"], base, IMAGE_SLOTS)

    annual_payload = merge_request_member(shared, requests["annual"])
    monthly_payload = merge_request_member(shared, requests["monthly"])

    annual_request = parse_business_request(annual_payload)
    monthly_request = parse_business_request(monthly_payload)

    output_root = resolve_path(payload["output_root"], base, "output_root")

    return CloudWaterSingleYearRequestSet(
        request_set_id=payload["request_set_id"],
        year=year,
        shared_request=shared,
        annual_request=annual_request,
        monthly_request=monthly_request,
        product=product,
        output_root=output_root,
    )

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
    product_source = product_source_from_data_source(annual_task.data_source, base)
    region_spec = region_spec_from_task(annual_task)

    cloud_water_prepared = prepare_cloud_water_year(
        product_source, region_spec, year
    )
    annual_dataset = cloud_water_prepared.annual_dataset
    monthly_dataset = _combine_monthly_datasets(
        cloud_water_prepared.monthly_datasets, year
    )

    mask = cloud_water_prepared.mask
    mask_bundle = write_mask_bundle(mask, region_spec, staged_output_root)

    annual_prepared = prepared_source(
        _annual_with_time(annual_dataset, year),
        [cloud_water_prepared.annual_path],
        "year",
    )
    monthly_prepared = prepared_source(
        monthly_dataset,
        [cloud_water_prepared.monthly_paths[m] for m in range(1, 13)],
        "month",
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
