import json
from pathlib import Path


def write_report_inputs(
    task,
    output_root: Path,
    artifacts: list[dict] | None = None,
    runtime: dict | None = None,
    name: str = "report_inputs",
) -> Path:
    target_dir = output_root / "report_inputs"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{name}.json"
    payload = {
        "schema_version": 1,
        "task": {
            "task_id": task.task_id,
            "status": "success",
            "output_root": str(output_root),
        },
        "inputs": {
            "data_source": task.data_source,
            "time_slices": [item.__dict__ for item in task.time_slices],
            "region_spec": {
                "kind": task.region_spec.kind,
                "payload": task.region_spec.payload,
            },
            "variables": task.variables,
            "operators": task.operators,
            "requested_outputs": [item.__dict__ for item in task.outputs],
        },
        "artifacts": artifacts or [],
        "runtime": runtime or {
            "workflow_steps": task.workflow_steps,
            "executed_steps": [],
            "used_cache": [],
        },
        "stats": runtime.get("stat_results", []) if runtime else [],
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
