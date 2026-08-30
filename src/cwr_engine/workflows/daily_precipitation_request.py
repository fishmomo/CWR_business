from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path
import re
import tempfile
from typing import Any

from cwr_engine.business_request import (
    BusinessRequest,
    compile_business_request,
    parse_business_request,
)
from cwr_engine.data_sources.netcdf import ensure_hdf5_backend
from cwr_engine.pipeline import prepare_engine_task_inputs
from cwr_engine.precipitation_product import (
    derive_daily_precipitation_product,
    write_daily_precipitation_product,
)
from cwr_engine.workflows.cloud_water_request_contract import (
    merge_request_member,
    reject_unknown_fields,
    required_text,
    resolve_path,
    run_standard_request,
    validate_named_request_members,
    validate_request_set_header,
    validate_shared_request,
)
from cwr_engine.workflows.cloud_water_shared import (
    publish_directory,
    rebase_json_file,
    verify_request_set_manifest_paths,
    write_request_set_manifest,
)


REQUEST_SET_NAME = "daily_precipitation_analysis"
SAFE_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


@dataclass(frozen=True)
class DailyPrecipitationRequestSet:
    request_set_id: str
    daily_request: BusinessRequest
    dates: list[str]
    product: dict[str, str]
    output_root: Path


def load_daily_precipitation_request_set(path: Path) -> DailyPrecipitationRequestSet:
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_request_set_header(payload, REQUEST_SET_NAME)
    shared = validate_shared_request(payload["shared_request"])
    members = validate_named_request_members(payload["requests"], ("daily",))
    daily_request = parse_business_request(
        merge_request_member(shared, members["daily"])
    )
    dates = _validate_daily_request(daily_request)
    product = _resolve_product(payload["product"])
    return DailyPrecipitationRequestSet(
        request_set_id=required_text(payload, "request_set_id", "request set"),
        daily_request=daily_request,
        dates=dates,
        product=product,
        output_root=resolve_path(payload["output_root"], path.parent, "output_root"),
    )


def build_daily_precipitation_request_set(spec_path: Path) -> Path:
    spec = load_daily_precipitation_request_set(spec_path)
    ensure_hdf5_backend()
    spec.output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{spec.output_root.name}-staging-",
        dir=spec.output_root.parent,
    ) as raw_temp:
        staging = Path(raw_temp) / "output"
        staged_output = staging / spec.output_root.name
        standard_output = staged_output / "standard_request"
        task = compile_business_request(
            spec.daily_request,
            spec_path,
            output_root=standard_output,
        )
        prepared = prepare_engine_task_inputs(
            task,
            spec_path,
            staged_output,
            additional_source_variables=["dxy"],
        )
        standard_manifest = run_standard_request(
            task,
            spec_path,
            prepared.source.dataset,
            prepared.mask_data,
            prepared.mask_bundle,
            standard_output,
        )
        product = derive_daily_precipitation_product(
            prepared.source.dataset,
            prepared.mask_data,
        )
        artifacts = write_daily_precipitation_product(
            product,
            staged_output,
            spec.product["output_prefix"],
        )
        report_inputs = _write_report_inputs(
            staged_output,
            spec,
            artifacts,
            prepared.source.trace,
        )
        request_set_manifest = (
            staged_output / "report_inputs" / "request_set_manifest.json"
        )
        write_request_set_manifest(
            path=request_set_manifest,
            request_set_id=spec.request_set_id,
            request_set=REQUEST_SET_NAME,
            members=[
                {
                    "role": "daily",
                    "request_id": spec.daily_request.request_id,
                    "manifest": str(standard_manifest),
                }
            ],
            product_report_inputs=report_inputs,
        )
        verify_request_set_manifest_paths(staged_output)
        for path in (
            staged_output / "mask" / "mask_bundle.json",
            standard_manifest,
            report_inputs,
            request_set_manifest,
        ):
            rebase_json_file(path, staged_output, spec.output_root)
        _verify_no_staging_paths(staged_output)
        publish_directory(staged_output, spec.output_root)
    return spec.output_root / "report_inputs" / "report_inputs.json"


def _validate_daily_request(request: BusinessRequest) -> list[str]:
    if request.period.get("scale") != "day":
        raise ValueError("daily.period.scale must be day")
    dates = request.period.get("dates", [])
    parsed = [date.fromisoformat(value) for value in dates]
    if not parsed or len({item.year for item in parsed}) != 1:
        raise ValueError("daily period must contain dates from exactly one year")
    expected = []
    current = parsed[0]
    while current <= parsed[-1]:
        expected.append(current)
        current += timedelta(days=1)
    if parsed != expected:
        raise ValueError("daily period must be continuous without gaps")
    if request.variables != ["Ps", "GMh", "CWR"]:
        raise ValueError("daily variables must be exactly Ps, GMh and CWR")
    if request.operators != ["sum"]:
        raise ValueError("daily operators must be exactly sum")
    expected_results = [
        ("region_table", "daily_regional"),
        ("grid_nc", "daily_grids"),
    ]
    actual_results = [
        (item["engine_kind"], item["name"]) for item in request.results
    ]
    if actual_results != expected_results:
        raise ValueError(
            "daily results must be daily_regional CSV and daily_grids NetCDF"
        )
    return [item.isoformat() for item in parsed]


def _resolve_product(payload: Any) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError("product must be an object")
    reject_unknown_fields(payload, {"region_name", "output_prefix"}, "product")
    region_name = required_text(payload, "region_name", "product")
    output_prefix = required_text(payload, "output_prefix", "product")
    if not SAFE_PREFIX.fullmatch(output_prefix):
        raise ValueError(
            "product.output_prefix must contain only letters, numbers, '.', '_' or '-'"
        )
    return {"region_name": region_name, "output_prefix": output_prefix}


def _write_report_inputs(
    output_root: Path,
    spec: DailyPrecipitationRequestSet,
    artifacts: list[dict[str, str]],
    source_trace: dict[str, Any],
) -> Path:
    path = output_root / "report_inputs" / "report_inputs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    request_set_manifest = path.parent / "request_set_manifest.json"
    payload = {
        "schema_version": 1,
        "task": {"task_id": spec.request_set_id, "status": "success"},
        "inputs": {
            "request_set_id": spec.request_set_id,
            "request_set": REQUEST_SET_NAME,
            "region_name": spec.product["region_name"],
            "dates": spec.dates,
            "request_set_manifest": str(request_set_manifest),
        },
        "artifacts": artifacts,
        "runtime": {
            "source_trace": source_trace,
            "sample_days": len(spec.dates),
        },
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


def _verify_no_staging_paths(output_root: Path) -> None:
    for path in output_root.rglob("*.json"):
        text = path.read_text(encoding="utf-8")
        if "-staging-" in text:
            raise ValueError(f"Staging path leaked into formal JSON: {path}")
