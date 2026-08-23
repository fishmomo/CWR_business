from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import json
from pathlib import Path
import re
from typing import Any

from cwr_engine.models.output_request import OutputRequest
from cwr_engine.models.region import build_region_spec
from cwr_engine.models.task import EngineTask
from cwr_engine.models.time_slice import normalize_time_slice
from cwr_engine.registries.operators import build_operator_registry
from cwr_engine.registries.variables import build_variable_registry


REQUEST_SCHEMA_VERSION = 1
SAFE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
RESULT_KIND_MAP = {
    ("region", "csv", None): "region_table",
    ("grid", "netcdf", None): "grid_nc",
    ("region", "figure", "time_series"): "figure_timeseries",
    ("region", "figure", "bar_compare"): "figure_bar_compare",
    ("grid", "figure", "distribution"): "figure_distribution",
}
DEFAULT_RESULT_NAMES = {
    "region_table": "regional_results",
    "grid_nc": "gridded_results",
    "figure_timeseries": "time_series",
    "figure_bar_compare": "bar_comparison",
    "figure_distribution": "distribution",
}


@dataclass(frozen=True)
class BusinessRequest:
    request_id: str
    data_source: dict[str, Any]
    region: dict[str, Any]
    period: dict[str, Any]
    variables: list[str]
    operators: list[str]
    results: list[dict[str, Any]]
    output_root: str | None


def parse_business_request(payload: dict[str, Any]) -> BusinessRequest:
    if not isinstance(payload, dict):
        raise ValueError("Business request must be a JSON object")
    _reject_unknown(
        payload,
        {
            "schema_version",
            "request_id",
            "data_source",
            "region",
            "period",
            "variables",
            "operators",
            "results",
            "output_root",
        },
        "business request",
    )
    if payload.get("schema_version") != REQUEST_SCHEMA_VERSION:
        raise ValueError(
            f"schema_version must be {REQUEST_SCHEMA_VERSION}"
        )

    request_id = _safe_name(payload.get("request_id"), "request_id")
    data_source = _validate_data_source(payload.get("data_source"))
    region = _validate_region(payload.get("region"))
    period = _validate_period(payload.get("period"))
    variables = _string_list(payload.get("variables"), "variables")
    operators = _string_list(payload.get("operators", ["mean"]), "operators")
    results = _validate_results(payload.get("results"))
    output_root = payload.get("output_root")
    if output_root is not None and (
        not isinstance(output_root, str) or not output_root.strip()
    ):
        raise ValueError("output_root must be a non-empty string")

    variable_map = data_source.get("variable_map", {})
    unknown_mappings = sorted(set(variable_map) - set(variables))
    if unknown_mappings:
        raise ValueError(
            f"variable_map contains an unrequested variable: {unknown_mappings[0]}"
        )
    _validate_registry_values(
        variables,
        build_variable_registry(),
        "variable",
    )
    _validate_registry_values(
        operators,
        build_operator_registry(),
        "operator",
    )
    return BusinessRequest(
        request_id=request_id,
        data_source=data_source,
        region=region,
        period=period,
        variables=variables,
        operators=operators,
        results=results,
        output_root=output_root,
    )


def load_business_request(path: Path) -> BusinessRequest:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return parse_business_request(payload)


def compile_business_request(
    request: BusinessRequest,
    request_path: Path,
    output_root: Path | None = None,
) -> EngineTask:
    time_slices = _expand_period(request.period)
    source = {
        "name": "nc",
        "root": _resolve_input_path(
            request.data_source["root"],
            request_path,
        ),
        "time_scale": request.period["scale"],
    }
    for key in ("engine", "pattern", "coordinate_map", "variable_map"):
        if key in request.data_source:
            source[key] = request.data_source[key]

    region = dict(request.region)
    kind = region.pop("kind")
    if "path" in region:
        region["path"] = _resolve_input_path(region["path"], request_path)
    outputs = [
        OutputRequest(
            kind=item["engine_kind"],
            name=item["name"],
            params=item.get("params", {}),
        )
        for item in request.results
    ]
    outputs.append(OutputRequest(kind="report_inputs", name="request_manifest"))
    workflow_steps = _workflow_steps(outputs)

    if output_root is not None:
        root = output_root.resolve()
    elif request.output_root:
        configured = Path(request.output_root)
        root = (
            configured
            if configured.is_absolute()
            else request_path.parent / configured
        )
        root = root.resolve()
    else:
        root = (Path.cwd() / "artifacts" / "runs" / request.request_id).resolve()
    return EngineTask(
        task_id=request.request_id,
        data_source=source,
        time_slices=time_slices,
        region_spec=build_region_spec({"kind": kind, "payload": region}),
        variables=request.variables,
        operators=request.operators,
        outputs=outputs,
        workflow_steps=workflow_steps,
        reuse_policy={},
        output_root=str(root),
    )


def run_business_request(
    request_path: Path,
    output_root: Path | None = None,
) -> Path:
    from cwr_engine.pipeline import run_engine_task

    request = load_business_request(request_path)
    task = compile_business_request(request, request_path, output_root)
    return run_engine_task(task, task_path=request_path)


def _validate_data_source(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("data_source must be an object")
    _reject_unknown(
        payload,
        {"kind", "root", "engine", "pattern", "coordinate_map", "variable_map"},
        "data_source",
    )
    if payload.get("kind") != "netcdf":
        raise ValueError("data_source.kind must be 'netcdf'")
    root = payload.get("root")
    if not isinstance(root, str) or not root.strip():
        raise ValueError("data_source.root must be a non-empty string")
    result = {"kind": "netcdf", "root": root}
    for key in ("engine", "pattern"):
        value = payload.get(key)
        if value is not None:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"data_source.{key} must be a non-empty string")
            result[key] = value
    if "coordinate_map" in payload:
        coordinate_map = _string_map(payload["coordinate_map"], "coordinate_map")
        unknown = sorted(set(coordinate_map) - {"time", "lat", "lon"})
        if unknown:
            raise ValueError(f"Unsupported coordinate_map key: {unknown[0]}")
        result["coordinate_map"] = coordinate_map
    if "variable_map" in payload:
        result["variable_map"] = _string_map(
            payload["variable_map"],
            "variable_map",
        )
    return result


def _validate_region(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("region must be an object")
    kind = payload.get("kind")
    if kind == "shp":
        allowed = {"kind", "path", "source_crs", "target_crs"}
        _reject_unknown(payload, allowed, "region")
        result = {"kind": kind, "path": _required_text(payload, "path", "region")}
        for key in ("source_crs", "target_crs"):
            if key in payload:
                result[key] = _required_text(payload, key, "region")
        return result
    if kind == "existing_mask":
        allowed = {"kind", "path", "variable", "engine"}
        _reject_unknown(payload, allowed, "region")
        result = {"kind": kind, "path": _required_text(payload, "path", "region")}
        for key in ("variable", "engine"):
            if key in payload:
                result[key] = _required_text(payload, key, "region")
        return result
    if kind == "bbox":
        allowed = {"kind", "min_lon", "max_lon", "min_lat", "max_lat"}
        _reject_unknown(payload, allowed, "region")
        result = {"kind": kind}
        for key in ("min_lon", "max_lon", "min_lat", "max_lat"):
            value = payload.get(key)
            if not _is_number(value):
                raise ValueError(f"region.{key} must be a number")
            result[key] = float(value)
        if result["min_lon"] > result["max_lon"]:
            raise ValueError("region.min_lon must not exceed max_lon")
        if result["min_lat"] > result["max_lat"]:
            raise ValueError("region.min_lat must not exceed max_lat")
        return result
    raise ValueError("region.kind must be one of: shp, existing_mask, bbox")


def _validate_period(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("period must be an object")
    scale = payload.get("scale")
    if scale == "year":
        _reject_unknown(payload, {"scale", "years", "year_range"}, "period")
        years = _year_selection(payload)
        return {"scale": scale, "years": years}
    if scale == "month":
        _reject_unknown(
            payload,
            {"scale", "items", "years", "year_range", "months"},
            "period",
        )
        has_items = "items" in payload
        has_cross_product = any(
            key in payload for key in ("years", "year_range", "months")
        )
        if has_items == has_cross_product:
            raise ValueError(
                "month period requires either items or years/year_range with months"
            )
        if has_items:
            items = _month_items(payload["items"])
        else:
            years = _year_selection(payload)
            months = _integer_list(payload.get("months"), "period.months", 1, 12)
            items = sorted(
                f"{year:04d}-{month:02d}"
                for year in years
                for month in months
            )
        return {"scale": scale, "items": items}
    if scale == "day":
        _reject_unknown(payload, {"scale", "dates", "date_range"}, "period")
        has_dates = "dates" in payload
        has_range = "date_range" in payload
        if has_dates == has_range:
            raise ValueError("day period requires either dates or date_range")
        if has_dates:
            dates = _date_items(payload["dates"], "period.dates")
        else:
            date_range = payload["date_range"]
            if not isinstance(date_range, list) or len(date_range) != 2:
                raise ValueError("period.date_range must contain start and end dates")
            start, end = (_iso_date(item, "period.date_range") for item in date_range)
            if start > end:
                raise ValueError("period.date_range start must not exceed end")
            dates = []
            current = start
            while current <= end:
                dates.append(current.isoformat())
                current += timedelta(days=1)
        return {"scale": scale, "dates": dates}
    raise ValueError("period.scale must be one of: day, month, year")


def _validate_results(payload: Any) -> list[dict[str, Any]]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("results must be a non-empty list")
    results = []
    names = set()
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"results[{index}] must be an object")
        _reject_unknown(
            item,
            {"scope", "format", "plot", "name", "params"},
            f"results[{index}]",
        )
        scope = item.get("scope")
        output_format = item.get("format")
        plot = item.get("plot")
        key = (scope, output_format, plot)
        engine_kind = RESULT_KIND_MAP.get(key)
        if engine_kind is None:
            raise ValueError(
                f"Unsupported result combination at results[{index}]: "
                f"scope={scope!r}, format={output_format!r}, plot={plot!r}"
            )
        if output_format != "figure" and "params" in item:
            raise ValueError(f"results[{index}].params is only valid for figures")
        params = item.get("params", {})
        if not isinstance(params, dict):
            raise ValueError(f"results[{index}].params must be an object")
        name = _safe_name(
            item.get("name", DEFAULT_RESULT_NAMES[engine_kind]),
            f"results[{index}].name",
        )
        if name in names:
            raise ValueError(f"Duplicate result name: {name}")
        names.add(name)
        results.append(
            {"engine_kind": engine_kind, "name": name, "params": params}
        )
    return results


def _expand_period(period: dict[str, Any]) -> list:
    if period["scale"] == "year":
        items = [
            {"scale": "year", "year": year}
            for year in period["years"]
        ]
    elif period["scale"] == "month":
        items = [
            {
                "scale": "month",
                "year": int(value[:4]),
                "month": int(value[5:]),
            }
            for value in period["items"]
        ]
    else:
        items = [
            {"scale": "day", "date": value}
            for value in period["dates"]
        ]
    return [normalize_time_slice(item) for item in items]


def _workflow_steps(outputs: list[OutputRequest]) -> list[str]:
    kinds = {item.kind for item in outputs}
    steps = ["prepare", "mask", "subset", "transform"]
    if kinds & {"region_table", "figure_bar_compare"}:
        steps.append("stat")
    if any(kind.startswith("figure_") for kind in kinds):
        steps.append("plot")
    if kinds & {"region_table", "grid_nc"}:
        steps.append("export")
    steps.append("report_inputs")
    return steps


def _year_selection(payload: dict[str, Any]) -> list[int]:
    has_years = "years" in payload
    has_range = "year_range" in payload
    if has_years == has_range:
        raise ValueError("period requires either years or year_range")
    if has_years:
        return _integer_list(payload["years"], "period.years", 1, 9999)
    year_range = payload["year_range"]
    if not isinstance(year_range, list) or len(year_range) != 2:
        raise ValueError("period.year_range must contain start and end years")
    start, end = year_range
    if not _is_int(start) or not _is_int(end):
        raise ValueError("period.year_range values must be integers")
    if not 1 <= start <= end <= 9999:
        raise ValueError("period.year_range must satisfy 1 <= start <= end <= 9999")
    return list(range(start, end + 1))


def _month_items(payload: Any) -> list[str]:
    if not isinstance(payload, list) or not payload:
        raise ValueError("period.items must be a non-empty list")
    result = []
    for value in payload:
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}", value):
            raise ValueError("period.items values must use YYYY-MM")
        year = int(value[:4])
        month = int(value[5:])
        if not 1 <= year <= 9999 or not 1 <= month <= 12:
            raise ValueError(f"Invalid month period: {value}")
        result.append(value)
    return _unique_sorted(result, "period.items")


def _date_items(payload: Any, field: str) -> list[str]:
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"{field} must be a non-empty list")
    values = [_iso_date(value, field).isoformat() for value in payload]
    return _unique_sorted(values, field)


def _integer_list(
    payload: Any,
    field: str,
    minimum: int,
    maximum: int,
) -> list[int]:
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"{field} must be a non-empty list")
    for value in payload:
        if not _is_int(value) or not minimum <= value <= maximum:
            raise ValueError(
                f"{field} values must be integers from {minimum} to {maximum}"
            )
    return _unique_sorted(payload, field)


def _string_list(payload: Any, field: str) -> list[str]:
    if not isinstance(payload, list) or not payload:
        raise ValueError(f"{field} must be a non-empty list")
    for value in payload:
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field} values must be non-empty strings")
    return _unique_preserving_order(payload, field)


def _string_map(payload: Any, field: str) -> dict[str, str]:
    if not isinstance(payload, dict):
        raise ValueError(f"data_source.{field} must be an object")
    for key, value in payload.items():
        if (
            not isinstance(key, str)
            or not key.strip()
            or not isinstance(value, str)
            or not value.strip()
        ):
            raise ValueError(
                f"data_source.{field} keys and values must be non-empty strings"
            )
    return dict(payload)


def _validate_registry_values(values: list[str], registry: dict, label: str) -> None:
    for value in values:
        if value not in registry:
            raise ValueError(f"Unsupported {label}: {value}")


def _unique_sorted(values: list, field: str) -> list:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must not contain duplicates")
    return sorted(values)


def _unique_preserving_order(values: list[str], field: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field} must not contain duplicates")
    return list(values)


def _safe_name(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SAFE_NAME_PATTERN.fullmatch(value):
        raise ValueError(
            f"{field} must contain only letters, numbers, '.', '_' or '-'"
        )
    return value


def _required_text(payload: dict, key: str, parent: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{parent}.{key} must be a non-empty string")
    return value


def _iso_date(value: Any, field: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError(f"{field} values must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"Invalid date in {field}: {value}") from error


def _resolve_input_path(raw_path: str, request_path: Path) -> str:
    path = Path(raw_path)
    if not path.is_absolute():
        path = request_path.parent / path
    return str(path.resolve())


def _reject_unknown(payload: dict, allowed: set[str], field: str) -> None:
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"Unsupported {field} field: {unknown[0]}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)
