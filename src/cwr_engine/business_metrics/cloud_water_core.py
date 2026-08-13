from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water import (
    ANNUAL_METRIC_NAMES,
    BOUNDARY_COMPONENTS,
    DIRECT_ANNUAL_SOURCE_VARIABLES,
    DIRECT_MONTHLY_SOURCE_VARIABLES,
    MONTHLY_METRIC_NAMES,
    SEASON_MONTHS,
    _aggregate_direct_product,
    _boundary_metrics,
    _compile_direct_mask,
    _direct_spatial_composite,
    _discover_direct_product_files,
    _load_direct_product,
    _number,
    _validate_product_grid,
)


@dataclass(frozen=True)
class CloudWaterYearResult:
    year: int
    annual_record: dict[str, Any]
    monthly_records: dict[int, dict[str, Any]]
    seasons: dict[str, dict[str, Any]]
    spatial: xr.Dataset
    mask: xr.DataArray
    reference_grid: xr.Dataset
    annual_product: Path
    monthly_products: dict[int, Path]


def derive_cloud_water_year(
    product_source: dict[str, Any],
    region_spec: dict[str, Any],
    year: int,
    *,
    reference_grid: xr.Dataset | None = None,
    mask: xr.DataArray | None = None,
) -> CloudWaterYearResult:
    if (reference_grid is None) != (mask is None):
        raise ValueError("reference_grid and mask must be provided together")
    annual_path, monthly_paths = _discover_direct_product_files(
        product_source,
        year,
    )
    annual_dataset = _load_direct_product(
        annual_path,
        product_source,
        DIRECT_ANNUAL_SOURCE_VARIABLES,
    )
    if reference_grid is None:
        reference_grid = annual_dataset
        mask = _compile_direct_mask(
            region_spec,
            annual_dataset["lat"].values,
            annual_dataset["lon"].values,
        )
    else:
        _validate_product_grid(reference_grid, annual_dataset)
    if mask is None or not bool(mask.any().item()):
        raise ValueError("Compiled cloud-water mask contains no grid cells")

    annual_raw = _aggregate_direct_product(
        annual_dataset,
        mask,
        year,
        month=None,
    )
    monthly_datasets: dict[int, xr.Dataset] = {}
    monthly_records: dict[int, dict[str, Any]] = {}
    for month, product_path in monthly_paths.items():
        dataset = _load_direct_product(
            product_path,
            product_source,
            DIRECT_MONTHLY_SOURCE_VARIABLES,
        )
        _validate_product_grid(reference_grid, dataset)
        monthly_datasets[month] = dataset
        monthly_records[month] = _monthly_record(
            month,
            _aggregate_direct_product(dataset, mask, year, month=month),
            annual_raw["dxy"],
        )
    spatial = _direct_spatial_composite(
        annual_dataset,
        monthly_datasets,
        mask,
    )
    return CloudWaterYearResult(
        year=year,
        annual_record=_annual_record(year, annual_raw),
        monthly_records=monthly_records,
        seasons=_seasons(monthly_records),
        spatial=spatial,
        mask=mask,
        reference_grid=reference_grid,
        annual_product=annual_path,
        monthly_products=monthly_paths,
    )


def _annual_record(year: int, source: dict[str, Any]) -> dict[str, Any]:
    dxy = _number(source, "dxy")
    if np.isclose(dxy, 0):
        raise ValueError(f"Annual dxy must not be zero for {year}")
    values = {name: _number(source, name) for name in ANNUAL_METRIC_NAMES}
    return {
        "year": year,
        "values": values,
        "equivalent_depth_mm": {
            name: values[name] / dxy
            for name in ("GMv", "GMh", "SP", "CWR", "MC")
        },
        "boundaries": {
            name: _boundary_metrics(source, incoming, outgoing)
            for name, (incoming, outgoing) in BOUNDARY_COMPONENTS.items()
        },
    }


def _monthly_record(
    month: int,
    source: dict[str, Any],
    annual_dxy: Any,
) -> dict[str, Any]:
    dxy = float(annual_dxy)
    if not math.isfinite(dxy) or np.isclose(dxy, 0):
        raise ValueError("annual dxy must be finite and non-zero")
    values = {name: _number(source, name) for name in MONTHLY_METRIC_NAMES}
    return {
        "month": month,
        **values,
        "dxy": _number(source, "dxy"),
        "GMv_mm": values["GMv"] / dxy,
        "GMh_mm": values["GMh"] / dxy,
        "MC_mm": values["MC"] / dxy,
        "CWR_mm": values["CWR"] / dxy,
        "SP_mm": values["SP"] / dxy,
    }


def _seasons(
    monthly: dict[int, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    return {
        season: {
            "months": months,
            "SP_mm": sum(monthly[month]["SP_mm"] for month in months),
            "CWR_mm": sum(monthly[month]["CWR_mm"] for month in months),
        }
        for season, months in SEASON_MONTHS.items()
    }
