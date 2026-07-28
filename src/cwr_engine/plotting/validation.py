from __future__ import annotations

from string import Formatter

import matplotlib
from matplotlib.colors import is_color_like


def validate_plot_requests(task, plot_registry: dict) -> None:
    registry_by_kind = {
        specification["request_kind"]: specification
        for specification in plot_registry.values()
    }
    for request in task.outputs:
        specification = registry_by_kind.get(request.kind)
        if specification is None:
            continue
        _validate_params(request, specification)
        _validate_workflow(task, request.kind, specification)


def _validate_params(request, specification: dict) -> None:
    params = request.params
    if not isinstance(params, dict):
        raise ValueError(f"Plot params for {request.kind} must be an object")
    unknown = sorted(set(params) - set(specification["allowed_params"]))
    if unknown:
        raise ValueError(
            f"Unsupported plot parameter for {request.kind}: {unknown[0]}"
        )

    if "title" in params:
        _validate_title(params["title"], specification["title_fields"])
    if "figsize" in params:
        figsize = params["figsize"]
        if (
            not isinstance(figsize, (list, tuple))
            or len(figsize) != 2
            or not all(_is_number(item) for item in figsize)
        ):
            raise ValueError("figsize must contain two numbers")
        if any(item <= 0 for item in figsize):
            raise ValueError("figsize values must be positive")
    if "dpi" in params:
        if (
            not isinstance(params["dpi"], int)
            or isinstance(params["dpi"], bool)
            or params["dpi"] <= 0
        ):
            raise ValueError("dpi must be a positive integer")
    if "cmap" in params and params["cmap"] not in matplotlib.colormaps:
        raise ValueError(f"Invalid color map: {params['cmap']}")
    for color_key in ("line_color", "bar_color"):
        if color_key in params and not is_color_like(params[color_key]):
            raise ValueError(f"Invalid color: {params[color_key]}")
    for limit in ("vmin", "vmax"):
        if limit in params and params[limit] is not None and not _is_number(
            params[limit]
        ):
            raise ValueError(f"{limit} must be a number or null")
    if (
        params.get("vmin") is not None
        and params.get("vmax") is not None
        and params["vmin"] >= params["vmax"]
    ):
        raise ValueError("vmin must be less than vmax")
    for label_key in ("ylabel", "colorbar_label"):
        if label_key in params and params[label_key] is not None and not isinstance(
            params[label_key], str
        ):
            raise ValueError(f"{label_key} must be a string or null")


def _validate_title(template, allowed_fields: set[str]) -> None:
    if not isinstance(template, str):
        raise ValueError("title must be a string")
    try:
        parsed = Formatter().parse(template)
        for _, field_name, _, _ in parsed:
            if field_name and field_name not in allowed_fields:
                raise ValueError(f"Unsupported title field: {field_name}")
    except ValueError as error:
        if str(error).startswith("Unsupported title field"):
            raise
        raise ValueError(f"Invalid title template: {error}") from error


def _validate_workflow(task, request_kind: str, specification: dict) -> None:
    if "plot" not in task.workflow_steps:
        return
    plot_index = task.workflow_steps.index("plot")
    for required_step in specification["required_steps"]:
        if (
            required_step not in task.workflow_steps
            or task.workflow_steps.index(required_step) >= plot_index
        ):
            raise ValueError(
                f"{request_kind} requires {required_step} before plot"
            )


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
