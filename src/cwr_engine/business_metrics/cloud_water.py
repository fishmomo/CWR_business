from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
import math
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water_figures import (
    IMAGE_SLOTS,
    render_cloud_water_figures,
)
from cwr_engine.steps.mask import compile_shp_mask


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
    "pic3_d",
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
DIRECT_ANNUAL_SOURCE_VARIABLES = [
    "SP",
    "Mv0",
    "MvT",
    "aveMv",
    "Mh0",
    "aveMh",
    "MC",
    "ME",
    "GMv",
    "GMh",
    "CWR",
    "CEv",
    "PEh",
    "dxy",
    *[
        f"{component}_QData{flow}_{side}Temp"
        for component in ("qv", "qc")
        for flow in ("In", "Out")
        for side in ("W", "E", "N", "S")
    ],
]
DIRECT_MONTHLY_SOURCE_VARIABLES = [
    "SP",
    "Mv0",
    "MvT",
    "Mh0",
    "aveMv",
    "aveMh",
    "MC",
    "ME",
    "CWR",
    "dxy",
    *[
        f"{component}_QData{flow}_{side}Temp"
        for component in ("qv", "qc")
        for flow in ("In", "Out")
        for side in ("W", "E", "N", "S")
    ],
]
NETCDF3_SIGNATURES = (b"CDF\x01", b"CDF\x02", b"CDF\x05")
HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"


@dataclass(frozen=True)
class CloudWaterMetricsSpec:
    task_id: str
    year: int
    region_name: str
    product_source: dict[str, Any]
    region_spec: dict[str, Any]
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
        temp_figures = {
            slot: temp / targets[f"figure_{index}"].name
            for index, slot in enumerate(IMAGE_SLOTS, start=1)
            if f"figure_{index}" in targets
        }
        temp_metrics.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        spatial.to_netcdf(temp_spatial, engine="scipy")
        if temp_figures:
            render_cloud_water_figures(
                metrics,
                spatial,
                spec.region_spec,
                temp_figures,
            )
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
        for index, slot in enumerate(IMAGE_SLOTS, start=1):
            if slot in temp_figures:
                temp_figures[slot].replace(targets[f"figure_{index}"])
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
    retained_keys = {"annual_csv", "monthly_csv", "mask_nc", "spatial_nc"}
    if retained_keys & set(payload):
        raise ValueError(
            "Retained CSV/spatial metric inputs are no longer supported; "
            "use product_source and region_spec"
        )
    product_source = _product_source(base, payload.get("product_source"))
    region_spec = _region_spec(base, payload.get("region_spec"))
    return CloudWaterMetricsSpec(
        task_id=_required_text(payload, "task_id"),
        year=year,
        region_name=_required_text(payload, "region_name"),
        product_source=product_source,
        region_spec=region_spec,
        output_root=_path(base, payload, "output_root"),
        artifact_name=artifact_name,
    )


def derive_cloud_water_business_metrics(
    spec: CloudWaterMetricsSpec,
) -> tuple[dict[str, Any], xr.Dataset]:
    annual, months, spatial = _derive_direct_product_inputs(spec)
    input_mode = "product_catalog"
    dxy = _number(annual, "dxy")
    if np.isclose(dxy, 0):
        raise ValueError("annual dxy must not be zero")

    monthly = []
    for month in range(1, 13):
        source = months[month]
        row = {
            "month": month,
            "SP": _number(source, "SP"),
            "CWR": _number(source, "CWR"),
            "dxy": _number(source, "dxy"),
            "SP_mm": _number(source, "SP") / dxy,
            "CWR_mm": _number(source, "CWR") / dxy,
        }
        optional = ("GMv", "GMh", "MC", "CEv", "RCh", "PEh")
        if all(name in source for name in optional):
            row.update(
                {
                    name: _number(source, name)
                    for name in optional
                }
            )
            row.update(
                {
                    "GMv_mm": row["GMv"] / dxy,
                    "GMh_mm": row["GMh"] / dxy,
                    "MC_mm": row["MC"] / dxy,
                }
            )
        monthly.append(row)
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
    metrics = {
        "schema_version": 1,
        "kind": "business_metrics",
        "metric_profile": PROFILE_NAME,
        "task_id": spec.task_id,
        "year": spec.year,
        "region_name": spec.region_name,
        "input_mode": input_mode,
        "source": _metrics_source(spec, input_mode),
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


def _derive_direct_product_inputs(
    spec: CloudWaterMetricsSpec,
) -> tuple[dict[str, float | str], dict[int, dict[str, float | str]], xr.Dataset]:
    annual_path, monthly_paths = _discover_direct_product_files(
        spec.product_source,
        spec.year,
    )
    annual_dataset = _load_direct_product(
        annual_path,
        spec.product_source,
        DIRECT_ANNUAL_SOURCE_VARIABLES,
    )
    mask = _compile_direct_mask(
        spec.region_spec,
        annual_dataset["lat"].values,
        annual_dataset["lon"].values,
    )
    annual = _aggregate_direct_product(
        annual_dataset,
        mask,
        spec.year,
        month=None,
    )

    monthly_datasets: dict[int, xr.Dataset] = {}
    months: dict[int, dict[str, float | str]] = {}
    for month, product_path in monthly_paths.items():
        dataset = _load_direct_product(
            product_path,
            spec.product_source,
            DIRECT_MONTHLY_SOURCE_VARIABLES,
        )
        _validate_product_grid(annual_dataset, dataset)
        monthly_datasets[month] = dataset
        months[month] = _aggregate_direct_product(
            dataset,
            mask,
            spec.year,
            month=month,
        )
    spatial = _direct_spatial_composite(
        annual_dataset,
        monthly_datasets,
        mask,
    )
    return annual, months, spatial


def _discover_direct_product_files(
    source: dict[str, Any],
    year: int,
) -> tuple[Path, dict[int, Path]]:
    root: Path = source["root"]
    year_root = root / "Y" if (root / "Y").is_dir() else root
    month_root = root / "M" if (root / "M").is_dir() else root
    annual_pattern = source.get(
        "annual_pattern",
        f"ResultGrid_Y_{year}-*.nc",
    ).format(year=year)
    annual_matches = sorted(year_root.glob(annual_pattern))
    if len(annual_matches) != 1:
        raise ValueError(
            f"Expected one annual product for {year}, found "
            f"{len(annual_matches)}"
        )
    monthly_paths = {}
    for month in range(1, 13):
        pattern = source.get(
            "monthly_pattern",
            "ResultGrid_M_{year}-{month:02d}-*.nc",
        ).format(year=year, month=month)
        matches = sorted(month_root.glob(pattern))
        if len(matches) != 1:
            raise ValueError(
                f"Expected one monthly product for {year}-{month:02d}, found "
                f"{len(matches)}"
            )
        monthly_paths[month] = matches[0]
    return annual_matches[0], monthly_paths


def _load_direct_product(
    path: Path,
    source: dict[str, Any],
    logical_variables: list[str],
) -> xr.Dataset:
    with xr.open_dataset(path, engine=source.get("engine", "h5netcdf")) as opened:
        coordinate_map = source.get("coordinate_map", {})
        lat_name = coordinate_map.get("lat") or _coordinate_name(
            opened,
            ("lat", "latitude"),
        )
        lon_name = coordinate_map.get("lon") or _coordinate_name(
            opened,
            ("lon", "longitude"),
        )
        if opened[lat_name].ndim != 1 or opened[lon_name].ndim != 1:
            raise ValueError(f"Product coordinates must be one-dimensional: {path}")
        normalized = opened.rename(
            {
                **({lat_name: "lat"} if lat_name != "lat" else {}),
                **({lon_name: "lon"} if lon_name != "lon" else {}),
            }
        )
        variable_map = source.get("variable_map", {})
        missing = [
            logical
            for logical in logical_variables
            if variable_map.get(logical, logical) not in normalized
        ]
        if missing:
            raise ValueError(f"Product is missing variable {missing[0]}: {path}")
        result = xr.Dataset(coords={"lat": normalized["lat"], "lon": normalized["lon"]})
        for logical in logical_variables:
            source_name = variable_map.get(logical, logical)
            data = normalized[source_name].squeeze(drop=True)
            if data.dims != ("lat", "lon"):
                try:
                    data = data.transpose("lat", "lon")
                except ValueError as error:
                    raise ValueError(
                        f"Product variable {source_name} is not a lat/lon grid: "
                        f"{path}"
                    ) from error
            result[logical] = data.load()
        return result


def _compile_direct_mask(
    region_spec: dict[str, Any],
    lat_values: np.ndarray,
    lon_values: np.ndarray,
) -> xr.DataArray:
    kind = region_spec["kind"]
    payload = region_spec["payload"]
    if kind == "shp":
        return compile_shp_mask(
            Path(payload["path"]),
            payload,
            lat_values,
            lon_values,
        )
    if kind == "existing_mask":
        path = Path(payload["path"])
        with _open_netcdf(path) as dataset:
            variable = payload.get("variable") or next(iter(dataset.data_vars))
            mask = dataset[variable].load().astype(bool)
        lat_name = "lat" if "lat" in mask.coords else "latitude"
        lon_name = "lon" if "lon" in mask.coords else "longitude"
        mask = mask.rename(
            {
                **({lat_name: "lat"} if lat_name != "lat" else {}),
                **({lon_name: "lon"} if lon_name != "lon" else {}),
            }
        ).transpose("lat", "lon")
        expected = xr.DataArray(
            np.zeros((len(lat_values), len(lon_values))),
            coords={"lat": lat_values, "lon": lon_values},
            dims=("lat", "lon"),
        )
        _validate_product_grid(
            xr.Dataset({"grid": expected}),
            xr.Dataset({"grid": mask}),
        )
        return mask
    if kind == "bbox":
        lat = xr.DataArray(lat_values, dims="lat", coords={"lat": lat_values})
        lon = xr.DataArray(lon_values, dims="lon", coords={"lon": lon_values})
        return (
            (lat >= payload["min_lat"])
            & (lat <= payload["max_lat"])
            & (lon >= payload["min_lon"])
            & (lon <= payload["max_lon"])
        ).rename("ind_area_bool")
    raise ValueError(f"Unsupported direct region kind: {kind}")


def _aggregate_direct_product(
    dataset: xr.Dataset,
    mask: xr.DataArray,
    year: int,
    month: int | None,
) -> dict[str, float | str]:
    boundary_indices = _boundary_indices(
        mask.values.astype(bool),
        dataset["lat"].values,
        dataset["lon"].values,
    )
    boundaries = {}
    for component, short_name in (("qv", "v"), ("qc", "h")):
        for flow, metric_prefix in (("In", "IN"), ("Out", "OT")):
            for side, boundary_name in (
                ("W", "west"),
                ("E", "east"),
                ("N", "north"),
                ("S", "south"),
            ):
                key = f"{metric_prefix}{short_name}_{side}"
                source_name = f"{component}_QData{flow}_{side}Temp"
                boundaries[key] = _boundary_sum(
                    dataset[source_name].values,
                    boundary_indices[boundary_name],
                    source_name,
                )

    incoming_vapor = sum(boundaries[f"INv_{side}"] for side in "WENS")
    outgoing_vapor = sum(boundaries[f"OTv_{side}"] for side in "WENS")
    incoming_hydro = sum(boundaries[f"INh_{side}"] for side in "WENS")
    outgoing_hydro = sum(boundaries[f"OTh_{side}"] for side in "WENS")
    values = {
        name: _masked_sum(dataset[name].values, mask.values, name)
        for name in (
            "Mv0",
            "MvT",
            "Mh0",
            "aveMv",
            "aveMh",
            "MC",
            "ME",
            "SP",
            "dxy",
        )
    }
    storage_exchange = (
        (values["MvT"] - values["Mv0"])
        + (outgoing_vapor - incoming_vapor)
        + (values["MC"] - values["ME"])
    )
    gmh = incoming_hydro + values["Mh0"] + values["MC"]
    cwr = gmh - values["SP"]
    gmv = (
        incoming_vapor
        + values["Mv0"]
        + values["ME"]
        + storage_exchange
    )
    days = (
        (date(year + 1, 1, 1) - date(year, 1, 1)).days
        if month is None
        else (date(year + (month == 12), month % 12 + 1, 1) - date(year, month, 1)).days
    )
    result: dict[str, float | str] = {
        "time": (
            f"{year}-01-01T00:00:00"
            if month is None
            else f"{year}-{month:02d}-01T00:00:00"
        ),
        "GMv": gmv,
        "GMh": gmh,
        "SP": values["SP"],
        "CWR": cwr,
        "MC": values["MC"],
        "CEv": _rounded_ratio(values["MC"], gmv, 5, 100),
        "PEh": _rounded_ratio(values["SP"], gmh, 5, 100),
        "PEv": _rounded_ratio(values["SP"], gmv, 5, 100),
        "PEw": _rounded_ratio(values["SP"], gmv + gmh, 5, 100),
        "dxy": values["dxy"],
        **boundaries,
    }
    result.update(
        {
            "RCv": _rounded_ratio(
                values["aveMv"],
                values["SP"] / days,
                3,
            ),
            "RCh": _rounded_ratio(
                values["aveMh"],
                values["SP"] / (days * 24),
                3,
            ),
        }
    )
    return result


def _direct_spatial_composite(
    annual: xr.Dataset,
    monthly: dict[int, xr.Dataset],
    mask: xr.DataArray,
) -> xr.Dataset:
    dxy = annual["dxy"]
    if bool((dxy == 0).any().item()):
        raise ValueError("Annual product dxy contains zero")
    if any(
        bool((dataset["dxy"] == 0).any().item())
        for dataset in monthly.values()
    ):
        raise ValueError("Monthly product dxy contains zero")
    composite = xr.Dataset(
        {
            "pic3_a": annual["GMv"] / dxy,
            "pic3_b": annual["CEv"],
            "pic3_c": annual["CWR"] / dxy,
            "pic3_d": annual["GMh"] / dxy,
            "pic3_e": annual["SP"] / dxy,
            "pic3_f": annual["PEh"],
        },
        coords={"lat": annual["lat"], "lon": annual["lon"]},
    )
    season_order = [
        ("spring", [3, 4, 5]),
        ("summer", [6, 7, 8]),
        ("autumn", [9, 10, 11]),
        ("winter", [12, 1, 2]),
    ]
    for index, (_, month_numbers) in enumerate(season_order):
        suffix = chr(ord("a") + index)
        composite[f"pic4_{suffix}"] = sum(
            monthly[month]["SP"] / monthly[month]["dxy"]
            for month in month_numbers
        )
        composite[f"pic5_{suffix}"] = sum(
            monthly[month]["CWR"] / monthly[month]["dxy"]
            for month in month_numbers
        )
    composite["ind_area_bool"] = mask
    composite.attrs.update(
        {
            "schema_version": 1,
            "metric_profile": PROFILE_NAME,
            "source_mode": "product_catalog",
        }
    )
    return composite


def _boundary_indices(
    mask: np.ndarray,
    lat_values: np.ndarray,
    lon_values: np.ndarray,
) -> dict[str, list[tuple[int, int]]]:
    result = {name: [] for name in ("west", "east", "north", "south")}
    lon_ascending = bool(lon_values[0] < lon_values[-1])
    lat_ascending = bool(lat_values[0] < lat_values[-1])
    for row_index in range(mask.shape[0]):
        for segment in _contiguous_segments(np.where(mask[row_index])[0]):
            west_index = segment[0] if lon_ascending else segment[-1]
            east_index = segment[-1] if lon_ascending else segment[0]
            result["west"].append((row_index, int(west_index)))
            result["east"].append((row_index, int(east_index)))
    for column_index in range(mask.shape[1]):
        for segment in _contiguous_segments(np.where(mask[:, column_index])[0]):
            north_index = segment[-1] if lat_ascending else segment[0]
            south_index = segment[0] if lat_ascending else segment[-1]
            result["north"].append((int(north_index), column_index))
            result["south"].append((int(south_index), column_index))
    if not all(result.values()):
        raise ValueError("Region mask has no complete directional boundaries")
    return result


def _contiguous_segments(indices: np.ndarray) -> list[np.ndarray]:
    if indices.size == 0:
        return []
    return list(np.split(indices, np.where(np.diff(indices) > 1)[0] + 1))


def _boundary_sum(
    values: np.ndarray,
    indices: list[tuple[int, int]],
    variable: str,
) -> float:
    selected = np.asarray([values[index] for index in indices], dtype=float)
    if not np.all(np.isfinite(selected)):
        raise ValueError(f"Product boundary variable {variable} is non-finite")
    return float(selected.sum())


def _masked_sum(values: np.ndarray, mask: np.ndarray, variable: str) -> float:
    selected = np.asarray(values[mask], dtype=float)
    if not np.all(np.isfinite(selected)):
        raise ValueError(f"Product variable {variable} is non-finite in region")
    return float(selected.sum())


def _rounded_ratio(
    numerator: float,
    denominator: float,
    decimals: int,
    scale: float = 1,
) -> float:
    if np.isclose(denominator, 0):
        raise ValueError("Direct product metric denominator must not be zero")
    return float(np.round(numerator / denominator, decimals) * scale)


def _validate_product_grid(reference: xr.Dataset, candidate: xr.Dataset) -> None:
    for coordinate in ("lat", "lon"):
        if not np.array_equal(
            reference[coordinate].values,
            candidate[coordinate].values,
            equal_nan=True,
        ):
            raise ValueError("Product files use incompatible grids")


def _coordinate_name(dataset: xr.Dataset, names: tuple[str, ...]) -> str:
    for name in names:
        if name in dataset.coords:
            return name
    raise ValueError(f"Product is missing coordinate: {' or '.join(names)}")


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


def _artifact_targets(spec: CloudWaterMetricsSpec) -> dict[str, Path]:
    targets = {
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
    targets.update(
        {
            f"figure_{index}": (
                spec.output_root / "profile_image" / f"{slot}.png"
            )
            for index, slot in enumerate(IMAGE_SLOTS, start=1)
        }
    )
    return targets


def _report_inputs_payload(
    spec: CloudWaterMetricsSpec,
    targets: dict[str, Path],
) -> dict[str, Any]:
    artifacts = [
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
    ]
    for index, slot in enumerate(IMAGE_SLOTS, start=1):
        figure_key = f"figure_{index}"
        if figure_key in targets:
            artifacts.append(
                {
                    "kind": "profile_image",
                    "name": slot,
                    "metric_profile": PROFILE_NAME,
                    "schema_version": 1,
                    "path": str(targets[figure_key]),
                }
            )
    workflow_steps = ["business_metrics"]
    workflow_steps.append("profile_figures")
    workflow_steps.append("report_inputs")
    return {
        "schema_version": 1,
        "task": {
            "task_id": spec.task_id,
            "status": "success",
            "output_root": str(spec.output_root),
        },
        "inputs": {
            "metric_profile": PROFILE_NAME,
            "metric_input_mode": "product_catalog",
            "time_slices": [
                {"scale": "year", "year": spec.year, "label": str(spec.year)}
            ],
            "region_name": spec.region_name,
        },
        "artifacts": artifacts,
        "runtime": {
            "workflow_steps": workflow_steps,
            "executed_steps": workflow_steps,
            "used_cache": [],
        },
        "stats": [],
    }


def _metrics_source(
    spec: CloudWaterMetricsSpec,
    input_mode: str,
) -> dict[str, Any]:
    return {
        "mode": input_mode,
        "root": str(spec.product_source["root"]),
        "annual_scale": "year",
        "annual_product_count": 1,
        "monthly_scale": "month",
        "monthly_product_count": 12,
        "region_kind": spec.region_spec["kind"],
    }


def _open_netcdf(path: Path) -> xr.Dataset:
    with path.open("rb") as stream:
        signature = stream.read(8)
    if signature.startswith(NETCDF3_SIGNATURES):
        return xr.open_dataset(path, engine="scipy")
    if signature == HDF5_SIGNATURE:
        return xr.open_dataset(path, engine="h5netcdf")
    raise ValueError(f"unsupported NetCDF file format: {path}")


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
    source = {**value, "root": root}
    for key in ("coordinate_map", "variable_map"):
        if key in source and not isinstance(source[key], dict):
            raise ValueError(f"product_source.{key} must be an object")
    for key in ("annual_pattern", "monthly_pattern", "engine"):
        if key in source and (
            not isinstance(source[key], str) or not source[key].strip()
        ):
            raise ValueError(f"product_source.{key} must be a non-empty string")
    return source


def _region_spec(base: Path, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("region_spec must be an object")
    kind = value.get("kind")
    payload = value.get("payload")
    if kind not in {"shp", "existing_mask", "bbox"}:
        raise ValueError("region_spec.kind must be shp, existing_mask, or bbox")
    if not isinstance(payload, dict):
        raise ValueError("region_spec.payload must be an object")
    resolved_payload = dict(payload)
    if kind in {"shp", "existing_mask"}:
        raw_path = payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("region_spec.payload.path must be a non-empty path")
        path = Path(raw_path)
        path = path if path.is_absolute() else (base / path).resolve()
        if not path.is_file():
            raise ValueError(f"region_spec path does not exist: {path}")
        resolved_payload["path"] = str(path)
    else:
        required = {"min_lon", "max_lon", "min_lat", "max_lat"}
        if not required <= set(payload):
            missing = sorted(required - set(payload))
            raise ValueError(f"bbox region_spec is missing {missing[0]}")
    return {"kind": kind, "payload": resolved_payload}
