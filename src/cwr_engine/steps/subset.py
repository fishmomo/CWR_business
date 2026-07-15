def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("subset")
    dataset = context["prepared_dataset"]
    bounds = context["mask_bundle"].spatial_bounds
    task = context["task"]
    spatial_subset = dataset.sel(
        lat=slice(bounds["min_lat"], bounds["max_lat"]),
        lon=slice(bounds["min_lon"], bounds["max_lon"]),
    )
    subset_mask_data = context["mask_data"].sel(
        lat=slice(bounds["min_lat"], bounds["max_lat"]),
        lon=slice(bounds["min_lon"], bounds["max_lon"]),
    )
    sliced_subsets = []
    for time_slice in task.time_slices:
        sliced_subsets.append(
            {
                "time_slice": time_slice,
                "dataset": spatial_subset.sel(time=slice(time_slice.start, time_slice.end)),
                "mask_data": subset_mask_data,
            }
        )
    context["subset_dataset"] = sliced_subsets[0]["dataset"]
    context["subset_mask_data"] = subset_mask_data
    context["sliced_subsets"] = sliced_subsets
    return context
