import xarray as xr

from cwr_engine.registries.variables import resolve_source_key


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("transform")
    variable_results = {}
    for variable in context["task"].variables:
        specification = context["variable_registry"][variable]
        source_key = resolve_source_key(
            variable,
            context["variable_registry"],
            context["prepared_dataset"],
            context["task"].data_source.get("variable_map"),
        )
        transformed_slices = []
        for item in context["sliced_subsets"]:
            masked = item["dataset"][source_key].where(item["mask_data"]).rename(variable)
            masked.attrs["source_key"] = source_key
            if specification["unit"] and "units" not in masked.attrs:
                masked.attrs["units"] = specification["unit"]
            transformed_slices.append(
                {
                    "time_slice": item["time_slice"],
                    "masked_data": masked,
                    "timeseries_data": masked.mean(dim=("lat", "lon")),
                }
            )
        variable_results[variable] = {
            "specification": specification,
            "source_key": source_key,
            "transformed_slices": transformed_slices,
            "timeseries_data": xr.concat(
                [item["timeseries_data"] for item in transformed_slices],
                dim="time",
            ).sortby("time"),
        }
    context["variable_results"] = variable_results
    first_result = variable_results[context["task"].variables[0]]
    context["transformed_slices"] = first_result["transformed_slices"]
    context["timeseries_data"] = first_result["timeseries_data"]
    return context
