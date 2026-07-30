from __future__ import annotations

import csv
from dataclasses import dataclass
import json
import math
from pathlib import Path
import tempfile
from typing import Any

from docx import Document
import numpy as np
import xarray as xr

from cwr_report.assembler import build_report


SEASONS = ["春季", "夏季", "秋季", "冬季"]
BOUNDARIES = ["东边界", "西边界", "南边界", "北边界"]
IMAGE_SLOTS = [f"target_image{index}" for index in range(1, 6)]
PIC3_VARIABLES = ["pic3_a", "pic3_b", "pic3_c", "pic3_e", "pic3_f"]
PIC4_VARIABLES = ["pic4_a", "pic4_b", "pic4_c", "pic4_d"]
PIC5_VARIABLES = ["pic5_a", "pic5_b", "pic5_c", "pic5_d"]
NETCDF3_SIGNATURES = (b"CDF\x01", b"CDF\x02", b"CDF\x05")
HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"

TEXT_SLOT_NAMES = {
    "year_which",
    "region_name",
    "GMv_Kg",
    "GMv_mm",
    "GMh_Kg",
    "GMh_mm",
    "SP_mm",
    "SP_Kg",
    "CWR_Kg",
    "CWR_mm",
    "PEh_values",
    "PEv_values",
    "PEh_level",
    "RTh_level",
    "PEw_values",
    "RTh_values",
    "RTv_values",
    "SP_season_1",
    "SP_season_2",
    "SP_season_3",
    "SP_season_4",
    "SP_max_month",
    "SP_min_month",
    "SP_win",
    "SP_sum",
    "SP_ratio",
    "CWR_peak_feature",
    "CWR_maximum_month",
    "CWR_second_maximum_month",
    "CWR_minimum_month",
    "CWR_second_minimum_month",
    "CWR_season_1",
    "CWR_season_2",
    "CWR_season_3",
    "CWR_season_4",
    "Vinput_maximum_bound",
    "Vinput_maximum_gigatons",
    "Vinput_maximum_perp",
    "Voutput_maximum_bound",
    "Voutput_maximum_gigatons",
    "Voutput_maximum_perp",
    "Dv_input_bound",
    "Dv_input_gigatons",
    "Dv_output_bound",
    "Hinput_maximum_bound",
    "Hinput_maximum_gigatons",
    "Hinput_maximum_perp",
    "Houtput_maximum_bound",
    "Houtput_maximum_perp",
    "Dh_input_bound",
    "Dh_input_gigatons",
    "Dh_output_bound",
    "scale",
    "pic3_a",
    "pic3_b",
    "pic3_c",
    "pic3_e",
    "pic3_f",
    "pic4_maxseas",
    "pic4_minseas",
    "pic4_maxseas_destrip",
    "pic4_minseas_destrip",
    "pic5_maxseas",
    "pic5_minseas",
    "pic5_maxseas_destrip",
    "pic5_minseas_destrip",
}

ANNUAL_COLUMNS = {
    "time",
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
    "INv_W",
    "OTv_W",
    "INv_E",
    "OTv_E",
    "INv_N",
    "OTv_N",
    "INv_S",
    "OTv_S",
    "INh_W",
    "OTh_W",
    "INh_E",
    "OTh_E",
    "INh_N",
    "OTh_N",
    "INh_S",
    "OTh_S",
}
MONTHLY_COLUMNS = {"time", "SP", "CWR", "dxy"}


@dataclass(frozen=True)
class CloudWaterProfileSpec:
    report_id: str
    year: int
    region_name: str
    report_inputs: Path
    annual_csv: Path | None
    monthly_csv: Path | None
    mask_nc: Path | None
    spatial_nc: Path
    business_metrics: Path | None
    template: Path
    output: Path
    images: dict[str, Path]
    image_width_inches: float


@dataclass(frozen=True)
class CloudWaterProfileData:
    text_values: dict[str, str]
    vapor_table: list[dict[str, str]]
    hydrometeor_table: list[dict[str, str]]


def build_cloud_water_single_year_report(spec_path: Path) -> Path:
    spec = load_cloud_water_profile_spec(spec_path)
    standard_inputs = json.loads(spec.report_inputs.read_text(encoding="utf-8"))
    _validate_standard_inputs(standard_inputs, spec.year)
    data = derive_cloud_water_profile_data(spec)

    with tempfile.TemporaryDirectory(prefix="cwr-cloud-water-profile-") as raw_temp:
        temp = Path(raw_temp)
        report_inputs_path = temp / "report_inputs.json"
        generic_spec_path = temp / "report_spec.json"
        artifacts = [
            {
                "kind": "profile_image",
                "name": slot,
                "path": str(spec.images[slot]),
            }
            for slot in IMAGE_SLOTS
        ]
        stats = [
            {**row, "profile_table": "water_vapor"}
            for row in data.vapor_table
        ] + [
            {**row, "profile_table": "hydrometeor"}
            for row in data.hydrometeor_table
        ]
        report_inputs_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "task": {
                        "task_id": spec.report_id,
                        "status": "success",
                        "output_root": str(spec.output.parent),
                    },
                    "inputs": {
                        "profile": "cloud_water_single_year",
                        "standard_report_inputs": str(spec.report_inputs),
                        "year": spec.year,
                        "region_name": spec.region_name,
                    },
                    "artifacts": artifacts,
                    "runtime": {},
                    "stats": stats,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        generic_spec_path.write_text(
            json.dumps(
                _generic_report_spec(spec, data, report_inputs_path),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        return build_report(generic_spec_path)


def load_cloud_water_profile_spec(path: Path) -> CloudWaterProfileSpec:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("profile") != "cloud_water_single_year":
        raise ValueError("profile must be cloud_water_single_year")
    base = path.parent
    report_inputs = _existing_path(
        base, payload.get("report_inputs"), "report_inputs"
    )
    supplemental_keys = {"annual_csv", "monthly_csv", "mask_nc", "spatial_nc"}
    compatibility_mode = bool(supplemental_keys & set(payload))
    if compatibility_mode and not supplemental_keys <= set(payload):
        missing = sorted(supplemental_keys - set(payload))
        raise ValueError(
            f"Compatibility profile is missing supplemental input: {missing[0]}"
        )
    if compatibility_mode:
        report_id = _required_text(payload, "report_id")
        year = _required_year(payload)
        region_name = _required_text(payload, "region_name")
        annual_csv = _existing_path(
            base, payload.get("annual_csv"), "annual_csv"
        )
        monthly_csv = _existing_path(
            base, payload.get("monthly_csv"), "monthly_csv"
        )
        mask_nc = _existing_path(base, payload.get("mask_nc"), "mask_nc")
        spatial_nc = _existing_path(
            base, payload.get("spatial_nc"), "spatial_nc"
        )
        business_metrics = None
    else:
        (
            report_id,
            year,
            region_name,
            business_metrics,
            spatial_nc,
        ) = _standardized_profile_inputs(report_inputs)
        annual_csv = None
        monthly_csv = None
        mask_nc = spatial_nc
    raw_images = payload.get("images")
    if not isinstance(raw_images, dict) or set(raw_images) != set(IMAGE_SLOTS):
        raise ValueError(f"images must contain exactly {IMAGE_SLOTS}")
    images = {
        slot: _existing_path(base, raw_images[slot], f"images.{slot}")
        for slot in IMAGE_SLOTS
    }
    width = payload.get("image_width_inches", 4.0)
    if (
        not isinstance(width, (int, float))
        or isinstance(width, bool)
        or width <= 0
    ):
        raise ValueError("image_width_inches must be positive")
    output = _path(base, payload, "output")
    template = _existing_path(base, payload.get("template"), "template")
    if output.suffix.lower() != ".docx":
        raise ValueError("output must use the .docx suffix")
    if output.resolve() == template.resolve():
        raise ValueError("output must not overwrite the template")
    return CloudWaterProfileSpec(
        report_id=report_id,
        year=year,
        region_name=region_name,
        report_inputs=report_inputs,
        annual_csv=annual_csv,
        monthly_csv=monthly_csv,
        mask_nc=mask_nc,
        spatial_nc=spatial_nc,
        business_metrics=business_metrics,
        template=template,
        output=output,
        images=images,
        image_width_inches=float(width),
    )


def derive_cloud_water_profile_data(
    spec: CloudWaterProfileSpec,
) -> CloudWaterProfileData:
    if spec.business_metrics:
        metrics = _load_business_metrics(spec.business_metrics, spec.year)
        annual, months = _legacy_rows_from_metrics(metrics)
    else:
        annual, months = _legacy_rows_from_supplemental_inputs(spec)

    text = _derive_scalar_text(spec, annual, months)
    if spec.mask_nc is None:
        raise ValueError("mask_nc is required for spatial analysis")
    spatial = _derive_spatial_text(spec.mask_nc, spec.spatial_nc)
    text.update(spatial)
    missing_text = sorted(TEXT_SLOT_NAMES - set(text))
    if missing_text:
        raise ValueError(f"Profile did not derive text slot: {missing_text[0]}")

    vapor_table, hydrometeor_table = _derive_boundary_tables(annual)
    return CloudWaterProfileData(
        text_values={key: str(value) for key, value in text.items()},
        vapor_table=vapor_table,
        hydrometeor_table=hydrometeor_table,
    )


def _legacy_rows_from_supplemental_inputs(
    spec: CloudWaterProfileSpec,
) -> tuple[dict[str, str], dict[int, dict[str, str]]]:
    if spec.annual_csv is None or spec.monthly_csv is None:
        raise ValueError("Compatibility profile requires annual and monthly CSV")
    annual_rows = _read_csv(spec.annual_csv, ANNUAL_COLUMNS)
    annual_matches = [
        row for row in annual_rows if _year(row["time"]) == spec.year
    ]
    if len(annual_matches) != 1:
        raise ValueError(
            f"annual_csv must contain exactly one row for {spec.year}"
        )
    annual = annual_matches[0]

    months: dict[int, dict[str, str]] = {}
    for row in _read_csv(spec.monthly_csv, MONTHLY_COLUMNS):
        if _year(row["time"]) != spec.year:
            continue
        month = _month(row["time"])
        if month in months:
            raise ValueError(f"monthly_csv has duplicate {spec.year}-{month:02d}")
        months[month] = row
    if set(months) != set(range(1, 13)):
        missing = sorted(set(range(1, 13)) - set(months))
        raise ValueError(f"monthly_csv is missing months: {missing}")
    return annual, months


def _legacy_rows_from_metrics(
    metrics: dict[str, Any],
) -> tuple[dict[str, Any], dict[int, dict[str, Any]]]:
    annual = {
        "time": f"{metrics['year']}-01-01",
        **metrics["annual"]["values"],
    }
    prefixes = {
        "water_vapor": ("INv", "OTv"),
        "hydrometeor": ("INh", "OTh"),
    }
    side_codes = {"west": "W", "east": "E", "south": "S", "north": "N"}
    for component, (incoming_prefix, outgoing_prefix) in prefixes.items():
        rows = {
            row["boundary"]: row
            for row in metrics["boundaries"][component]
            if row["boundary"] != "total"
        }
        for boundary, side in side_codes.items():
            annual[f"{incoming_prefix}_{side}"] = (
                float(rows[boundary]["input"]) * 1e11
            )
            annual[f"{outgoing_prefix}_{side}"] = (
                float(rows[boundary]["output"]) * 1e11
            )
    months = {
        int(row["month"]): {
            "time": f"{metrics['year']}-{int(row['month']):02d}-01",
            "SP": row["SP"],
            "CWR": row["CWR"],
            "dxy": row["dxy"],
        }
        for row in metrics["monthly"]
    }
    if set(months) != set(range(1, 13)):
        raise ValueError("business_metrics must contain all twelve months")
    return annual, months


def _derive_scalar_text(
    spec: CloudWaterProfileSpec,
    annual: dict[str, str],
    months: dict[int, dict[str, str]],
) -> dict[str, str]:
    dxy = _number(annual, "dxy")
    if dxy == 0:
        raise ValueError("annual dxy must not be zero")
    sp_month = np.array(
        [_number(months[month], "SP") / dxy for month in range(1, 13)]
    )
    cwr_month = np.array(
        [_number(months[month], "CWR") / dxy for month in range(1, 13)]
    )
    sp_season = _season_totals(sp_month)
    cwr_season = _season_totals(cwr_month)
    sp_order = np.argsort(sp_season)
    cwr_order = np.argsort(cwr_season)

    values: dict[str, str] = {
        "year_which": str(spec.year),
        "region_name": spec.region_name,
        "GMv_Kg": _format(_number(annual, "GMv") / 1e11),
        "GMv_mm": _format(_number(annual, "GMv") / dxy),
        "GMh_Kg": _format(_number(annual, "GMh") / 1e11),
        "GMh_mm": _format(_number(annual, "GMh") / dxy),
        "SP_Kg": _format(_number(annual, "SP") / 1e11),
        "SP_mm": _format(_number(annual, "SP") / dxy),
        "CWR_Kg": _format(_number(annual, "CWR") / 1e11),
        "CWR_mm": _format(_number(annual, "CWR") / dxy),
        "PEh_values": _format(_number(annual, "PEh")),
        "PEv_values": _format(_number(annual, "PEv")),
        "PEw_values": _format(_number(annual, "PEw")),
        "RTv_values": _format(_number(annual, "RCv")),
        "RTh_values": _format(_number(annual, "RCh")),
        "PEh_level": _precipitation_efficiency_level(_number(annual, "PEh")),
        "RTh_level": _residence_time_level(_number(annual, "RCh")),
        "SP_max_month": f"{int(np.argmax(sp_month)) + 1:02d}",
        "SP_min_month": f"{int(np.argmin(sp_month)) + 1:02d}",
        "SP_win": _format(sp_season[3]),
        "SP_sum": _format(math.floor(sp_season[1] / 100) * 100, 0),
        "SP_ratio": _format(_safe_ratio(sp_season[1], sp_season[3]), 0),
        "CWR_peak_feature": (
            "双峰" if _is_bimodal_by_top2(cwr_month) else "单峰"
        ),
        "CWR_maximum_month": str(int(np.argmax(cwr_month)) + 1),
        "CWR_second_maximum_month": str(int(np.argsort(cwr_month)[-2]) + 1),
        "CWR_minimum_month": str(int(np.argmin(cwr_month)) + 1),
        "CWR_second_minimum_month": str(int(np.argsort(cwr_month)[1]) + 1),
    }
    for rank, key in enumerate((4, 3, 2, 1)):
        values[f"SP_season_{key}"] = SEASONS[int(sp_order[rank])]
        values[f"CWR_season_{key}"] = SEASONS[int(cwr_order[rank])]

    boundary = _boundary_values(annual)
    values.update(_derive_boundary_text(boundary))
    return values


def _derive_boundary_text(values: dict[str, np.ndarray]) -> dict[str, str]:
    vapor_in = values["vapor_in"]
    vapor_out = values["vapor_out"]
    hydro_in = values["hydro_in"]
    hydro_out = values["hydro_out"]
    vapor_net = vapor_in - vapor_out
    hydro_net = hydro_in - hydro_out
    vapor_input_index = int(np.argmax(vapor_in))
    vapor_output_index = int(np.argmax(vapor_out))
    hydro_input_index = int(np.argmax(hydro_in))
    hydro_output_index = int(np.argmax(hydro_out))
    scale_ratio = _safe_ratio(float(vapor_in.sum()), float(hydro_in.sum()))
    scale = max(0, int(math.floor(math.log10(abs(scale_ratio))))) if scale_ratio else 0
    return {
        "Vinput_maximum_bound": BOUNDARIES[vapor_input_index],
        "Vinput_maximum_gigatons": _format(vapor_in[vapor_input_index]),
        "Vinput_maximum_perp": _format(
            _safe_ratio(vapor_in[vapor_input_index] * 100, vapor_in.sum())
        ),
        "Voutput_maximum_bound": BOUNDARIES[vapor_output_index],
        "Voutput_maximum_gigatons": _format(vapor_out[vapor_output_index]),
        "Voutput_maximum_perp": _format(
            _safe_ratio(vapor_out[vapor_output_index] * 100, vapor_out.sum())
        ),
        "Dv_input_bound": _joined_boundaries(vapor_net, positive=True),
        "Dv_input_gigatons": _joined_values(vapor_net, positive=True),
        "Dv_output_bound": _joined_boundaries(vapor_net, positive=False),
        "Hinput_maximum_bound": BOUNDARIES[hydro_input_index],
        "Hinput_maximum_gigatons": _format(hydro_in[hydro_input_index]),
        "Hinput_maximum_perp": _format(
            _safe_ratio(hydro_in[hydro_input_index] * 100, hydro_in.sum())
        ),
        "Houtput_maximum_bound": BOUNDARIES[hydro_output_index],
        "Houtput_maximum_perp": _format(
            _safe_ratio(hydro_out[hydro_output_index] * 100, hydro_out.sum())
        ),
        "Dh_input_bound": _joined_boundaries(hydro_net, positive=True),
        "Dh_input_gigatons": _joined_values(hydro_net, positive=True),
        "Dh_output_bound": _joined_boundaries(hydro_net, positive=False),
        "scale": str(scale),
    }


def _derive_boundary_tables(
    annual: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    values = _boundary_values(annual)
    return (
        _boundary_table(values["vapor_in"], values["vapor_out"]),
        _boundary_table(values["hydro_in"], values["hydro_out"]),
    )


def _boundary_values(annual: dict[str, str]) -> dict[str, np.ndarray]:
    def array(prefix_in: str, prefix_out: str) -> tuple[np.ndarray, np.ndarray]:
        order = ["E", "W", "S", "N"]
        incoming = np.array(
            [_number(annual, f"{prefix_in}_{side}") / 1e11 for side in order]
        )
        outgoing = np.array(
            [_number(annual, f"{prefix_out}_{side}") / 1e11 for side in order]
        )
        return incoming, outgoing

    vapor_in, vapor_out = array("INv", "OTv")
    hydro_in, hydro_out = array("INh", "OTh")
    return {
        "vapor_in": vapor_in,
        "vapor_out": vapor_out,
        "hydro_in": hydro_in,
        "hydro_out": hydro_out,
    }


def _boundary_table(
    incoming: np.ndarray,
    outgoing: np.ndarray,
) -> list[dict[str, str]]:
    display_order = [1, 0, 2, 3]
    rows = [
        {
            "边界名称": BOUNDARIES[index],
            "输入": _format(incoming[index]),
            "输出": _format(outgoing[index]),
            "净输入": _format(incoming[index] - outgoing[index]),
        }
        for index in display_order
    ]
    rows.append(
        {
            "边界名称": "合计",
            "输入": _format(incoming.sum()),
            "输出": _format(outgoing.sum()),
            "净输入": _format(incoming.sum() - outgoing.sum()),
        }
    )
    return rows


def _derive_spatial_text(mask_path: Path, spatial_path: Path) -> dict[str, str]:
    with _open_netcdf(mask_path) as mask_dataset:
        variable = (
            "ind_area_bool"
            if "ind_area_bool" in mask_dataset
            else next(iter(mask_dataset.data_vars))
        )
        mask = mask_dataset[variable].values.astype(bool)
    with _open_netcdf(spatial_path) as dataset:
        required = set(PIC3_VARIABLES + PIC4_VARIABLES + PIC5_VARIABLES)
        missing = sorted(required - set(dataset.data_vars))
        if missing:
            raise ValueError(f"spatial_nc is missing variable: {missing[0]}")
        if any(dataset[name].shape != mask.shape for name in required):
            raise ValueError("spatial_nc variables must match mask shape")
        result = {
            name: _spatial_description(dataset, name, mask)
            for name in PIC3_VARIABLES
        }
        result.update(
            _seasonal_spatial_text(dataset, mask, PIC4_VARIABLES, "pic4")
        )
        result.update(
            _seasonal_spatial_text(dataset, mask, PIC5_VARIABLES, "pic5")
        )
        return result


def _open_netcdf(path: Path) -> xr.Dataset:
    with path.open("rb") as stream:
        signature = stream.read(8)

    if signature.startswith(NETCDF3_SIGNATURES):
        return xr.open_dataset(path, engine="scipy")
    if signature == HDF5_SIGNATURE:
        return xr.open_dataset(path, engine="h5netcdf")
    raise ValueError(f"unsupported NetCDF file format: {path}")


def _seasonal_spatial_text(
    dataset,
    mask: np.ndarray,
    variables: list[str],
    prefix: str,
) -> dict[str, str]:
    means = np.array(
        [float(np.nanmean(dataset[name].values[mask])) for name in variables]
    )
    maximum = int(np.nanargmax(means))
    minimum = int(np.nanargmin(means))
    return {
        f"{prefix}_maxseas": SEASONS[maximum],
        f"{prefix}_minseas": SEASONS[minimum],
        f"{prefix}_maxseas_destrip": (
            f"{SEASONS[maximum]}分布特点为"
            f"{_spatial_description(dataset, variables[maximum], mask)}"
        ),
        f"{prefix}_minseas_destrip": (
            f"{SEASONS[minimum]}分布特点为"
            f"{_spatial_description(dataset, variables[minimum], mask)}"
        ),
    }


def _spatial_description(dataset, variable: str, mask: np.ndarray) -> str:
    data = np.asarray(dataset[variable].values, dtype=float)
    valid = mask & np.isfinite(data)
    if valid.sum() < 3:
        raise ValueError(f"{variable} has fewer than three valid mask cells")
    if np.isclose(float(np.nanmin(data[valid])), float(np.nanmax(data[valid]))):
        return "区域内数值空间分布较为均匀，高值区与低值区的梯度方向不明显。"
    lat_name = "lat" if "lat" in dataset.coords else "latitude"
    lon_name = "lon" if "lon" in dataset.coords else "longitude"
    lon, lat = np.meshgrid(dataset[lon_name].values, dataset[lat_name].values)
    x = _normalize(lon[valid])
    y = _normalize(lat[valid])
    design = np.column_stack([x, y, np.ones(valid.sum())])
    coefficients, *_ = np.linalg.lstsq(design, data[valid], rcond=None)
    vector = coefficients[:2]
    if not np.all(np.isfinite(vector)) or np.hypot(*vector) < 1e-12:
        return "区域内数值空间分布较为均匀，高值区与低值区的梯度方向不明显。"
    high = _direction(float(vector[0]), float(vector[1]))
    low = _direction(float(-vector[0]), float(-vector[1]))
    return (
        f"区域内数值总体表现为由{low}向{high}递增，"
        f"高值区主要偏向{high}，低值区主要偏向{low}。"
    )


def _generic_report_spec(
    spec: CloudWaterProfileSpec,
    data: CloudWaterProfileData,
    report_inputs_path: Path,
) -> dict[str, Any]:
    template_slots = _template_slots(spec.template)
    block_slots = set(IMAGE_SLOTS) | {
        "table_for_TFdatav",
        "table_for_TFdatah",
    }
    template_text_slots = template_slots - block_slots
    missing = sorted(template_text_slots - set(data.text_values))
    if missing:
        raise ValueError(f"Profile cannot populate template slot: {missing[0]}")
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
        "report_inputs": str(report_inputs_path),
        "template": str(spec.template),
        "output": str(spec.output),
        "text_slots": {
            slot: data.text_values[slot] for slot in sorted(template_text_slots)
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
                "width_inches": spec.image_width_inches,
                "alt_text": f"{spec.year}年{spec.region_name}{slot}",
            }
            for slot in IMAGE_SLOTS
        },
    }


def _template_slots(path: Path) -> set[str]:
    document = Document(path)
    slots = set()
    for paragraph in document.paragraphs:
        text = paragraph.text
        start = 0
        while True:
            left = text.find("<<", start)
            if left < 0:
                break
            right = text.find(">>", left + 2)
            if right < 0:
                break
            slots.add(text[left + 2 : right])
            start = right + 2
    return slots


def _validate_standard_inputs(payload: dict, year: int) -> None:
    if payload.get("schema_version", 1) != 1:
        raise ValueError("Unsupported standard report_inputs schema version")
    if payload.get("task", {}).get("status") != "success":
        raise ValueError("Standard report_inputs task status must be success")
    slices = payload.get("inputs", {}).get("time_slices", [])
    labels = [
        str(item.get("label") or item.get("year") or item.get("start", ""))
        for item in slices
        if isinstance(item, dict)
    ]
    if not any(label.startswith(str(year)) for label in labels):
        raise ValueError(f"Standard report_inputs does not cover year {year}")


def _standardized_profile_inputs(
    report_inputs_path: Path,
) -> tuple[str, int, str, Path, Path]:
    payload = json.loads(report_inputs_path.read_text(encoding="utf-8"))
    if payload.get("schema_version", 1) != 1:
        raise ValueError("Unsupported standard report_inputs schema version")
    if payload.get("task", {}).get("status") != "success":
        raise ValueError("Standard report_inputs task status must be success")
    metrics_records = [
        artifact
        for artifact in payload.get("artifacts", [])
        if artifact.get("kind") == "business_metrics"
        and artifact.get("metric_profile") == "cloud_water_single_year"
    ]
    spatial_records = [
        artifact
        for artifact in payload.get("artifacts", [])
        if artifact.get("kind") == "spatial_composite"
        and artifact.get("metric_profile") == "cloud_water_single_year"
    ]
    if len(metrics_records) != 1:
        raise ValueError(
            "report_inputs must index exactly one cloud-water business_metrics"
        )
    if len(spatial_records) != 1:
        raise ValueError(
            "report_inputs must index exactly one cloud-water spatial_composite"
        )
    metrics_path = _artifact_path(report_inputs_path, metrics_records[0])
    spatial_path = _artifact_path(report_inputs_path, spatial_records[0])
    metrics = _load_business_metrics(metrics_path)
    if payload["task"].get("task_id") != metrics["task_id"]:
        raise ValueError(
            "report_inputs task_id does not match business_metrics task_id"
        )
    expected_spatial_name = metrics.get("spatial_composite", {}).get(
        "artifact_name"
    )
    if expected_spatial_name != spatial_records[0].get("name"):
        raise ValueError(
            "business_metrics spatial artifact name does not match "
            "report_inputs"
        )
    return (
        str(metrics["task_id"]),
        int(metrics["year"]),
        str(metrics["region_name"]),
        metrics_path,
        spatial_path,
    )


def _load_business_metrics(
    path: Path,
    expected_year: int | None = None,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("Unsupported business_metrics schema version")
    if payload.get("kind") != "business_metrics":
        raise ValueError("business_metrics kind must be business_metrics")
    if payload.get("metric_profile") != "cloud_water_single_year":
        raise ValueError(
            "business_metrics metric_profile must be cloud_water_single_year"
        )
    year = payload.get("year")
    if not isinstance(year, int) or isinstance(year, bool):
        raise ValueError("business_metrics year must be an integer")
    if expected_year is not None and year != expected_year:
        raise ValueError(
            f"business_metrics year {year} does not match report year "
            f"{expected_year}"
        )
    for key in ("task_id", "region_name", "annual", "monthly", "boundaries"):
        if key not in payload:
            raise ValueError(f"business_metrics is missing {key}")
    annual_values = payload["annual"].get("values", {})
    missing_annual = sorted(
        {
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
        }
        - set(annual_values)
    )
    if missing_annual:
        raise ValueError(
            f"business_metrics annual values are missing {missing_annual[0]}"
        )
    monthly = payload["monthly"]
    if not isinstance(monthly, list) or len(monthly) != 12:
        raise ValueError("business_metrics must contain twelve monthly records")
    if {
        int(row.get("month", -1)) for row in monthly if isinstance(row, dict)
    } != set(range(1, 13)):
        raise ValueError("business_metrics must contain months 1 through 12")
    boundaries = payload["boundaries"]
    if not {"water_vapor", "hydrometeor"} <= set(boundaries):
        raise ValueError("business_metrics is missing boundary components")
    for component in ("water_vapor", "hydrometeor"):
        names = {
            row.get("boundary")
            for row in boundaries[component]
            if isinstance(row, dict)
        }
        if names != {"west", "east", "south", "north", "total"}:
            raise ValueError(
                f"business_metrics {component} boundaries are incomplete"
            )
    return payload


def _artifact_path(report_inputs_path: Path, artifact: dict[str, Any]) -> Path:
    raw = artifact.get("path")
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Indexed artifact path must be a non-empty string")
    path = Path(raw)
    candidates = (
        [path]
        if path.is_absolute()
        else [
            report_inputs_path.parent / path,
            report_inputs_path.parent.parent / path,
        ]
    )
    for candidate in candidates:
        resolved = candidate.resolve()
        if resolved.is_file():
            return resolved
    raise ValueError(f"Indexed artifact does not exist: {raw}")


def _read_csv(path: Path, required: set[str]) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = sorted(required - fields)
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
        return int(str(value)[5:7])
    except ValueError as error:
        raise ValueError(f"Invalid monthly CSV time: {value}") from error


def _number(row: dict[str, str], key: str) -> float:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"Invalid numeric value for {key}") from error
    if not math.isfinite(value):
        raise ValueError(f"Non-finite numeric value for {key}")
    return value


def _season_totals(values: np.ndarray) -> np.ndarray:
    return np.array(
        [
            values[2:5].sum(),
            values[5:8].sum(),
            values[8:11].sum(),
            values[11] + values[0:2].sum(),
        ]
    )


def _is_bimodal_by_top2(values: np.ndarray) -> bool:
    indices = np.sort(np.argsort(values)[-2:])
    return int(indices[1] - indices[0]) > 1


def _precipitation_efficiency_level(value: float) -> str:
    if value >= 70:
        return "高"
    if value > 50:
        return "较低"
    return "低"


def _residence_time_level(value: float) -> str:
    return "长" if value > 5 else "短"


def _joined_boundaries(values: np.ndarray, positive: bool) -> str:
    selected = values > 0 if positive else values < 0
    names = [BOUNDARIES[index] for index in np.where(selected)[0]]
    return "、".join(names) if names else "无"


def _joined_values(values: np.ndarray, positive: bool) -> str:
    selected = values > 0 if positive else values < 0
    numbers = [_format(value) for value in values[selected]]
    return "、".join(numbers) if numbers else "0.0"


def _safe_ratio(numerator: float, denominator: float) -> float:
    return 0.0 if np.isclose(denominator, 0) else float(numerator / denominator)


def _normalize(values: np.ndarray) -> np.ndarray:
    minimum = float(np.nanmin(values))
    maximum = float(np.nanmax(values))
    if np.isclose(minimum, maximum):
        return np.zeros_like(values, dtype=float)
    return ((values - minimum) / (maximum - minimum)) * 2 - 1


def _direction(x: float, y: float) -> str:
    names = ["东", "东北", "北", "西北", "西", "西南", "南", "东南"]
    angle = (math.degrees(math.atan2(y, x)) + 360) % 360
    return names[int(((angle + 22.5) % 360) // 45)]


def _format(value: float, precision: int = 1) -> str:
    return f"{float(value):.{precision}f}"


def _required_text(payload: dict, key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def _required_year(payload: dict[str, Any]) -> int:
    year = payload.get("year")
    if not isinstance(year, int) or isinstance(year, bool):
        raise ValueError("year must be an integer")
    return year


def _path(base: Path, payload: dict, key: str) -> Path:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty path")
    path = Path(value)
    return path if path.is_absolute() else (base / path).resolve()


def _existing_path(base: Path, value: Any, key: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty path")
    path = Path(value)
    resolved = path if path.is_absolute() else (base / path).resolve()
    if not resolved.is_file():
        raise ValueError(f"{key} does not exist: {resolved}")
    return resolved
