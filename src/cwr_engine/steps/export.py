import csv
from pathlib import Path


def _requests_for(context: dict, kind: str):
    return [request for request in context["task"].outputs if request.kind == kind]


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("export")
    output_root: Path = context["output_root"]
    for request in _requests_for(context, "region_table"):
        target = output_root / "export" / f"{request.name}.csv"
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["label", "variable", "operator", "value"])
            for row in context["stat_results"]:
                writer.writerow([row["label"], row["variable"], row["operator"], f"{row['value']:.2f}"])
        context["artifacts"].append(
            {
                "kind": "region_table",
                "path": str(target),
            }
        )
    for request in _requests_for(context, "grid_nc"):
        target = output_root / "export" / f"{request.name}.nc"
        context["grid_mean_data"].to_dataset(name=context["task"].variables[0]).to_netcdf(target, engine="scipy")
        context["artifacts"].append(
            {
                "kind": "grid_nc",
                "path": str(target),
            }
        )
    return context
