def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("prepare")
    return context
