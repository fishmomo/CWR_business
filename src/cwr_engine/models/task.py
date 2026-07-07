from dataclasses import dataclass
from typing import Any

from cwr_engine.models.output_request import OutputRequest
from cwr_engine.models.region import RegionSpec
from cwr_engine.models.time_slice import TimeSlice


@dataclass(frozen=True)
class EngineTask:
    task_id: str
    data_source: dict[str, Any]
    time_slices: list[TimeSlice]
    region_spec: RegionSpec
    variables: list[str]
    operators: list[str]
    outputs: list[OutputRequest]
    workflow_steps: list[str]
    reuse_policy: dict[str, Any]
    output_root: str
