import xarray as xr

from cwr_engine.registries.variables import resolve_source_keys


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("transform")
    variable_results = {}
    for variable in context["task"].variables:
        specification = context["variable_registry"][variable]
        source_keys = resolve_source_keys(
            variable,
            context["variable_registry"],
            context["prepared_dataset"],
            context["task"].data_source.get("variable_map"),
        )
        transformed_slices = []
        for item in context["sliced_subsets"]:
            source_data = _build_source_data(
                item["dataset"],
                source_keys,
                specification,
            )
            masked = source_data.where(item["mask_data"]).rename(variable)
            masked.attrs["source_key"] = ",".join(source_keys)
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
            "source_key": ",".join(source_keys),
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


def _build_source_data(dataset, source_keys: list[str], specification: dict):
    if len(source_keys) == 1:
        return dataset[source_keys[0]]
    if specification.get("source_operation") == "difference" and len(source_keys) == 2:
        return dataset[source_keys[0]] - dataset[source_keys[1]]
    raise ValueError(
        f"Unsupported source operation for fields: {', '.join(source_keys)}"
    )
