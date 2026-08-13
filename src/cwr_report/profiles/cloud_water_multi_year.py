from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
from typing import Any

from docx import Document
import numpy as np
import xarray as xr

from cwr_engine.business_metrics.cloud_water_multi_year_figures import (
    IMAGE_SLOTS,
)
from cwr_report.assembler import build_report
from cwr_report.profiles.cloud_water_shared import (
    derive_boundary_tables,
    derive_scalar_text,
    image_width_overrides,
    seasonal_spatial_text,
    spatial_description,
    template_slots,
)


PROFILE_NAME = "cloud_water_multi_year"
SEASONS = ["春季", "夏季", "秋季", "冬季"]
SEASON_KEYS = ["spring", "summer", "autumn", "winter"]


@dataclass(frozen=True)
class CloudWaterMultiYearProfileSpec:
    report_id: str
    start_year: int
    end_year: int
    region_name: str
    report_inputs: Path
    business_metrics: Path
    spatial_nc: Path
    template: Path
    output: Path
    images: dict[str, Path]
    image_width_inches: float
    image_widths_inches: dict[str, float]


@dataclass(frozen=True)
class CloudWaterMultiYearProfileData:
    text_values: dict[str, str]
    vapor_table: list[dict[str, str]]
    hydrometeor_table: list[dict[str, str]]


def build_cloud_water_multi_year_report(spec_path: Path) -> Path:
    spec = load_cloud_water_multi_year_profile_spec(spec_path)
    metrics = _load_metrics(spec.business_metrics)
    data = derive_cloud_water_multi_year_profile_data(spec, metrics)
    with tempfile.TemporaryDirectory(prefix="cwr-multi-year-profile-") as raw_temp:
        temp = Path(raw_temp)
        generated_inputs = temp / "report_inputs.json"
        generated_spec = temp / "report_spec.json"
        stats = [
            {**row, "profile_table": "water_vapor"}
            for row in data.vapor_table
        ] + [
            {**row, "profile_table": "hydrometeor"}
            for row in data.hydrometeor_table
        ]
        generated_inputs.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "task": {
                        "task_id": spec.report_id,
                        "status": "success",
                        "output_root": str(spec.output.parent),
                    },
                    "inputs": {
                        "profile": PROFILE_NAME,
                        "standard_report_inputs": str(spec.report_inputs),
                        "start_year": spec.start_year,
                        "end_year": spec.end_year,
                        "region_name": spec.region_name,
                    },
                    "artifacts": [
                        {
                            "kind": "profile_image",
                            "name": slot,
                            "path": str(spec.images[slot]),
                        }
                        for slot in IMAGE_SLOTS
                    ],
                    "runtime": {},
                    "stats": stats,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        generated_spec.write_text(
            json.dumps(
                _generic_report_spec(spec, data, generated_inputs),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return build_report(generated_spec)


def load_cloud_water_multi_year_profile_spec(
    path: Path,
) -> CloudWaterMultiYearProfileSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("profile") != PROFILE_NAME:
        raise ValueError(f"profile must be {PROFILE_NAME}")
    base = path.parent
    report_inputs = _existing_path(base, payload.get("report_inputs"), "report_inputs")
    indexed = _standardized_inputs(report_inputs)
    template = _existing_path(base, payload.get("template"), "template")
    output = _path(base, payload, "output")
    if output.suffix.lower() != ".docx":
        raise ValueError("output must use the .docx suffix")
    if output.resolve() == template.resolve():
        raise ValueError("output must not overwrite the template")
    width = payload.get("image_width_inches", 4.0)
    if (
        not isinstance(width, (int, float))
        or isinstance(width, bool)
        or width <= 0
    ):
        raise ValueError("image_width_inches must be positive")
    width_overrides = image_width_overrides(
        payload.get("image_widths_inches", {}),
        IMAGE_SLOTS,
    )
    return CloudWaterMultiYearProfileSpec(
        report_id=indexed["task_id"],
        start_year=indexed["start_year"],
        end_year=indexed["end_year"],
        region_name=indexed["region_name"],
        report_inputs=report_inputs,
        business_metrics=indexed["metrics"],
        spatial_nc=indexed["spatial"],
        template=template,
        output=output,
        images=indexed["images"],
        image_width_inches=float(width),
        image_widths_inches=width_overrides,
    )


def derive_cloud_water_multi_year_profile_data(
    spec: CloudWaterMultiYearProfileSpec,
    metrics: dict[str, Any],
) -> CloudWaterMultiYearProfileData:
    annual = _mean_annual_row(metrics)
    months = {
        int(row["month"]): row for row in metrics["monthly_climatology"]
    }
    common = derive_scalar_text(
        SimpleNamespace(year=spec.end_year, region_name=spec.region_name),
        annual,
        months,
    )
    values = {
        key: value
        for key, value in common.items()
        if key not in {"year_which", "PEv_values", "PEw_values"}
    }
    values.update(
        {
            "first_year": str(spec.start_year),
            "last_year": str(spec.end_year),
            "year_period": str(spec.end_year - spec.start_year + 1),
            "region_name": spec.region_name,
            "CEv_values": _format(metrics["multi_year_mean"]["values"]["CEv"]),
        }
    )
    values.update(_monthly_tie_text(metrics))
    values.update(_interannual_text(metrics))
    values.update(_spatial_text(spec.spatial_nc))
    vapor_table, hydrometeor_table = derive_boundary_tables(annual)
    required = template_slots(spec.template) - set(IMAGE_SLOTS) - {
        "table_for_TFdatav",
        "table_for_TFdatah",
    }
    missing = sorted(required - set(values))
    if missing:
        raise ValueError(f"Multi-year profile cannot populate slot: {missing[0]}")
    return CloudWaterMultiYearProfileData(
        text_values={key: str(value) for key, value in values.items()},
        vapor_table=vapor_table,
        hydrometeor_table=hydrometeor_table,
    )


def _mean_annual_row(metrics: dict[str, Any]) -> dict[str, Any]:
    row = {
        "time": f"{metrics['start_year']}-01-01",
        **metrics["multi_year_mean"]["values"],
    }
    prefixes = {
        "water_vapor": ("INv", "OTv"),
        "hydrometeor": ("INh", "OTh"),
    }
    sides = {"west": "W", "east": "E", "south": "S", "north": "N"}
    for component, (incoming, outgoing) in prefixes.items():
        records = {
            item["boundary"]: item
            for item in metrics["boundaries"][component]
        }
        for boundary, side in sides.items():
            row[f"{incoming}_{side}"] = records[boundary]["input"] * 1e11
            row[f"{outgoing}_{side}"] = records[boundary]["output"] * 1e11
    return row


def _monthly_tie_text(metrics: dict[str, Any]) -> dict[str, str]:
    monthly = metrics["monthly_climatology"]
    labels = [str(int(row["month"])) for row in monthly]
    sp = np.asarray([row["SP_mm"] for row in monthly], dtype=float)
    cwr = np.asarray([row["CWR_mm"] for row in monthly], dtype=float)
    sp_ranks = _rank_labels(sp, labels)
    cwr_ranks = _rank_labels(cwr, labels)
    seasons = metrics["seasonal_climatology"]
    season_labels = [SEASONS[SEASON_KEYS.index(row["season"])] for row in seasons]
    sp_seasons = _ordered_groups(
        np.asarray([row["SP_mm"] for row in seasons], dtype=float),
        season_labels,
    )
    cwr_seasons = _ordered_groups(
        np.asarray([row["CWR_mm"] for row in seasons], dtype=float),
        season_labels,
    )
    values = {
        "SP_max_month": sp_ranks["maximum"],
        "SP_min_month": sp_ranks["minimum"],
        "CWR_maximum_month": cwr_ranks["maximum"],
        "CWR_second_maximum_month": cwr_ranks["second_maximum"],
        "CWR_minimum_month": cwr_ranks["minimum"],
        "CWR_second_minimum_month": cwr_ranks["second_minimum"],
    }
    for index in range(4):
        values[f"SP_season_{index + 1}"] = sp_seasons[index]
        values[f"CWR_season_{index + 1}"] = cwr_seasons[index]
    return values


def _rank_labels(values: np.ndarray, labels: list[str]) -> dict[str, str]:
    rounded = np.round(values, 1)
    distinct = np.unique(rounded)
    low, high = distinct[0], distinct[-1]
    second_low = distinct[1] if len(distinct) > 1 else low
    second_high = distinct[-2] if len(distinct) > 1 else high

    def joined(value: float) -> str:
        return "、".join(
            label for label, item in zip(labels, rounded) if item == value
        )

    return {
        "maximum": joined(high),
        "second_maximum": joined(second_high),
        "minimum": joined(low),
        "second_minimum": joined(second_low),
    }


def _ordered_groups(values: np.ndarray, labels: list[str]) -> list[str]:
    rounded = np.round(values, 1)
    groups = []
    for value in sorted(np.unique(rounded), reverse=True):
        groups.append(
            "、".join(
                label for label, item in zip(labels, rounded) if item == value
            )
        )
    while len(groups) < 4:
        groups.append(groups[-1])
    return groups[:4]


def _interannual_text(metrics: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for variable in ("GMh", "SP", "CWR"):
        summary = metrics["interannual"][variable]
        extrema = summary["extrema"]
        result[f"{variable}_maximum_year"] = _years(
            extrema["maximum"]["years"]
        )
        result[f"{variable}_second_maximum_year"] = _years(
            extrema["second_maximum"]["years"]
        )
        result[f"{variable}_minimum_year"] = _years(
            extrema["minimum"]["years"]
        )
        second_minimum_key = f"{variable}_second_minimum_year"
        result[second_minimum_key] = _years(
            extrema["second_minimum"]["years"]
        )
        result[f"{variable}_trend"] = summary["trend"]["wording"]
    for variable in ("GMh", "SP"):
        summary = metrics["interannual"][variable]
        result[f"{variable}_Kg_min"] = _format(
            summary["mass_range_1e11_kg"]["min"]
        )
        result[f"{variable}_Kg_max"] = _format(
            summary["mass_range_1e11_kg"]["max"]
        )
        result[f"{variable}_mm_min"] = _format(
            summary["depth_range_mm"]["min"]
        )
        result[f"{variable}_mm_max"] = _format(
            summary["depth_range_mm"]["max"]
        )
    return result


def _spatial_text(path: Path) -> dict[str, str]:
    with xr.open_dataset(path, engine="scipy") as opened:
        dataset = opened.load()
    mask = dataset["ind_area_bool"].values.astype(bool)
    annual = {
        "pic4_a": "annual_mean_gmv_mm",
        "pic4_b": "annual_mean_cev_percent",
        "pic4_c": "annual_mean_cwr_mm",
        "pic4_e": "annual_mean_sp_mm",
        "pic4_f": "annual_mean_peh_percent",
    }
    result = {
        slot: spatial_description(dataset, variable, mask)
        for slot, variable in annual.items()
    }
    seasonal = xr.Dataset(
        {
            **{
                f"pic5_{chr(ord('a') + index)}": dataset[
                    "seasonal_mean_sp_mm"
                ].sel(season=season, drop=True)
                for index, season in enumerate(SEASON_KEYS)
            },
            **{
                f"pic6_{chr(ord('a') + index)}": dataset[
                    "seasonal_mean_cwr_mm"
                ].sel(season=season, drop=True)
                for index, season in enumerate(SEASON_KEYS)
            },
        },
        coords={"lat": dataset["lat"], "lon": dataset["lon"]},
    )
    result.update(
        seasonal_spatial_text(
            seasonal,
            mask,
            [f"pic5_{suffix}" for suffix in "abcd"],
            "pic5",
        )
    )
    result.update(
        seasonal_spatial_text(
            seasonal,
            mask,
            [f"pic6_{suffix}" for suffix in "abcd"],
            "pic6",
        )
    )
    return result


def _generic_report_spec(
    spec: CloudWaterMultiYearProfileSpec,
    data: CloudWaterMultiYearProfileData,
    report_inputs: Path,
) -> dict[str, Any]:
    template_slot_names = template_slots(spec.template)
    block_slots = set(IMAGE_SLOTS) | {
        "table_for_TFdatav",
        "table_for_TFdatah",
    }
    text_slots = template_slot_names - block_slots
    columns = [
        {"field": "边界名称", "title": "边界名称"},
        {"field": "输入", "title": "输入"},
        {"field": "输出", "title": "输出"},
        {"field": "净输入", "title": "净输入"},
    ]
    table_base = {
        "source": "stats",
        "columns": columns,
        "column_widths": [2100, 2070, 2070, 2070],
        "style": "Normal Table",
        "border_mode": "three_line",
    }
    return {
        "report_id": spec.report_id,
        "report_inputs": str(report_inputs),
        "template": str(spec.template),
        "output": str(spec.output),
        "text_slots": {
            slot: data.text_values[slot] for slot in sorted(text_slots)
        },
        "narrative_slots": {},
        "table_slots": {
            "table_for_TFdatav": {
                **table_base,
                "filters": {"profile_table": "water_vapor"},
            },
            "table_for_TFdatah": {
                **table_base,
                "filters": {"profile_table": "hydrometeor"},
            },
        },
        "image_slots": {
            slot: {
                "selector": {"kind": "profile_image", "name": slot},
                "width_inches": spec.image_widths_inches.get(
                    slot,
                    spec.image_width_inches,
                ),
                "alt_text": (
                    f"{spec.start_year}-{spec.end_year}年"
                    f"{spec.region_name}{slot}"
                ),
            }
            for slot in IMAGE_SLOTS
        },
    }


def _standardized_inputs(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version", 1) != 1:
        raise ValueError("Unsupported report_inputs schema version")
    if payload.get("task", {}).get("status") != "success":
        raise ValueError("report_inputs task status must be success")
    artifacts = payload.get("artifacts", [])
    metrics_records = _records(artifacts, "business_metrics")
    spatial_records = _records(artifacts, "spatial_composite")
    image_records = _records(artifacts, "profile_image")
    if len(metrics_records) != 1 or len(spatial_records) != 1:
        raise ValueError(
            "report_inputs must index one multi-year metrics and spatial artifact"
        )
    names = [record.get("name") for record in image_records]
    if len(image_records) != 6 or set(names) != set(IMAGE_SLOTS):
        raise ValueError("report_inputs must index exactly six multi-year images")
    metrics_path = _artifact_path(path, metrics_records[0])
    metrics = _load_metrics(metrics_path)
    return {
        "task_id": str(metrics["task_id"]),
        "start_year": int(metrics["start_year"]),
        "end_year": int(metrics["end_year"]),
        "region_name": str(metrics["region_name"]),
        "metrics": metrics_path,
        "spatial": _artifact_path(path, spatial_records[0]),
        "images": {
            slot: _artifact_path(
                path,
                next(record for record in image_records if record["name"] == slot),
            )
            for slot in IMAGE_SLOTS
        },
    }


def _records(artifacts: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [
        item
        for item in artifacts
        if item.get("kind") == kind
        and item.get("metric_profile") == PROFILE_NAME
    ]


def _load_metrics(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported multi-year business_metrics schema")
    if payload.get("metric_profile") != PROFILE_NAME:
        raise ValueError(f"business_metrics metric_profile must be {PROFILE_NAME}")
    if payload.get("year_count", 0) < 5:
        raise ValueError("Multi-year business_metrics requires at least five years")
    if len(payload.get("annual_series", [])) != payload["year_count"]:
        raise ValueError("annual_series count does not match year_count")
    if len(payload.get("monthly_climatology", [])) != 12:
        raise ValueError("monthly_climatology must contain twelve months")
    if len(payload.get("seasonal_climatology", [])) != 4:
        raise ValueError("seasonal_climatology must contain four seasons")
    return payload


def _artifact_path(report_inputs: Path, artifact: dict[str, Any]) -> Path:
    raw = artifact.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Indexed artifact path must be non-empty")
    path = Path(raw)
    candidates = [path] if path.is_absolute() else [
        report_inputs.parent / path,
        report_inputs.parent.parent / path,
    ]
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise ValueError(f"Indexed artifact does not exist: {raw}")


def _years(values: list[int]) -> str:
    return "、".join(str(int(value)) for value in values)


def _format(value: Any) -> str:
    return f"{float(value):.1f}"


def _path(base: Path, payload: dict[str, Any], key: str) -> Path:
    raw = payload.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{key} must be a non-empty path")
    path = Path(raw)
    return path if path.is_absolute() else (base / path).resolve()


def _existing_path(base: Path, raw: Any, key: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"{key} must be a non-empty path")
    path = Path(raw)
    resolved = path if path.is_absolute() else (base / path).resolve()
    if not resolved.is_file():
        raise ValueError(f"{key} does not exist: {resolved}")
    return resolved
