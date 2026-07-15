from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("plot")
    output_root: Path = context["output_root"]
    requests = [request for request in context["task"].outputs if request.kind == "figure_timeseries"]
    for variable, result in context["variable_results"].items():
        series = result["timeseries_data"]
        for request in requests:
            target = output_root / "plot" / f"{request.name}_{variable}.png"
            fig, ax = plt.subplots()
            ax.plot(series["time"].values, series.values)
            ax.set_title("Demo Time Series")
            ax.set_ylabel(variable)
            fig.savefig(target, dpi=120, bbox_inches="tight")
            plt.close(fig)
            context["artifacts"].append(
                {
                    "kind": "figure_timeseries",
                    "path": str(target),
                }
            )
    return context
