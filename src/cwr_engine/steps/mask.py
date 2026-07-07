def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("mask")
    return context
