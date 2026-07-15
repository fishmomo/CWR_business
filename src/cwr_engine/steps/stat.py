def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("stat")
    context["stat_results"] = []
    for variable, result in context["variable_results"].items():
        for item in result["transformed_slices"]:
            value = float(item["timeseries_data"].mean().item())
            context["stat_results"].append(
                {
                    "label": item["time_slice"].label,
                    "variable": variable,
                    "operator": "mean",
                    "value": value,
                }
            )
    return context
