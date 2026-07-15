import xarray as xr


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("transform")
    variable_results = {}
    for variable in context["task"].variables:
        transformed_slices = []
        for item in context["sliced_subsets"]:
            masked = item["dataset"][variable].where(item["mask_data"])
            transformed_slices.append(
                {
                    "time_slice": item["time_slice"],
                    "timeseries_data": masked.mean(dim=("lat", "lon")),
                    "grid_mean_data": masked.mean(dim="time"),
                }
            )
        variable_results[variable] = {
            "transformed_slices": transformed_slices,
            "timeseries_data": xr.concat(
                [item["timeseries_data"] for item in transformed_slices],
                dim="time",
            ).sortby("time"),
            "grid_mean_data": transformed_slices[0]["grid_mean_data"],
        }
    context["variable_results"] = variable_results
    first_result = variable_results[context["task"].variables[0]]
    context["transformed_slices"] = first_result["transformed_slices"]
    context["timeseries_data"] = first_result["timeseries_data"]
    context["grid_mean_data"] = first_result["grid_mean_data"]
    return context
