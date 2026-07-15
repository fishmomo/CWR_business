# Multi-Variable Results Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute, export, and index every requested variable for tasks using the registered `mean` operator.

**Architecture:** `transform` writes a `variable_results` mapping keyed by task variable. `stat`, `export`, and `plot` consume that mapping, creating combined CSV/NC artifacts and per-variable PNG files. Operator validation rejects any request other than the currently implemented `mean`.

**Tech Stack:** Python 3.12, xarray, SciPy NetCDF, Matplotlib, pytest.

## Global Constraints

- Run all Python commands with `conda run -n cwr_py312`.
- Support all requested variables; do not silently select index zero.
- Support only the registered `mean` operator in this delivery.
- Keep report generation outside `cwr_engine`.

---

### Task 1: Establish multi-variable transform and mean-statistics results

**Files:**
- Modify: `src/cwr_engine/steps/transform.py`
- Modify: `src/cwr_engine/steps/stat.py`
- Modify: `src/cwr_engine/pipeline.py`
- Modify: `tests/test_pipeline_smoke.py`

**Interfaces:**
- Consumes: `task.variables: list[str]`, `task.operators: list[str]`, and `sliced_subsets`.
- Produces: `context["variable_results"][variable]` and one `stat_results` row per label/variable/mean tuple.

- [ ] **Step 1: Add a failing two-variable task test**

Write a NetCDF fixture with `temp` values `[[[1, 2], [3, 4]]]` and `precip`
values `[[[10, 20], [30, 40]]]`; run one year task with both variables, output a
`region_table`, and assert the CSV rows are:

```python
assert rows[1] == ["2025", "temp", "mean", "2.50"]
assert rows[2] == ["2025", "precip", "mean", "25.00"]
```

Add an operator-validation test:

```python
with pytest.raises(ValueError, match="Unsupported operator: max"):
    run_task(task_path, tmp_path / "result")
```

- [ ] **Step 2: Verify RED**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "multiple_variables or unsupported_operator" -q`

Expected: FAIL because only `temp` and the first operator are used.

- [ ] **Step 3: Implement variable mapping and operator validation**

In `transform.py`, for each `variable` in `context["task"].variables`, create a
per-slice list and store:

```python
context["variable_results"][variable] = {
    "transformed_slices": transformed_slices,
    "timeseries_data": xr.concat(
        [item["timeseries_data"] for item in transformed_slices], dim="time"
    ).sortby("time"),
    "grid_mean_data": transformed_slices[0]["grid_mean_data"],
}
```

In `pipeline.py`, reject every operator not equal to `mean` before creating the
output root. In `stat.py`, loop over `variable_results.items()` and append one
row per transformed slice with `operator == "mean"`.

- [ ] **Step 4: Verify GREEN**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "multiple_variables or unsupported_operator" -q`

Expected: PASS.

### Task 2: Export all requested variables to NC and per-variable figures

**Files:**
- Modify: `src/cwr_engine/steps/export.py`
- Modify: `src/cwr_engine/steps/plot.py`
- Modify: `tests/test_pipeline_smoke.py`

**Interfaces:**
- Consumes: `context["variable_results"]`.
- Produces: one multi-variable `grid_nc` dataset and `<request.name>_<variable>.png` files.

- [ ] **Step 1: Add failing NC and figure tests**

For the two-variable fixture, request `grid_nc` named `annual_grids` and one
`figure_timeseries` named `annual_series`:

```python
dataset = xr.load_dataset(root / "export" / "annual_grids.nc", engine="scipy")
assert set(dataset.data_vars) == {"temp", "precip"}
assert (root / "plot" / "annual_series_temp.png").exists()
assert (root / "plot" / "annual_series_precip.png").exists()
```

- [ ] **Step 2: Verify RED**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider tests/test_pipeline_smoke.py -k "multiple_variables_grid or multiple_variables_figures" -q`

Expected: FAIL because NC and plot code use only `variables[0]`.

- [ ] **Step 3: Implement all-variable artifacts**

In `export.py`, build a dataset with:

```python
grid_dataset = xr.Dataset(
    {variable: result["grid_mean_data"] for variable, result in context["variable_results"].items()}
)
```

Write that dataset for each `grid_nc` request. In `plot.py`, nest the figure
request loop inside `variable_results.items()`, use `result["timeseries_data"]`,
label with `variable`, and write `f"{request.name}_{variable}.png"`.

- [ ] **Step 4: Verify GREEN and full regression**

Run: `conda run -n cwr_py312 python -m pytest -p no:cacheprovider --basetemp .test-tmp-multi-variable-release -q`

Expected: all tests pass.

- [ ] **Step 5: Commit**

```powershell
git add src/cwr_engine/pipeline.py src/cwr_engine/steps/transform.py src/cwr_engine/steps/stat.py src/cwr_engine/steps/export.py src/cwr_engine/steps/plot.py tests/test_pipeline_smoke.py
git commit -m "feat: compute requested variables"
```
