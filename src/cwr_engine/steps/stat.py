def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("stat")
    variable = context["task"].variables[0]
    operator = context["task"].operators[0]
    context["stat_results"] = []
    for item in context["transformed_slices"]:
        value = float(item["timeseries_data"].mean().item())
        context["stat_results"].append(
            {
                "label": item["time_slice"].label,
                "variable": variable,
                "operator": operator,
                "value": value,
            }
        )
    return context
