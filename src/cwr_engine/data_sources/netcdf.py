from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
import re

import numpy as np
import xarray as xr

from cwr_engine.registries.variables import resolve_source_keys


SCALE_CODES = {"day": "D", "month": "M", "year": "Y"}
PRODUCT_DATE_PATTERN = re.compile(
    r"ResultGrid_[DMY]_(?P<date>\d{4}-\d{2}-\d{2})"
)


def load_netcdf_source(context: dict) -> tuple[xr.Dataset, dict]:
    task = context["task"]
    source = task.data_source
    root = _resolve_path(source["root"], context["task_path"])
    expected_dates = _expected_dates(task.time_slices, source["time_scale"])
    files = _discover_files(root, source, expected_dates)
    datasets = [
        _load_product_file(path, source, context["variable_registry"], task.variables)
        for path in files
    ]
    dataset = _combine_datasets(datasets)
    dataset = _select_and_validate_times(
        dataset,
        expected_dates,
        source["time_scale"],
    )
    trace = {
        "file_count": len(files),
        "first_file": str(files[0]),
        "last_file": str(files[-1]),
        "time_scale": source["time_scale"],
    }
    return dataset, trace


def _discover_files(
    root: Path,
    source: dict,
    expected_dates: list[date],
) -> list[Path]:
    if root.is_file():
        return [root]
    if not root.exists():
        raise FileNotFoundError(f"Data source path does not exist: {root}")
    if not root.is_dir():
        raise ValueError(f"Data source path is not a file or directory: {root}")

    scale = source["time_scale"]
    scale_code = SCALE_CODES[scale]
    scale_directory = root / scale_code
    if not scale_directory.is_dir():
        scale_directory = root
    pattern = source.get("pattern", f"ResultGrid_{scale_code}_*.nc")
    candidates = sorted(scale_directory.glob(pattern))
    if not candidates:
        raise FileNotFoundError(
            f"No NetCDF product files match {pattern!r} under {scale_directory}"
        )

    expected_set = set(expected_dates)
    files_by_date: dict[date, Path] = {}
    duplicate_filenames: list[str] = []
    for path in candidates:
        product_date = _date_from_filename(path)
        if product_date not in expected_set:
            continue
        if product_date in files_by_date:
            duplicate_filenames.append(product_date.isoformat())
        files_by_date[product_date] = path
    if duplicate_filenames:
        duplicates = ", ".join(sorted(set(duplicate_filenames)))
        raise ValueError(f"Duplicate {scale} source files: {duplicates}")

    missing = [item for item in expected_dates if item not in files_by_date]
    if missing:
        missing_text = ", ".join(item.isoformat() for item in missing)
        raise ValueError(f"Missing {scale} source periods: {missing_text}")
    return [files_by_date[item] for item in expected_dates]


def _load_product_file(
    path: Path,
    source: dict,
    variable_registry: dict,
    variables: list[str],
) -> xr.Dataset:
    engine = source.get("engine")
    open_kwargs = {"engine": engine} if engine else {}
    with xr.open_dataset(path, **open_kwargs) as opened:
        dataset = _normalize_coordinates(opened, source.get("coordinate_map", {}))
        source_keys = []
        for variable in variables:
            try:
                resolved_keys = resolve_source_keys(
                    variable,
                    variable_registry,
                    dataset,
                    source.get("variable_map"),
                )
            except ValueError as error:
                raise ValueError(f"{error} in {path}") from error
            for source_key in resolved_keys:
                if source_key not in source_keys:
                    source_keys.append(source_key)
        return dataset[source_keys].load()


def _normalize_coordinates(
    dataset: xr.Dataset,
    coordinate_map: dict[str, str],
) -> xr.Dataset:
    time_name = coordinate_map.get("time") or _find_coordinate(
        dataset, ["time", "valid_time"]
    )
    lat_name = coordinate_map.get("lat") or _find_coordinate(
        dataset, ["lat", "latitude"]
    )
    lon_name = coordinate_map.get("lon") or _find_coordinate(
        dataset, ["lon", "longitude"]
    )

    normalized = dataset
    if time_name != "time":
        normalized = normalized.rename({time_name: "time"})
    if "time" not in normalized.dims:
        normalized = normalized.expand_dims("time")
    normalized = _normalize_spatial_axis(normalized, lat_name, "lat")
    normalized = _normalize_spatial_axis(normalized, lon_name, "lon")

    if normalized["time"].ndim != 1:
        raise ValueError("Time coordinate must be scalar or one-dimensional")
    if normalized["lat"].ndim != 1 or normalized["lon"].ndim != 1:
        raise ValueError("Latitude and longitude coordinates must be one-dimensional")
    return normalized.sortby(["time", "lat", "lon"])


def _normalize_spatial_axis(
    dataset: xr.Dataset,
    source_name: str,
    target_name: str,
) -> xr.Dataset:
    coordinate = dataset[source_name]
    if coordinate.ndim != 1:
        raise ValueError(f"Coordinate {source_name} must be one-dimensional")
    coordinate_dimension = coordinate.dims[0]
    if source_name == coordinate_dimension:
        if source_name == target_name:
            return dataset
        return dataset.rename({source_name: target_name})

    # CRA40 stores values in latitude(lat) while fields use a separate
    # latitude dimension. Rebind those values to the field dimension.
    dimension = (
        source_name
        if source_name in dataset.dims
        and dataset.sizes[source_name] == coordinate.size
        else coordinate_dimension
    )
    values = coordinate.values
    normalized = dataset.drop_vars(source_name)
    normalized = normalized.assign_coords({dimension: values})
    if dimension != target_name:
        normalized = normalized.rename({dimension: target_name})
    return normalized


def _find_coordinate(dataset: xr.Dataset, candidates: list[str]) -> str:
    for name in candidates:
        if name in dataset.coords:
            return name
    expected = ", ".join(candidates)
    raise ValueError(f"Missing coordinate; expected one of: {expected}")


def _combine_datasets(datasets: list[xr.Dataset]) -> xr.Dataset:
    if len(datasets) == 1:
        return datasets[0]
    try:
        return xr.concat(
            datasets,
            dim="time",
            data_vars="all",
            coords="minimal",
            compat="override",
            join="exact",
        ).sortby("time")
    except ValueError as error:
        raise ValueError(f"Product files use incompatible grids: {error}") from error


def _select_and_validate_times(
    dataset: xr.Dataset,
    expected_dates: list[date],
    scale: str,
) -> xr.Dataset:
    actual_dates = [_as_date(value) for value in dataset["time"].values]
    duplicates = sorted(
        {item for item in actual_dates if actual_dates.count(item) > 1}
    )
    if duplicates:
        duplicate_text = ", ".join(item.isoformat() for item in duplicates)
        raise ValueError(f"Duplicate source times: {duplicate_text}")

    expected_set = set(expected_dates)
    missing = [item for item in expected_dates if item not in actual_dates]
    if missing:
        missing_text = ", ".join(item.isoformat() for item in missing)
        raise ValueError(f"Missing {scale} source periods: {missing_text}")
    selected_indexes = [
        index for index, item in enumerate(actual_dates) if item in expected_set
    ]
    return dataset.isel(time=selected_indexes).sortby("time")


def _expected_dates(time_slices, scale: str) -> list[date]:
    result = set()
    for time_slice in time_slices:
        start = date.fromisoformat(time_slice.start)
        end = date.fromisoformat(time_slice.end)
        current = _period_start(start, scale)
        while current <= end:
            result.add(current)
            current = _next_period(current, scale)
    return sorted(result)


def _period_start(value: date, scale: str) -> date:
    if scale == "year":
        return date(value.year, 1, 1)
    if scale == "month":
        return date(value.year, value.month, 1)
    return value


def _next_period(value: date, scale: str) -> date:
    if scale == "year":
        return date(value.year + 1, 1, 1)
    if scale == "month":
        if value.month == 12:
            return date(value.year + 1, 1, 1)
        return date(value.year, value.month + 1, 1)
    return value + timedelta(days=1)


def _date_from_filename(path: Path) -> date:
    match = PRODUCT_DATE_PATTERN.search(path.name)
    if not match:
        raise ValueError(f"Cannot determine product date from filename: {path.name}")
    return date.fromisoformat(match.group("date"))


def _as_date(value) -> date:
    if isinstance(value, np.datetime64):
        return date.fromisoformat(np.datetime_as_string(value, unit="D"))
    return date.fromisoformat(str(value)[:10])


def _resolve_path(raw_path: str, task_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (task_path.parent / path).resolve()
