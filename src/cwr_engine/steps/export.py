import csv
from pathlib import Path


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("export")
    output_root: Path = context["output_root"]
    target = output_root / "export" / "region_table.csv"
    with target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["variable", "operator", "value"])
        writer.writerow(["temp", "mean", "0.0"])
    context["artifacts"].append(
        {
            "kind": "region_table",
            "path": str(target),
        }
    )
    return context
