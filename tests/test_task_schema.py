from pathlib import Path

from cwr_engine.task_schema import load_task


def test_load_minimal_task_fixture():
    task = load_task(Path("tests/fixtures/minimal_task.json"))
    assert task.task_id == "demo-run"
    assert task.workflow_steps == [
        "prepare",
        "mask",
        "subset",
        "transform",
        "stat",
        "plot",
        "export",
        "report_inputs",
    ]
    assert task.time_slices[0].scale == "year"
    assert task.region_spec.kind == "bbox"
