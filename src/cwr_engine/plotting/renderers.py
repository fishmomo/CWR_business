from __future__ import annotations

from pathlib import Path
import re

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def render_timeseries(context: dict, request, specification: dict) -> None:
    params = {**specification["defaults"], **request.params}
    output_root: Path = context["output_root"]
    for variable, result in context["variable_results"].items():
        series = result["timeseries_data"]
        target = output_root / "plot" / f"{request.name}_{_file_part(variable)}.png"
        fig, ax = plt.subplots(figsize=tuple(params["figsize"]))
        try:
            ax.plot(
                series["time"].values,
                series.values,
                color=params["line_color"],
            )
            ax.set_title(_title(params["title"], variable=variable))
            ax.set_xlabel("Time")
            ax.set_ylabel(params["ylabel"] or _unit_or_variable(result, variable))
            fig.autofmt_xdate()
            _save(fig, target, params["dpi"])
        finally:
            plt.close(fig)
        context["artifacts"].append(
            {
                "kind": request.kind,
                "path": str(target),
                "variable": variable,
            }
        )


def render_distribution(context: dict, request, specification: dict) -> None:
    params = {**specification["defaults"], **request.params}
    output_root: Path = context["output_root"]
    color_map = matplotlib.colormaps[params["cmap"]].with_extremes(
        bad=(0, 0, 0, 0)
    )
    for variable, result in context["variable_results"].items():
        for item in result["transformed_slices"]:
            label = item["time_slice"].label
            for operator in context["task"].operators:
                reducer = context["operator_registry"][operator]["apply"]
                grid = reducer(item["masked_data"], dim="time")
                target = output_root / "plot" / (
                    f"{request.name}_{_file_part(label)}_{_file_part(variable)}_"
                    f"{_file_part(operator)}.png"
                )
                fig, ax = plt.subplots(figsize=tuple(params["figsize"]))
                try:
                    image = ax.pcolormesh(
                        grid["lon"].values,
                        grid["lat"].values,
                        grid.values,
                        shading="auto",
                        cmap=color_map,
                        vmin=params["vmin"],
                        vmax=params["vmax"],
                    )
                    ax.set_title(
                        _title(
                            params["title"],
                            label=label,
                            variable=variable,
                            operator=operator,
                        )
                    )
                    ax.set_xlabel("Longitude")
                    ax.set_ylabel("Latitude")
                    colorbar = fig.colorbar(image, ax=ax)
                    colorbar.set_label(
                        params["colorbar_label"]
                        or _unit_or_variable(result, variable)
                    )
                    _save(fig, target, params["dpi"])
                finally:
                    plt.close(fig)
                context["artifacts"].append(
                    {
                        "kind": request.kind,
                        "path": str(target),
                        "variable": variable,
                        "operator": operator,
                        "label": label,
                    }
                )


def render_bar_compare(context: dict, request, specification: dict) -> None:
    params = {**specification["defaults"], **request.params}
    output_root: Path = context["output_root"]
    stat_results = context.get("stat_results", [])
    for variable, result in context["variable_results"].items():
        for operator in context["task"].operators:
            rows = [
                item
                for item in stat_results
                if item["variable"] == variable and item["operator"] == operator
            ]
            labels = [item["label"] for item in rows]
            values = [item["value"] for item in rows]
            target = output_root / "plot" / (
                f"{request.name}_{_file_part(variable)}_{_file_part(operator)}.png"
            )
            fig, ax = plt.subplots(figsize=tuple(params["figsize"]))
            try:
                ax.bar(labels, values, color=params["bar_color"])
                ax.set_title(
                    _title(
                        params["title"],
                        variable=variable,
                        operator=operator,
                    )
                )
                ax.set_xlabel("Time slice")
                ax.set_ylabel(params["ylabel"] or _unit_or_variable(result, variable))
                ax.tick_params(axis="x", rotation=30)
                _save(fig, target, params["dpi"])
            finally:
                plt.close(fig)
            context["artifacts"].append(
                {
                    "kind": request.kind,
                    "path": str(target),
                    "variable": variable,
                    "operator": operator,
                }
            )


def _unit_or_variable(result: dict, variable: str) -> str:
    unit = result["specification"].get("unit")
    return unit or variable


def _title(template: str, **values: str) -> str:
    return template.format(**values)


def _file_part(value: str) -> str:
    return re.sub(r'[<>:"/\\|?*\s]+', "_", value).strip("_")


def _save(fig, target: Path, dpi: int) -> None:
    fig.savefig(target, dpi=dpi, bbox_inches="tight")
