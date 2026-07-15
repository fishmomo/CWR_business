from pathlib import Path

from cwr_engine.steps import export, mask, plot, prepare, stat, subset, transform
from cwr_engine.steps.report_inputs import write_report_inputs
from cwr_engine.task_schema import load_task


STEP_RUNNERS = {
    "prepare": prepare.run,
    "mask": mask.run,
    "subset": subset.run,
    "transform": transform.run,
    "stat": stat.run,
    "plot": plot.run,
    "export": export.run,
}


def run_task(task_path: Path, output_root: Path | None = None) -> Path:
    task = load_task(task_path)
    root = output_root or Path(task.output_root)
    root.mkdir(parents=True, exist_ok=True)
    for name in [*STEP_RUNNERS.keys(), "report_inputs"]:
        (root / name).mkdir(parents=True, exist_ok=True)
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
        runner = STEP_RUNNERS[step_name]
        context = runner(context)
    context["runtime"]["stat_results"] = context.get("stat_results", [])
    return write_report_inputs(
        task=task,
        output_root=root,
        artifacts=context["artifacts"],
        runtime=context["runtime"],
    )
