from pathlib import Path
from typing import Any

from cwr_engine.registries.operators import build_operator_registry
from cwr_engine.registries.plots import build_plot_registry
from cwr_engine.registries.variables import build_variable_registry
from cwr_engine.plotting.validation import validate_plot_requests
from cwr_engine.steps import export, mask, plot, prepare, stat, subset, transform
from cwr_engine.steps.report_inputs import write_report_inputs
from cwr_engine.task_schema import load_task


SUPPORTED_OUTPUT_KINDS = {
    "region_table",
    "figure_timeseries",
    "figure_distribution",
    "figure_bar_compare",
    "grid_nc",
    "report_inputs",
}


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


def _validate_variables(task, variable_registry: dict) -> None:
    if not task.variables:
        raise ValueError("At least one variable is required")
    if len(task.variables) != len(set(task.variables)):
        raise ValueError("Duplicate variables are not allowed")
    for variable in task.variables:
        if variable not in variable_registry:
            raise ValueError(f"Unsupported variable: {variable}")


def _validate_operators(task, operator_registry: dict) -> None:
    if not task.operators:
        raise ValueError("At least one operator is required")
    if len(task.operators) != len(set(task.operators)):
        raise ValueError("Duplicate operators are not allowed")
    for operator in task.operators:
        if operator not in operator_registry:
            raise ValueError(f"Unsupported operator: {operator}")


def _validate_time_scales(
    task,
    variable_registry: dict,
    operator_registry: dict,
) -> None:
    source_scale = task.data_source.get("time_scale")
    if source_scale not in {"day", "month", "year"}:
        raise ValueError("data_source.time_scale must be one of: day, month, year")
    for time_slice in task.time_slices:
        if time_slice.scale != "range" and time_slice.scale != source_scale:
            raise ValueError(
                f"Data source time scale '{source_scale}' does not match "
                f"time slice scale '{time_slice.scale}'"
            )
        for variable in task.variables:
            if source_scale not in variable_registry[variable]["supported_scales"]:
                raise ValueError(
                    f"Variable {variable} does not support time scale {source_scale}"
                )
        for operator in task.operators:
            if source_scale not in operator_registry[operator]["supported_scales"]:
                raise ValueError(
                    f"Operator {operator} does not support time scale {source_scale}"
                )


def run_task(task_path: Path, output_root: Path | None = None) -> Path:
    task = load_task(task_path)
    return run_engine_task(task, task_path, output_root)


def run_engine_task(task, task_path: Path, output_root: Path | None = None) -> Path:
    variable_registry = build_variable_registry()
    operator_registry = build_operator_registry()
    plot_registry = build_plot_registry()
    _validate_output_requests(task)
    _validate_variables(task, variable_registry)
    _validate_operators(task, operator_registry)
    _validate_time_scales(task, variable_registry, operator_registry)
    validate_plot_requests(task, plot_registry)
    root = output_root or Path(task.output_root)
    root.mkdir(parents=True, exist_ok=True)
    context = {
        "task": task,
        "task_path": task_path,
        "output_root": root,
        "variable_registry": variable_registry,
        "operator_registry": operator_registry,
        "plot_registry": plot_registry,
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


def run_engine_task_from_prepared(
    task,
    task_path: Path,
    prepared_dataset: Any,
    mask_data: Any,
    mask_bundle: Any,
    output_root: Path,
) -> Path:
    """Run pipeline steps for a task that has already been prepared and masked.

    Skips prepare and mask; executes subset, transform, stat, plot, export and
    report_inputs as required by the task's workflow_steps.  This allows an
    orchestrator to share one product discovery, one load and one mask across
    multiple standard requests.
    """
    variable_registry = build_variable_registry()
    operator_registry = build_operator_registry()
    plot_registry = build_plot_registry()
    _validate_output_requests(task)
    _validate_variables(task, variable_registry)
    _validate_operators(task, operator_registry)
    _validate_time_scales(task, variable_registry, operator_registry)
    validate_plot_requests(task, plot_registry)
    output_root.mkdir(parents=True, exist_ok=True)
    context: dict[str, Any] = {
        "task": task,
        "task_path": task_path,
        "output_root": output_root,
        "variable_registry": variable_registry,
        "operator_registry": operator_registry,
        "plot_registry": plot_registry,
        "prepared_dataset": prepared_dataset,
        "mask_data": mask_data,
        "mask_bundle": mask_bundle,
        "artifacts": [],
        "runtime": {
            "workflow_steps": task.workflow_steps,
            "executed_steps": [],
            "used_cache": [],
        },
    }
    for step_name in task.workflow_steps:
        if step_name in {"prepare", "mask"}:
            continue
        if step_name == "report_inputs":
            break
        (output_root / step_name).mkdir(parents=True, exist_ok=True)
        runner = STEP_RUNNERS[step_name]
        context = runner(context)
    context["runtime"]["stat_results"] = context.get("stat_results", [])
    requested_kinds = {request.kind for request in task.outputs}
    if "report_inputs" in requested_kinds and "report_inputs" in task.workflow_steps:
        report_request = next(request for request in task.outputs if request.kind == "report_inputs")
        return write_report_inputs(
            task=task,
            output_root=output_root,
            artifacts=context["artifacts"],
            runtime=context["runtime"],
            name=report_request.name,
        )
    return output_root
