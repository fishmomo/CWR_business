import xarray as xr


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("transform")
    variable = context["task"].variables[0]
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
    context["transformed_slices"] = transformed_slices
    context["timeseries_data"] = xr.concat(
        [item["timeseries_data"] for item in transformed_slices],
        dim="time",
    ).sortby("time")
    context["grid_mean_data"] = transformed_slices[0]["grid_mean_data"]
    return context
