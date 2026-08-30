import csv
from pathlib import Path

import xarray as xr


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
                "name": request.name,
                "path": str(target),
            }
        )
    for request in _requests_for(context, "grid_nc"):
        target = output_root / "export" / f"{request.name}.nc"
        grid_variables = {}
        multiple_operators = len(context["task"].operators) > 1
        for variable, result in context["variable_results"].items():
            for operator in context["task"].operators:
                output_name = (
                    f"{variable}_{operator}" if multiple_operators else variable
                )
                reducer = context["operator_registry"][operator]["apply"]
                grids = [
                    reducer(item["masked_data"], dim="time")
                    for item in result["transformed_slices"]
                ]
                if len(grids) == 1:
                    grid_data = grids[0]
                else:
                    labels = [
                        item["time_slice"].label
                        for item in result["transformed_slices"]
                    ]
                    grid_data = xr.concat(grids, dim=xr.IndexVariable("period", labels))
                grid_data = grid_data.rename(output_name)
                grid_data.attrs["operator"] = operator
                grid_data.attrs["source_variable"] = result["source_key"]
                grid_variables[output_name] = grid_data
        grid_dataset = xr.Dataset(grid_variables)
        grid_dataset.to_netcdf(target, engine="h5netcdf")
        context["artifacts"].append(
            {
                "kind": "grid_nc",
                "name": request.name,
                "path": str(target),
            }
        )
    return context
