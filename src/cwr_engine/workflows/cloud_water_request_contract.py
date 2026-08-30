from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from cwr_engine.cache import build_mask_signature
from cwr_engine.data_sources.netcdf import PreparedNetcdfSource
from cwr_engine.models.region import MaskBundle
from cwr_engine.models.task import EngineTask
from cwr_engine.pipeline import run_engine_task_from_prepared
from cwr_engine.steps.mask import _derive_bounds
from cwr_report.profiles.cloud_water_shared import image_width_overrides


REQUEST_SET_SCHEMA_VERSION = 1
REQUEST_SET_FIELDS = {
    "schema_version",
    "request_set",
    "request_set_id",
    "shared_request",
    "requests",
    "product",
    "output_root",
}
MEMBER_FIELDS = {"request_id", "period", "variables", "operators", "results"}
PRODUCT_FIELDS = {
    "region_name",
    "template",
    "report_filename",
    "image_width_inches",
    "image_widths_inches",
}
DATA_SOURCE_FIELDS = {
    "kind",
    "root",
    "engine",
    "coordinate_map",
    "variable_map",
}


def require_object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be an object")
    return value


def reject_unknown_fields(
    payload: dict[str, Any],
    allowed: set[str],
    context: str,
    *,
    message: str = "{field} is not a recognized field in {context}",
) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(message.format(field=unknown[0], context=context))


def required_text(payload: dict[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}.{key} must be a non-empty string")
    return value


def validate_request_set_header(payload: Any, request_set: str) -> dict[str, Any]:
    request_payload = require_object(payload, "Request set")
    reject_unknown_fields(
        request_payload,
        REQUEST_SET_FIELDS,
        "request set",
        message="Unsupported request set field: {field}",
    )
    if request_payload.get("schema_version") != REQUEST_SET_SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {REQUEST_SET_SCHEMA_VERSION}")
    if request_payload.get("request_set") != request_set:
        raise ValueError(f"request_set must be {request_set}")
    required_text(request_payload, "request_set_id", "request set")
    require_object(request_payload.get("shared_request"), "shared_request")
    require_object(request_payload.get("requests"), "requests")
    require_object(request_payload.get("product"), "product")
    required_text(request_payload, "output_root", "request set")
    return request_payload


def validate_shared_request(shared: Any) -> dict[str, Any]:
    shared_payload = require_object(shared, "shared_request")
    reject_unknown_fields(shared_payload, {"data_source", "region"}, "shared_request")
    if "data_source" not in shared_payload or "region" not in shared_payload:
        raise ValueError("shared_request must contain data_source and region")

    data_source = require_object(
        shared_payload["data_source"], "shared_request.data_source"
    )
    reject_unknown_fields(
        data_source, DATA_SOURCE_FIELDS, "shared_request.data_source"
    )
    region = require_object(shared_payload["region"], "shared_request.region")
    if "kind" not in region:
        raise ValueError("shared_request.region must contain 'kind'")
    if region["kind"] not in {"shp", "existing_mask", "bbox"}:
        raise ValueError(f"Unsupported region kind: {region['kind']}")
    return shared_payload


def validate_request_members(
    requests: Any,
    *,
    unknown_message: str = "{field} is not a recognized field in {context}",
) -> dict[str, dict[str, Any]]:
    request_members = require_object(requests, "requests")
    if set(request_members) != {"annual", "monthly"}:
        raise ValueError("requests must contain exactly annual and monthly")
    for role in ("annual", "monthly"):
        member = require_object(request_members[role], f"requests.{role}")
        reject_unknown_fields(
            member,
            MEMBER_FIELDS,
            f"requests.{role}",
            message=unknown_message,
        )
    return request_members


def merge_request_member(
    shared: dict[str, Any], member: dict[str, Any]
) -> dict[str, Any]:
    return {
        "schema_version": REQUEST_SET_SCHEMA_VERSION,
        **member,
        "data_source": shared["data_source"],
        "region": shared["region"],
    }


def resolve_request_product(
    product: Any,
    base: Path,
    image_slots: list[str],
) -> dict[str, Any]:
    product_payload = require_object(product, "product")
    reject_unknown_fields(product_payload, PRODUCT_FIELDS, "product")
    required = {"region_name", "template", "report_filename"}
    missing = sorted(required - set(product_payload))
    if missing:
        raise ValueError(f"product missing {missing[0]}")

    region_name = required_text(product_payload, "region_name", "product")
    template = resolve_path(
        required_text(product_payload, "template", "product"),
        base,
        "product.template",
    )
    if not template.is_file():
        raise ValueError(f"template does not exist: {template}")
    report_filename = required_text(product_payload, "report_filename", "product")
    if (
        Path(report_filename).name != report_filename
        or Path(report_filename).suffix.lower() != ".docx"
    ):
        raise ValueError("report_filename must be a .docx filename")
    width = product_payload.get("image_width_inches", 4.0)
    if not isinstance(width, (int, float)) or isinstance(width, bool) or width <= 0:
        raise ValueError("image_width_inches must be positive")
    overrides = image_width_overrides(
        product_payload.get("image_widths_inches", {}), image_slots
    )
    return {
        "region_name": region_name,
        "template": template,
        "report_filename": report_filename,
        "image_width_inches": float(width),
        "image_widths_inches": overrides,
    }


def resolve_path(value: str, base: Path, field: str) -> Path:
    path = Path(value)
    resolved = path if path.is_absolute() else (base / path).resolve()
    if field == "output_root" and resolved.exists() and not resolved.is_dir():
        raise ValueError(f"output_root is not a directory: {resolved}")
    return resolved


def product_source_from_data_source(
    data_source: dict[str, Any], base: Path
) -> dict[str, Any]:
    root = Path(data_source["root"])
    result: dict[str, Any] = {
        "root": root if root.is_absolute() else (base / root).resolve()
    }
    for key in ("engine", "coordinate_map", "variable_map"):
        if key in data_source:
            result[key] = data_source[key]
    return result


def region_spec_from_task(task: EngineTask) -> dict[str, Any]:
    return {
        "kind": task.region_spec.kind,
        "payload": dict(task.region_spec.payload),
    }


def concat_dated(items: list[tuple[xr.Dataset, str]]) -> xr.Dataset:
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


def prepared_source(
    dataset: xr.Dataset, files: list[Path], scale: str
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


def write_mask_bundle(
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


def run_standard_request(
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
