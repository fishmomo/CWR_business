from __future__ import annotations

from collections.abc import Iterable
from statistics import mean


def build_stat_summary(stats: list[dict], binding: dict) -> str:
    rows = _filter_rows(stats, binding)
    if not rows:
        raise ValueError("stat_summary has no matching statistics")

    variable = binding.get("variable_label") or rows[0]["variable"]
    operator = binding.get("operator_label") or rows[0]["operator"]
    unit = binding.get("unit", "")
    value_scale = binding.get("value_scale", 1.0)
    if (
        not isinstance(value_scale, (int, float))
        or isinstance(value_scale, bool)
    ):
        raise ValueError("stat_summary value_scale must be a number")
    values = [float(row["value"]) * value_scale for row in rows]
    precision = binding.get("precision", 2)
    if not isinstance(precision, int) or precision < 0:
        raise ValueError("stat_summary precision must be a non-negative integer")

    if len(rows) == 1:
        row = rows[0]
        return (
            f"{row['label']}，{variable}{operator}为"
            f"{_number(values[0], precision)}{unit}。"
        )

    maximum_index = values.index(max(values))
    minimum_index = values.index(min(values))
    maximum = rows[maximum_index]
    minimum = rows[minimum_index]
    direction = _direction(values[0], values[-1])
    return (
        f"{rows[0]['label']}至{rows[-1]['label']}期间，"
        f"{variable}{operator}平均为{_number(mean(values), precision)}{unit}；"
        f"最高值出现在{maximum['label']}，为"
        f"{_number(values[maximum_index], precision)}{unit}；"
        f"最低值出现在{minimum['label']}，为"
        f"{_number(values[minimum_index], precision)}{unit}，"
        f"期末较期初总体呈{direction}。"
    )


def filter_records(records: Iterable[dict], filters: dict | None) -> list[dict]:
    filters = filters or {}
    return [
        record
        for record in records
        if all(record.get(key) == value for key, value in filters.items())
    ]


def _filter_rows(stats: list[dict], binding: dict) -> list[dict]:
    filters = {
        key: binding[key]
        for key in ("variable", "operator")
        if key in binding
    }
    return filter_records(stats, filters)


def _number(value: float, precision: int) -> str:
    return f"{value:.{precision}f}"


def _direction(first: float, last: float) -> str:
    tolerance = max(abs(first), abs(last), 1.0) * 1e-9
    if last > first + tolerance:
        return "上升"
    if last < first - tolerance:
        return "下降"
    return "平稳"
