def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("subset")
    task = context["task"]
    dataset = context["prepared_dataset"]
    region = task.region_spec.payload
    time_slice = task.time_slices[0]
    subset_dataset = dataset.sel(
        time=slice(time_slice.start, time_slice.end),
        lat=slice(region["min_lat"], region["max_lat"]),
        lon=slice(region["min_lon"], region["max_lon"]),
    )
    context["subset_dataset"] = subset_dataset
    return context
