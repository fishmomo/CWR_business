def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("stat")
    return context
