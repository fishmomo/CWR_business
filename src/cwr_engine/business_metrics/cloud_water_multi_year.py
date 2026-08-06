from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
from scipy.stats import kendalltau, theilslopes
import xarray as xr

from cwr_engine.business_metrics.cloud_water import (
    ANNUAL_VARIABLES,
    BOUNDARY_COMPONENTS,
    DIRECT_ANNUAL_SOURCE_VARIABLES,
    DIRECT_MONTHLY_SOURCE_VARIABLES,
    SEASON_MONTHS,
    _aggregate_direct_product,
    _boundary_metrics,
    _compile_direct_mask,
    _direct_spatial_composite,
    _discover_direct_product_files,
    _load_direct_product,
    _path,
    _product_source,
    _region_spec,
    _required_text,
    _validate_product_grid,
)
from cwr_engine.business_metrics.cloud_water_multi_year_figures import (
    IMAGE_SLOTS,
    render_cloud_water_multi_year_figures,
)


PROFILE_NAME = "cloud_water_multi_year"
ANNUAL_METRIC_NAMES = [*ANNUAL_VARIABLES, "MC", "CEv"]
MONTHLY_METRIC_NAMES = [
    "GMv",
    "GMh",
    "MC",
    "CWR",
    "SP",
    "CEv",
    "PEh",
    "RCh",
]
SEASON_ORDER = ["spring", "summer", "autumn", "winter"]


@dataclass(frozen=True)
class CloudWaterMultiYearMetricsSpec:
    task_id: str
    start_year: int
    end_year: int
    region_name: str
    product_source: dict[str, Any]
    region_spec: dict[str, Any]
    output_root: Path
    artifact_name: str


def build_cloud_water_multi_year_business_metrics(spec_path: Path) -> Path:
    spec = load_cloud_water_multi_year_metrics_spec(spec_path)
    metrics, spatial = derive_cloud_water_multi_year_business_metrics(spec)
    targets = _artifact_targets(spec)

    spec.output_root.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="cwr-multi-year-metrics-",
        dir=spec.output_root.parent,
    ) as raw_temp:
        temp = Path(raw_temp)
        temp_metrics = temp / targets["metrics"].name
        temp_spatial = temp / targets["spatial"].name
        temp_report_inputs = temp / targets["report_inputs"].name
        temp_figures = {
            slot: temp / targets[f"figure_{index}"].name
            for index, slot in enumerate(IMAGE_SLOTS, start=1)
        }
        temp_metrics.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        spatial.to_netcdf(temp_spatial, engine="scipy")
        render_cloud_water_multi_year_figures(
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
            temp_figures[slot].replace(targets[f"figure_{index}"])
        temp_report_inputs.replace(targets["report_inputs"])
    return targets["report_inputs"]


def load_cloud_water_multi_year_metrics_spec(
    path: Path,
) -> CloudWaterMultiYearMetricsSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("metric_profile") != PROFILE_NAME:
        raise ValueError(f"metric_profile must be {PROFILE_NAME}")
    start_year = _year(payload, "start_year")
    end_year = _year(payload, "end_year")
    if end_year < start_year:
        raise ValueError("end_year must not be earlier than start_year")
    if end_year - start_year + 1 < 5:
        raise ValueError("Multi-year report requires at least five years")
    base = path.parent
    artifact_name = payload.get("artifact_name", PROFILE_NAME)
    if (
        not isinstance(artifact_name, str)
        or not artifact_name.strip()
        or Path(artifact_name).name != artifact_name
    ):
        raise ValueError("artifact_name must be a non-empty filename stem")
    return CloudWaterMultiYearMetricsSpec(
        task_id=_required_text(payload, "task_id"),
        start_year=start_year,
        end_year=end_year,
        region_name=_required_text(payload, "region_name"),
        product_source=_product_source(base, payload.get("product_source")),
        region_spec=_region_spec(base, payload.get("region_spec")),
        output_root=_path(base, payload, "output_root"),
        artifact_name=artifact_name,
    )


def derive_cloud_water_multi_year_business_metrics(
    spec: CloudWaterMultiYearMetricsSpec,
) -> tuple[dict[str, Any], xr.Dataset]:
    years = list(range(spec.start_year, spec.end_year + 1))
    discovered = {
        year: _discover_direct_product_files(spec.product_source, year)
        for year in years
    }
    first_annual = _load_direct_product(
        discovered[years[0]][0],
        spec.product_source,
        DIRECT_ANNUAL_SOURCE_VARIABLES,
    )
    mask = _compile_direct_mask(
        spec.region_spec,
        first_annual["lat"].values,
        first_annual["lon"].values,
    )
    if not bool(mask.any().item()):
        raise ValueError("Compiled multi-year mask contains no grid cells")

    annual_series: list[dict[str, Any]] = []
    monthly_by_year: dict[int, dict[int, dict[str, Any]]] = {}
    spatial_by_year: list[xr.Dataset] = []
    annual_sources: list[str] = []
    monthly_sources: list[str] = []
    for year in years:
        annual_path, monthly_paths = discovered[year]
        annual_dataset = (
            first_annual
            if year == years[0]
            else _load_direct_product(
                annual_path,
                spec.product_source,
                DIRECT_ANNUAL_SOURCE_VARIABLES,
            )
        )
        _validate_product_grid(first_annual, annual_dataset)
        annual_raw = _aggregate_direct_product(
            annual_dataset,
            mask,
            year,
            month=None,
        )
        annual_series.append(_annual_record(year, annual_raw))
        annual_sources.append(str(annual_path))

        month_datasets: dict[int, xr.Dataset] = {}
        month_records: dict[int, dict[str, Any]] = {}
        for month, month_path in monthly_paths.items():
            dataset = _load_direct_product(
                month_path,
                spec.product_source,
                DIRECT_MONTHLY_SOURCE_VARIABLES,
            )
            _validate_product_grid(first_annual, dataset)
            month_datasets[month] = dataset
            month_records[month] = _monthly_record(
                month,
                _aggregate_direct_product(
                    dataset,
                    mask,
                    year,
                    month=month,
                ),
                annual_raw["dxy"],
            )
            monthly_sources.append(str(month_path))
        monthly_by_year[year] = month_records
        spatial_by_year.append(
            _direct_spatial_composite(annual_dataset, month_datasets, mask)
        )

    _validate_dxy(annual_series)
    monthly_climatology = _monthly_climatology(years, monthly_by_year)
    seasonal_climatology = _seasonal_climatology(years, monthly_by_year)
    mean_record = _multi_year_mean(annual_series)
    boundaries = _mean_boundaries(annual_series)
    interannual = {
        name: _interannual_summary(annual_series, name)
        for name in ("GMh", "SP", "CWR")
    }
    spatial = _multi_year_spatial(spatial_by_year, mask)
    metrics = {
        "schema_version": 1,
        "kind": "business_metrics",
        "metric_profile": PROFILE_NAME,
        "task_id": spec.task_id,
        "region_name": spec.region_name,
        "start_year": spec.start_year,
        "end_year": spec.end_year,
        "year_count": len(years),
        "source": {
            "mode": "product_catalog",
            "root": str(spec.product_source["root"]),
            "annual_product_count": len(annual_sources),
            "monthly_product_count": len(monthly_sources),
            "annual_products": annual_sources,
            "monthly_products": monthly_sources,
            "region_kind": spec.region_spec["kind"],
        },
        "units": {
            "mass": "kg",
            "equivalent_depth": "mm",
            "boundary_mass": "1e11 kg/year",
            "trend_relative_slope": "%/year",
        },
        "annual_series": annual_series,
        "multi_year_mean": mean_record,
        "monthly_climatology": monthly_climatology,
        "seasonal_climatology": seasonal_climatology,
        "boundaries": boundaries,
        "interannual": interannual,
        "spatial_composite": {
            "artifact_name": spec.artifact_name,
            "mask_variable": "ind_area_bool",
            "variables": list(spatial.data_vars),
        },
    }
    return metrics, spatial


def _annual_record(year: int, source: dict[str, Any]) -> dict[str, Any]:
    dxy = _finite_number(source["dxy"], "dxy")
    if np.isclose(dxy, 0):
        raise ValueError(f"Annual dxy must not be zero for {year}")
    values = {
        name: _finite_number(source[name], name)
        for name in ANNUAL_METRIC_NAMES
    }
    boundaries = {
        name: _boundary_metrics(source, incoming, outgoing)
        for name, (incoming, outgoing) in BOUNDARY_COMPONENTS.items()
    }
    return {
        "year": year,
        "values": values,
        "equivalent_depth_mm": {
            name: values[name] / dxy
            for name in ("GMv", "GMh", "SP", "CWR", "MC")
        },
        "boundaries": boundaries,
    }


def _monthly_record(
    month: int,
    source: dict[str, Any],
    annual_dxy: Any,
) -> dict[str, Any]:
    dxy = _finite_number(annual_dxy, "annual dxy")
    values = {
        name: _finite_number(source[name], name)
        for name in MONTHLY_METRIC_NAMES
    }
    return {
        "month": month,
        **values,
        "GMv_mm": values["GMv"] / dxy,
        "GMh_mm": values["GMh"] / dxy,
        "MC_mm": values["MC"] / dxy,
        "CWR_mm": values["CWR"] / dxy,
        "SP_mm": values["SP"] / dxy,
    }


def _multi_year_mean(records: list[dict[str, Any]]) -> dict[str, Any]:
    value_names = records[0]["values"]
    depth_names = records[0]["equivalent_depth_mm"]
    return {
        "values": {
            name: _mean([row["values"][name] for row in records])
            for name in value_names
        },
        "equivalent_depth_mm": {
            name: _mean(
                [row["equivalent_depth_mm"][name] for row in records]
            )
            for name in depth_names
        },
    }


def _monthly_climatology(
    years: list[int],
    monthly: dict[int, dict[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    records = []
    for month in range(1, 13):
        rows = [monthly[year][month] for year in years]
        keys = [key for key in rows[0] if key != "month"]
        records.append(
            {
                "month": month,
                **{key: _mean([row[key] for row in rows]) for key in keys},
            }
        )
    return records


def _seasonal_climatology(
    years: list[int],
    monthly: dict[int, dict[int, dict[str, Any]]],
) -> list[dict[str, Any]]:
    records = []
    for season in SEASON_ORDER:
        months = SEASON_MONTHS[season]
        yearly_sp = [
            sum(monthly[year][month]["SP_mm"] for month in months)
            for year in years
        ]
        yearly_cwr = [
            sum(monthly[year][month]["CWR_mm"] for month in months)
            for year in years
        ]
        records.append(
            {
                "season": season,
                "months": months,
                "SP_mm": _mean(yearly_sp),
                "CWR_mm": _mean(yearly_cwr),
            }
        )
    return records


def _mean_boundaries(
    annual_series: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for component in BOUNDARY_COMPONENTS:
        names = ["west", "east", "south", "north", "total"]
        rows = []
        for name in names:
            matches = [
                next(
                    row
                    for row in annual["boundaries"][component]
                    if row["boundary"] == name
                )
                for annual in annual_series
            ]
            rows.append(
                {
                    "boundary": name,
                    "input": _mean([row["input"] for row in matches]),
                    "output": _mean([row["output"] for row in matches]),
                    "net_input": _mean(
                        [row["net_input"] for row in matches]
                    ),
                }
            )
        result[component] = rows
    return result


def _interannual_summary(
    annual_series: list[dict[str, Any]],
    variable: str,
) -> dict[str, Any]:
    years = np.asarray([row["year"] for row in annual_series], dtype=int)
    mass = np.asarray(
        [row["values"][variable] / 1e11 for row in annual_series],
        dtype=float,
    )
    depth = np.asarray(
        [row["equivalent_depth_mm"][variable] for row in annual_series],
        dtype=float,
    )
    return {
        "series": [
            {"year": int(year), "mass_1e11_kg": float(m), "depth_mm": float(d)}
            for year, m, d in zip(years, mass, depth)
        ],
        "mass_range_1e11_kg": {
            "min": float(mass.min()),
            "max": float(mass.max()),
        },
        "depth_range_mm": {
            "min": float(depth.min()),
            "max": float(depth.max()),
        },
        "extrema": _extrema(years, mass),
        "trend": _trend(years, depth),
    }


def _extrema(years: np.ndarray, values: np.ndarray) -> dict[str, Any]:
    displayed = np.round(values.astype(float), 1)
    distinct = np.unique(displayed)
    low = distinct[0]
    high = distinct[-1]
    second_low = distinct[1] if len(distinct) > 1 else low
    second_high = distinct[-2] if len(distinct) > 1 else high

    def record(value: float) -> dict[str, Any]:
        return {
            "display_value": float(value),
            "years": [
                int(year)
                for year, item in zip(years, displayed)
                if item == value
            ],
        }

    return {
        "maximum": record(high),
        "second_maximum": record(second_high),
        "minimum": record(low),
        "second_minimum": record(second_low),
    }


def _trend(years: np.ndarray, values: np.ndarray) -> dict[str, Any]:
    if np.allclose(values, values[0]):
        tau, p_value, slope = 0.0, 1.0, 0.0
    else:
        result = kendalltau(years, values, method="auto", variant="b")
        tau = float(result.statistic)
        p_value = float(result.pvalue)
        slope = float(theilslopes(values, years).slope)
    mean = float(np.mean(values))
    relative = 0.0 if np.isclose(mean, 0) else slope / mean * 100
    significant = bool(p_value < 0.05 and not np.isclose(slope, 0))
    if np.isclose(slope, 0):
        wording = "基本稳定"
        direction = "stable"
    elif slope > 0:
        wording = "显著增加" if significant else "增加"
        direction = "increase"
    else:
        wording = "显著下降" if significant else "下降"
        direction = "decrease"
    return {
        "method": "mann_kendall_theil_sen",
        "tau": tau,
        "p_value": p_value,
        "slope_per_year": slope,
        "relative_slope_percent_per_year": relative,
        "significant": significant,
        "direction": direction,
        "wording": wording,
    }


def _multi_year_spatial(
    datasets: list[xr.Dataset],
    mask: xr.DataArray,
) -> xr.Dataset:
    for dataset in datasets[1:]:
        if not np.array_equal(
            dataset["ind_area_bool"].values,
            mask.values,
        ):
            raise ValueError("Multi-year products produced incompatible masks")

    def average(name: str) -> xr.DataArray:
        return xr.concat(
            [dataset[name] for dataset in datasets],
            dim="year",
        ).mean("year")

    spatial = xr.Dataset(
        {
            "annual_mean_gmv_mm": average("pic3_a"),
            "annual_mean_cev_percent": average("pic3_b"),
            "annual_mean_cwr_mm": average("pic3_c"),
            "annual_mean_gmh_mm": average("pic3_d"),
            "annual_mean_sp_mm": average("pic3_e"),
            "annual_mean_peh_percent": average("pic3_f"),
            "seasonal_mean_sp_mm": xr.concat(
                [average(f"pic4_{suffix}") for suffix in "abcd"],
                dim=xr.IndexVariable("season", SEASON_ORDER),
            ),
            "seasonal_mean_cwr_mm": xr.concat(
                [average(f"pic5_{suffix}") for suffix in "abcd"],
                dim=xr.IndexVariable("season", SEASON_ORDER),
            ),
            "ind_area_bool": mask,
        }
    )
    spatial.attrs.update(
        {
            "schema_version": 1,
            "metric_profile": PROFILE_NAME,
            "aggregation": "derive_each_period_then_equal_weight_mean",
        }
    )
    return spatial


def _validate_dxy(records: list[dict[str, Any]]) -> None:
    reference = float(records[0]["values"]["dxy"])
    if any(
        not np.isclose(float(row["values"]["dxy"]), reference)
        for row in records[1:]
    ):
        raise ValueError("Regional dxy is incompatible across selected years")


def _artifact_targets(
    spec: CloudWaterMultiYearMetricsSpec,
) -> dict[str, Path]:
    targets = {
        "metrics": spec.output_root / "business_metrics" / f"{spec.artifact_name}.json",
        "spatial": spec.output_root / "spatial_composite" / f"{spec.artifact_name}.nc",
        "report_inputs": spec.output_root / "report_inputs" / "report_inputs.json",
    }
    targets.update(
        {
            f"figure_{index}": spec.output_root / "profile_image" / f"{slot}.png"
            for index, slot in enumerate(IMAGE_SLOTS, start=1)
        }
    )
    return targets


def _report_inputs_payload(
    spec: CloudWaterMultiYearMetricsSpec,
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
    artifacts.extend(
        {
            "kind": "profile_image",
            "name": slot,
            "metric_profile": PROFILE_NAME,
            "schema_version": 1,
            "path": str(targets[f"figure_{index}"]),
        }
        for index, slot in enumerate(IMAGE_SLOTS, start=1)
    )
    steps = ["business_metrics", "profile_figures", "report_inputs"]
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
                {
                    "scale": "year_range",
                    "start_year": spec.start_year,
                    "end_year": spec.end_year,
                    "label": f"{spec.start_year}-{spec.end_year}",
                }
            ],
            "region_name": spec.region_name,
        },
        "artifacts": artifacts,
        "runtime": {
            "workflow_steps": steps,
            "executed_steps": steps,
            "used_cache": [],
        },
        "stats": [],
    }


def _year(payload: dict[str, Any], key: str) -> int:
    value = payload.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


def _mean(values: list[Any]) -> float:
    array = np.asarray(values, dtype=float)
    if not np.all(np.isfinite(array)):
        raise ValueError("Multi-year mean contains non-finite values")
    return float(array.mean())


def _finite_number(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric value for {name}") from error
    if not math.isfinite(number):
        raise ValueError(f"Non-finite numeric value for {name}")
    return number
