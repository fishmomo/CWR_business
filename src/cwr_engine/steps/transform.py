def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("transform")
    dataset = context["subset_dataset"]
    variable = context["task"].variables[0]
    spatial_mean = dataset[variable].mean(dim=("lat", "lon"))
    temporal_grid_mean = dataset[variable].mean(dim="time")
    context["timeseries_data"] = spatial_mean
    context["grid_mean_data"] = temporal_grid_mean
    return context
