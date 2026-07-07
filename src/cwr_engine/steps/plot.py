from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("plot")
    output_root: Path = context["output_root"]
    target = output_root / "plot" / "timeseries.png"
    series = context["timeseries_data"]
    fig, ax = plt.subplots()
    ax.plot(series["time"].values, series.values)
    ax.set_title("Demo Time Series")
    ax.set_ylabel(context["task"].variables[0])
    fig.savefig(target, dpi=120, bbox_inches="tight")
    plt.close(fig)
    context["artifacts"].append(
        {
            "kind": "figure_timeseries",
            "path": str(target),
        }
    )
    return context
