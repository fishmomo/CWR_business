from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import xarray as xr


PROFILE_NAME = "cloud_water_single_year"
SEASON_MONTHS = {
    "spring": [3, 4, 5],
    "summer": [6, 7, 8],
    "autumn": [9, 10, 11],
    "winter": [12, 1, 2],
}
BOUNDARY_SIDES = {
    "west": "W",
    "east": "E",
    "south": "S",
    "north": "N",
}
ANNUAL_VARIABLES = [
    "GMv",
    "GMh",
    "SP",
    "CWR",
    "PEh",
    "PEv",
    "PEw",
    "RCv",
    "RCh",
    "dxy",
]
BOUNDARY_COMPONENTS = {
    "water_vapor": ("INv", "OTv"),
    "hydrometeor": ("INh", "OTh"),
}
SPATIAL_VARIABLES = [
    "pic3_a",
    "pic3_b",
    "pic3_c",
    "pic3_e",
    "pic3_f",
    "pic4_a",
    "pic4_b",
    "pic4_c",
    "pic4_d",
    "pic5_a",
    "pic5_b",
    "pic5_c",
    "pic5_d",
]
ANNUAL_COLUMNS = {
    "time",
    *ANNUAL_VARIABLES,
    *{
        f"{prefix}_{side}"
        for prefixes in BOUNDARY_COMPONENTS.values()
        for prefix in prefixes
        for side in BOUNDARY_SIDES.values()
    },
}
MONTHLY_COLUMNS = {"time", "SP", "CWR", "dxy"}
NETCDF3_SIGNATURES = (b"CDF\x01", b"CDF\x02", b"CDF\x05")
HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"


@dataclass(frozen=True)
class CloudWaterMetricsSpec:
    task_id: str
    year: int
    region_name: str
    annual_csv: Path
    monthly_csv: Path
    mask_nc: Path
    spatial_nc: Path
    output_root: Path
    artifact_name: str


def build_cloud_water_business_metrics(spec_path: Path) -> Path:
    spec = load_cloud_water_metrics_spec(spec_path)
    metrics, spatial = derive_cloud_water_business_metrics(spec)
    targets = _artifact_targets(spec)

    spec.output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="cwr-business-metrics-",
        dir=spec.output_root.parent,
    ) as raw_temp:
        temp = Path(raw_temp)
        temp_metrics = temp / targets["metrics"].name
        temp_spatial = temp / targets["spatial"].name
        temp_report_inputs = temp / targets["report_inputs"].name
        temp_metrics.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        spatial.to_netcdf(temp_spatial, engine="scipy")
        temp_report_inputs.write_text(
            json.dumps(
                _report_inputs_payload(spec, targets),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        for target in targets.values():
            target.parent.mkdir(parents=True, exist_ok=True)
        temp_metrics.replace(targets["metrics"])
        temp_spatial.replace(targets["spatial"])
        temp_report_inputs.replace(targets["report_inputs"])
    return targets["report_inputs"]


def load_cloud_water_metrics_spec(path: Path) -> CloudWaterMetricsSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("metric_profile") != PROFILE_NAME:
        raise ValueError(f"metric_profile must be {PROFILE_NAME}")
    base = path.parent
    year = payload.get("year")
    if not isinstance(year, int) or isinstance(year, bool):
        raise ValueError("year must be an integer")
    artifact_name = payload.get("artifact_name", PROFILE_NAME)
    if not isinstance(artifact_name, str) or not artifact_name.strip():
        raise ValueError("artifact_name must be a non-empty string")
    if Path(artifact_name).name != artifact_name:
        raise ValueError("artifact_name must not contain path separators")
    return CloudWaterMetricsSpec(
        task_id=_required_text(payload, "task_id"),
        year=year,
        region_name=_required_text(payload, "region_name"),
        annual_csv=_existing_path(base, payload, "annual_csv"),
        monthly_csv=_existing_path(base, payload, "monthly_csv"),
        mask_nc=_existing_path(base, payload, "mask_nc"),
        spatial_nc=_existing_path(base, payload, "spatial_nc"),
        output_root=_path(base, payload, "output_root"),
        artifact_name=artifact_name,
    )


def derive_cloud_water_business_metrics(
    spec: CloudWaterMetricsSpec,
) -> tuple[dict[str, Any], xr.Dataset]:
    annual = _select_annual_row(spec.annual_csv, spec.year)
    months = _select_monthly_rows(spec.monthly_csv, spec.year)
    dxy = _number(annual, "dxy")
    if np.isclose(dxy, 0):
        raise ValueError("annual dxy must not be zero")

    monthly = [
        {
            "month": month,
            "SP": _number(months[month], "SP"),
            "CWR": _number(months[month], "CWR"),
            "dxy": _number(months[month], "dxy"),
            "SP_mm": _number(months[month], "SP") / dxy,
            "CWR_mm": _number(months[month], "CWR") / dxy,
        }
        for month in range(1, 13)
    ]
    seasons = {
        season: {
            "months": season_months,
            "SP_mm": sum(monthly[month - 1]["SP_mm"] for month in season_months),
            "CWR_mm": sum(
                monthly[month - 1]["CWR_mm"] for month in season_months
            ),
        }
        for season, season_months in SEASON_MONTHS.items()
    }
    boundaries = {
        name: _boundary_metrics(annual, incoming, outgoing)
        for name, (incoming, outgoing) in BOUNDARY_COMPONENTS.items()
    }
    spatial = _spatial_composite(spec.mask_nc, spec.spatial_nc)
    metrics = {
        "schema_version": 1,
        "kind": "business_metrics",
        "metric_profile": PROFILE_NAME,
        "task_id": spec.task_id,
        "year": spec.year,
        "region_name": spec.region_name,
        "units": {
            "annual_mass": "kg",
            "equivalent_depth": "mm",
            "boundary_mass": "1e11 kg",
        },
        "annual": {
            "values": {
                name: _number(annual, name) for name in ANNUAL_VARIABLES
            },
            "equivalent_depth_mm": {
                name: _number(annual, name) / dxy
                for name in ("GMv", "GMh", "SP", "CWR")
            },
        },
        "monthly": monthly,
        "seasons": seasons,
        "boundaries": boundaries,
        "spatial_composite": {
            "artifact_name": spec.artifact_name,
            "mask_variable": "ind_area_bool",
            "variables": SPATIAL_VARIABLES,
        },
    }
    return metrics, spatial


def _select_annual_row(path: Path, year: int) -> dict[str, str]:
    matches = [
        row
        for row in _read_csv(path, ANNUAL_COLUMNS)
        if _year(row["time"]) == year
    ]
    if len(matches) != 1:
        raise ValueError(f"annual_csv must contain exactly one row for {year}")
    return matches[0]


def _select_monthly_rows(
    path: Path,
    year: int,
) -> dict[int, dict[str, str]]:
    months: dict[int, dict[str, str]] = {}
    for row in _read_csv(path, MONTHLY_COLUMNS):
        if _year(row["time"]) != year:
            continue
        month = _month(row["time"])
        if month in months:
            raise ValueError(f"monthly_csv has duplicate {year}-{month:02d}")
        months[month] = row
    expected = set(range(1, 13))
    if set(months) != expected:
        missing = sorted(expected - set(months))
        raise ValueError(f"monthly_csv is missing months: {missing}")
    return months


def _boundary_metrics(
    annual: dict[str, str],
    incoming_prefix: str,
    outgoing_prefix: str,
) -> list[dict[str, float | str]]:
    rows = []
    for name, side in BOUNDARY_SIDES.items():
        incoming = _number(annual, f"{incoming_prefix}_{side}") / 1e11
        outgoing = _number(annual, f"{outgoing_prefix}_{side}") / 1e11
        rows.append(
            {
                "boundary": name,
                "input": incoming,
                "output": outgoing,
                "net_input": incoming - outgoing,
            }
        )
    rows.append(
        {
            "boundary": "total",
            "input": sum(float(row["input"]) for row in rows),
            "output": sum(float(row["output"]) for row in rows),
            "net_input": sum(float(row["net_input"]) for row in rows),
        }
    )
    return rows


def _spatial_composite(mask_path: Path, spatial_path: Path) -> xr.Dataset:
    with _open_netcdf(mask_path) as mask_dataset:
        mask_name = (
            "ind_area_bool"
            if "ind_area_bool" in mask_dataset
            else next(iter(mask_dataset.data_vars))
        )
        mask = mask_dataset[mask_name].load().astype(bool)
    with _open_netcdf(spatial_path) as spatial_dataset:
        missing = sorted(set(SPATIAL_VARIABLES) - set(spatial_dataset.data_vars))
        if missing:
            raise ValueError(f"spatial_nc is missing variable: {missing[0]}")
        if any(
            spatial_dataset[name].shape != mask.shape for name in SPATIAL_VARIABLES
        ):
            raise ValueError("spatial_nc variables must match mask shape")
        composite = spatial_dataset[SPATIAL_VARIABLES].load()

    target = composite[SPATIAL_VARIABLES[0]]
    if set(mask.dims) != set(target.dims):
        raise ValueError("mask_nc and spatial_nc dimensions are incompatible")
    mask = mask.transpose(*target.dims)
    for dimension in target.dims:
        if dimension in mask.coords and dimension in target.coords:
            if not np.array_equal(
                mask[dimension].values,
                target[dimension].values,
                equal_nan=True,
            ):
                raise ValueError(
                    "mask_nc and spatial_nc coordinates are incompatible"
                )
    if any(
        composite[name].dims != target.dims for name in SPATIAL_VARIABLES
    ):
        raise ValueError("spatial_nc variable dimensions are incompatible")
    composite["ind_area_bool"] = mask
    composite.attrs.update(
        {
            "schema_version": 1,
            "metric_profile": PROFILE_NAME,
        }
    )
    return composite


def _artifact_targets(spec: CloudWaterMetricsSpec) -> dict[str, Path]:
    return {
        "metrics": (
            spec.output_root
            / "business_metrics"
            / f"{spec.artifact_name}.json"
        ),
        "spatial": (
            spec.output_root
            / "spatial_composite"
            / f"{spec.artifact_name}.nc"
        ),
        "report_inputs": spec.output_root / "report_inputs" / "report_inputs.json",
    }


def _report_inputs_payload(
    spec: CloudWaterMetricsSpec,
    targets: dict[str, Path],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task": {
            "task_id": spec.task_id,
            "status": "success",
            "output_root": str(spec.output_root),
        },
        "inputs": {
            "metric_profile": PROFILE_NAME,
            "time_slices": [
                {"scale": "year", "year": spec.year, "label": str(spec.year)}
            ],
            "region_name": spec.region_name,
        },
        "artifacts": [
            {
                "kind": "business_metrics",
                "name": spec.artifact_name,
                "metric_profile": PROFILE_NAME,
                "schema_version": 1,
                "path": str(targets["metrics"]),
            },
            {
                "kind": "spatial_composite",
                "name": spec.artifact_name,
                "metric_profile": PROFILE_NAME,
                "schema_version": 1,
                "path": str(targets["spatial"]),
            },
        ],
        "runtime": {
            "workflow_steps": ["business_metrics", "report_inputs"],
            "executed_steps": ["business_metrics", "report_inputs"],
            "used_cache": [],
        },
        "stats": [],
    }


def _open_netcdf(path: Path) -> xr.Dataset:
    with path.open("rb") as stream:
        signature = stream.read(8)
    if signature.startswith(NETCDF3_SIGNATURES):
        return xr.open_dataset(path, engine="scipy")
    if signature == HDF5_SIGNATURE:
        return xr.open_dataset(path, engine="h5netcdf")
    raise ValueError(f"unsupported NetCDF file format: {path}")


def _read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = sorted(required - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"{path.name} is missing column: {missing[0]}")
        return list(reader)


def _year(value: str) -> int:
    try:
        return int(str(value)[:4])
    except ValueError as error:
        raise ValueError(f"Invalid CSV time: {value}") from error


def _month(value: str) -> int:
    try:
        month = int(str(value)[5:7])
    except ValueError as error:
        raise ValueError(f"Invalid monthly CSV time: {value}") from error
    if month not in range(1, 13):
        raise ValueError(f"Invalid monthly CSV time: {value}")
    return month


def _number(row: dict[str, str], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric value for {key}") from error
    if not math.isfinite(value):
        raise ValueError(f"Non-finite numeric value for {key}")
    return value


def _required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _path(base: Path, payload: dict[str, Any], key: str) -> Path:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty path")
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _existing_path(base: Path, payload: dict[str, Any], key: str) -> Path:
    path = _path(base, payload, key)
    if not path.is_file():
        raise ValueError(f"{key} does not exist: {path}")
    return path
