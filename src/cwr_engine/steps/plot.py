def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("plot")
    registry_by_kind = {
        specification["request_kind"]: specification
        for specification in context["plot_registry"].values()
    }
    for request in context["task"].outputs:
        specification = registry_by_kind.get(request.kind)
        if specification is not None:
            specification["renderer"](context, request, specification)
    return context
