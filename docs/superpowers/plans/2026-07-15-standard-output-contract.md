# Standard Output Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `EngineTask.outputs` select exactly which standard CSV, PNG, NetCDF, and report-input artifacts a run creates.

**Architecture:** The pipeline validates requested output kinds before executing workflow steps. Export and plot steps filter task output requests by kind and use each request name as the filename stem. The pipeline writes report inputs only when both requested and listed in the workflow, returning the output root for artifact-only tasks.

**Tech Stack:** Python 3.12, xarray, SciPy NetCDF backend, Matplotlib, pytest.

## Global Constraints

- Run all Python commands with `conda run -n cwr_py312`.
- Preserve the two-layer boundary: no DOCX generation in `cwr_engine`.
- Only supported output kinds are `region_table`, `figure_timeseries`, `grid_nc`, and `report_inputs`.
- `OutputRequest.name` is the generated filename stem.
- Add a failing test before every production behavior change.

---

### Task 1: Validate output requests and make report inputs optional

**Files:**
- Modify: `src/cwr_engine/pipeline.py`
- Modify: `tests/test_pipeline_smoke.py`

**Interfaces:**
- Consumes: `EngineTask.outputs: list[OutputRequest]` and `EngineTask.workflow_steps: list[str]`.
- Produces: `run_task(task_path, output_root) -> Path`, returning report-input JSON when requested or the output root otherwise.

- [ ] **Step 1: Write failing tests for artifact-only and invalid-output tasks**

Add these tests with the existing minimal task payload copied and its `outputs` changed:

```python
def test_csv_only_task_returns_output_root_without_report_inputs(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "region_table", "name": "annual_table"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "stat", "export"],
    )
    result = run_task(task_path, tmp_path / "result")
    assert result == tmp_path / "result"
    assert (result / "export" / "annual_table.csv").exists()
    assert not (result / "report_inputs").exists()


def test_unknown_output_kind_fails_before_creating_artifacts(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "not_supported", "name": "bad"}],
        workflow_steps=["prepare"],
    )
    with pytest.raises(ValueError, match="Unsupported output kind: not_supported"):
        run_task(task_path, tmp_path / "result")
    assert not (tmp_path / "result").exists()
```

`_write_demo_task` is a test helper in the same module that writes a complete
demo JSON task and accepts the named `outputs` and `workflow_steps` arguments.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "csv_only or unknown_output" -q`

Expected: the CSV-only test receives a report-input path and the invalid task
does not raise the requested validation error.

- [ ] **Step 3: Implement validation and optional report inputs**

In `pipeline.py`, define:

```python
SUPPORTED_OUTPUT_KINDS = {"region_table", "figure_timeseries", "grid_nc", "report_inputs"}


def _validate_output_requests(task) -> None:
    for request in task.outputs:
        if request.kind not in SUPPORTED_OUTPUT_KINDS:
            raise ValueError(f"Unsupported output kind: {request.kind}")
```

Call `_validate_output_requests(task)` before creating `root`. After workflow
execution, call `write_report_inputs(...)` only when `report_inputs` is both
requested and included in `workflow_steps`; select the request named
`report_inputs` and pass its `name` to the writer. Otherwise return `root`.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "csv_only or unknown_output" -q`

Expected: PASS.

- [ ] **Step 5: Commit the optional-report behavior**

```powershell
git add src/cwr_engine/pipeline.py tests/test_pipeline_smoke.py
git commit -m "feat: validate requested output artifacts"
```

### Task 2: Export named CSV and NetCDF artifacts

**Files:**
- Modify: `src/cwr_engine/steps/export.py`
- Modify: `tests/test_pipeline_smoke.py`

**Interfaces:**
- Consumes: `context["task"].outputs`, `context["stat_results"]`, and `context["grid_mean_data"]`.
- Produces: artifact records of kind `region_table` and `grid_nc` with task-requested file names.

- [ ] **Step 1: Write failing CSV-name and NetCDF tests**

```python
def test_requested_csv_name_controls_export_filename(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "region_table", "name": "annual_table"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "stat", "export"],
    )
    root = run_task(task_path, tmp_path / "result")
    assert (root / "export" / "annual_table.csv").exists()
    assert not (root / "export" / "region_table.csv").exists()


def test_grid_nc_request_exports_masked_grid(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "grid_nc", "name": "annual_grid"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "export"],
    )
    root = run_task(task_path, tmp_path / "result")
    dataset = xr.load_dataset(root / "export" / "annual_grid.nc", engine="scipy")
    assert list(dataset.data_vars) == ["temp"]
    assert dataset["temp"].dims == ("lat", "lon")
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "requested_csv_name or grid_nc_request" -q`

Expected: FAIL because export uses a fixed CSV name and does not create NetCDF.

- [ ] **Step 3: Implement filtered named exports**

Add an internal request filter:

```python
def _requests_for(context: dict, kind: str):
    return [request for request in context["task"].outputs if request.kind == kind]
```

For each `region_table` request, write `output_root / "export" / f"{request.name}.csv"`.
For each `grid_nc` request, write
`context["grid_mean_data"].to_dataset(name=context["task"].variables[0])` to
`output_root / "export" / f"{request.name}.nc"` using `engine="scipy"`.
Append one artifact record for each file. Do not create any export artifact
when neither request kind is present.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "requested_csv_name or grid_nc_request" -q`

Expected: PASS.

- [ ] **Step 5: Commit the export contract**

```powershell
git add src/cwr_engine/steps/export.py tests/test_pipeline_smoke.py
git commit -m "feat: export requested CSV and NetCDF artifacts"
```

### Task 3: Produce named figures and named report-input JSON

**Files:**
- Modify: `src/cwr_engine/steps/plot.py`
- Modify: `src/cwr_engine/steps/report_inputs.py`
- Modify: `tests/test_pipeline_smoke.py`

**Interfaces:**
- Consumes: output requests of kind `figure_timeseries` and `report_inputs`.
- Produces: named PNG figures and named report JSON files with complete artifact indexes.

- [ ] **Step 1: Write failing selective-output tests**

```python
def test_figure_only_task_creates_only_requested_figure(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[{"kind": "figure_timeseries", "name": "annual_series"}],
        workflow_steps=["prepare", "mask", "subset", "transform", "plot"],
    )
    root = run_task(task_path, tmp_path / "result")
    assert (root / "plot" / "annual_series.png").exists()
    assert not (root / "export").exists()
    assert not (root / "report_inputs").exists()


def test_report_inputs_uses_requested_name_and_indexes_created_artifacts(tmp_path: Path):
    task_path = _write_demo_task(
        tmp_path,
        outputs=[
            {"kind": "region_table", "name": "annual_table"},
            {"kind": "report_inputs", "name": "annual_report_inputs"},
        ],
        workflow_steps=["prepare", "mask", "subset", "transform", "stat", "export", "report_inputs"],
    )
    report_path = run_task(task_path, tmp_path / "result")
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert report_path.name == "annual_report_inputs.json"
    assert [item["kind"] for item in payload["artifacts"]] == ["region_table"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "figure_only or report_inputs_uses" -q`

Expected: FAIL because figure and report-output names are fixed and output
directories are pre-created.

- [ ] **Step 3: Implement named selective plot and report outputs**

In `plot.py`, loop over `figure_timeseries` requests and write
`plot/<request.name>.png`; append one matching artifact record per request.
In `report_inputs.py`, accept `name: str = "report_inputs"` and write
`report_inputs/<name>.json`. In `pipeline.py`, create only the directory used
by a step when that step runs; do not pre-create all step directories.

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "figure_only or report_inputs_uses" -q`

Expected: PASS.

- [ ] **Step 5: Run release verification and commit**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider --basetemp .test-tmp-output-contract -q`

Expected: all tests pass.

```powershell
git add src/cwr_engine/pipeline.py src/cwr_engine/steps/plot.py src/cwr_engine/steps/report_inputs.py tests/test_pipeline_smoke.py
git commit -m "feat: generate requested figures and report inputs"
```
