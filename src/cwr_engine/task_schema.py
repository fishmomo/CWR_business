import json
from pathlib import Path

from cwr_engine.models.output_request import OutputRequest
from cwr_engine.models.region import build_region_spec
from cwr_engine.models.task import EngineTask
from cwr_engine.models.time_slice import TimeSlice, normalize_time_slice


def load_task(path: Path) -> EngineTask:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EngineTask(
        task_id=payload["task_id"],
        data_source=payload["data_source"],
        time_slices=[_load_time_slice(item) for item in payload["time_slices"]],
        region_spec=build_region_spec(payload["region_spec"]),
        variables=payload["variables"],
        operators=payload["operators"],
        outputs=[OutputRequest(**item) for item in payload["outputs"]],
        workflow_steps=payload["workflow_steps"],
        reuse_policy=payload["reuse_policy"],
        output_root=payload["output_root"],
    )


def _load_time_slice(payload: dict) -> TimeSlice:
    if payload["scale"] in {"year", "month", "day"}:
        return normalize_time_slice(payload)
    return TimeSlice(**payload)
