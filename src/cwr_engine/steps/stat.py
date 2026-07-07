def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("stat")
    variable = context["task"].variables[0]
    operator = context["task"].operators[0]
    value = float(context["timeseries_data"].mean().item())
    context["stat_results"] = [
        {
            "variable": variable,
            "operator": operator,
            "value": value,
        }
    ]
    return context
