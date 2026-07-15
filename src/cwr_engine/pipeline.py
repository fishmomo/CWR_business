from pathlib import Path

from cwr_engine.steps import export, mask, plot, prepare, stat, subset, transform
from cwr_engine.steps.report_inputs import write_report_inputs
from cwr_engine.task_schema import load_task


SUPPORTED_OUTPUT_KINDS = {"region_table", "figure_timeseries", "grid_nc", "report_inputs"}


STEP_RUNNERS = {
    "prepare": prepare.run,
    "mask": mask.run,
    "subset": subset.run,
    "transform": transform.run,
    "stat": stat.run,
    "plot": plot.run,
    "export": export.run,
}


def _validate_output_requests(task) -> None:
    for request in task.outputs:
        if request.kind not in SUPPORTED_OUTPUT_KINDS:
            raise ValueError(f"Unsupported output kind: {request.kind}")


def run_task(task_path: Path, output_root: Path | None = None) -> Path:
    task = load_task(task_path)
    _validate_output_requests(task)
    root = output_root or Path(task.output_root)
    root.mkdir(parents=True, exist_ok=True)
    context = {
        "task": task,
        "task_path": task_path,
        "output_root": root,
        "artifacts": [],
        "runtime": {
            "workflow_steps": task.workflow_steps,
            "executed_steps": [],
            "used_cache": [],
        },
    }
    for step_name in task.workflow_steps:
        if step_name == "report_inputs":
            break
        (root / step_name).mkdir(parents=True, exist_ok=True)
        runner = STEP_RUNNERS[step_name]
        context = runner(context)
    context["runtime"]["stat_results"] = context.get("stat_results", [])
    requested_kinds = {request.kind for request in task.outputs}
    if "report_inputs" in requested_kinds and "report_inputs" in task.workflow_steps:
        report_request = next(request for request in task.outputs if request.kind == "report_inputs")
        return write_report_inputs(
            task=task,
            output_root=root,
            artifacts=context["artifacts"],
            runtime=context["runtime"],
            name=report_request.name,
        )
    return root
