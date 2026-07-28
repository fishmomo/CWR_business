def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("stat")
    context["stat_results"] = []
    for variable, result in context["variable_results"].items():
        for item in result["transformed_slices"]:
            for operator in context["task"].operators:
                reducer = context["operator_registry"][operator]["apply"]
                value = float(reducer(item["masked_data"]).item())
                context["stat_results"].append(
                    {
                        "label": item["time_slice"].label,
                        "variable": variable,
                        "operator": operator,
                        "value": value,
                    }
                )
    return context
