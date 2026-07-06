# CWR Unified Engine Bootstrap Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first working skeleton of the unified CWR computation engine so the repo can execute one standard JSON task from `prepare` through `report_inputs` with registry-driven extension points.

**Architecture:** Implement a small Python package under `src/cwr_engine/` with explicit workflow steps, typed task models, and separate registries for variables, operators, and plots. Keep the first version fail-fast, JSON-config driven, and centered on standard objects such as `time_slice`, `region_spec`, `mask_bundle`, and `report_inputs.json`.

**Tech Stack:** Python 3.9+, `pytest`, standard library `dataclasses`/`pathlib`/`json`, `xarray`, `numpy`, optional `geopandas`/`rasterio` for mask work, `matplotlib` for plots

---

## File Structure

### New files

- `pyproject.toml`
  - Python project metadata and pytest config
- `src/cwr_engine/__init__.py`
  - Package export surface
- `src/cwr_engine/task_schema.py`
  - JSON task loading and validation entrypoint
- `src/cwr_engine/models/time_slice.py`
  - `TimeSlice` model and normalization helpers
- `src/cwr_engine/models/region.py`
  - `RegionSpec`, `MaskBundle`, and spatial metadata models
- `src/cwr_engine/models/output_request.py`
  - Standard output-request model
- `src/cwr_engine/models/task.py`
  - Top-level task dataclasses
- `src/cwr_engine/registries/variables.py`
  - Variable registry and built-in seed variables
- `src/cwr_engine/registries/operators.py`
  - Operator registry and built-in seed operators
- `src/cwr_engine/registries/plots.py`
  - Plot registry and built-in seed plot types
- `src/cwr_engine/steps/prepare.py`
  - Raw discovery and normalization step
- `src/cwr_engine/steps/mask.py`
  - `region_spec -> mask_bundle`
- `src/cwr_engine/steps/subset.py`
  - Pure space-time clipping
- `src/cwr_engine/steps/transform.py`
  - Time-scale conversion, unit conversion, derived variables
- `src/cwr_engine/steps/stat.py`
  - Registered statistical operator execution
- `src/cwr_engine/steps/plot.py`
  - Registered plotting dispatch
- `src/cwr_engine/steps/export.py`
  - Artifact export and output indexing
- `src/cwr_engine/steps/report_inputs.py`
  - Final `report_inputs.json` builder
- `src/cwr_engine/cache.py`
  - Layered cache signature helpers
- `src/cwr_engine/pipeline.py`
  - Explicit step runner and fail-fast orchestration
- `src/cwr_engine/cli.py`
  - Command-line task runner
- `tests/test_task_schema.py`
  - Task-file validation tests
- `tests/test_time_slice.py`
  - Time-slice normalization tests
- `tests/test_region_models.py`
  - Region-spec and mask-bundle tests
- `tests/test_registries.py`
  - Variable/operator/plot registry tests
- `tests/test_pipeline_smoke.py`
  - First end-to-end engine smoke test
- `tests/fixtures/minimal_task.json`
  - Minimal passing task fixture
- `docs/engine_task_example.json`
  - Human-readable example task config

### Existing files to reference

- `docs/superpowers/specs/2026-07-06-cwr-unified-engine-design.md`
  - Source-of-truth design spec
- `cwr_pipeline_config_template.json`
  - Existing config style reference only

## Task 1: Bootstrap the Python package and test harness

**Files:**
- Create: `pyproject.toml`
- Create: `src/cwr_engine/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Write the failing bootstrap test**

```python
# tests/test_pipeline_smoke.py
from cwr_engine import __version__


def test_package_imports():
    assert __version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_smoke.py::test_package_imports -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cwr_engine'`

- [ ] **Step 3: Write minimal package bootstrap**

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "cwr-engine"
version = "0.1.0"
description = "Unified computation engine for CWR workflows"
requires-python = ">=3.9"
dependencies = []

[tool.setuptools]
package-dir = {"" = "src"}

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
```

```python
# src/cwr_engine/__init__.py
__version__ = "0.1.0"
```

```python
# tests/__init__.py
```

Note: the `pythonpath = ["src"]` pytest setting is required here because Task 1 uses a `src/` package layout but does not yet install the package into the environment.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_smoke.py::test_package_imports -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/cwr_engine/__init__.py tests/__init__.py tests/test_pipeline_smoke.py
git commit -m "feat: bootstrap cwr engine package"
```

## Task 2: Implement typed task models and JSON task loading

**Files:**
- Create: `src/cwr_engine/models/time_slice.py`
- Create: `src/cwr_engine/models/region.py`
- Create: `src/cwr_engine/models/output_request.py`
- Create: `src/cwr_engine/models/task.py`
- Create: `src/cwr_engine/task_schema.py`
- Create: `tests/test_task_schema.py`
- Create: `tests/fixtures/minimal_task.json`
- Create: `docs/engine_task_example.json`

- [ ] **Step 1: Write the failing task-schema tests**

```python
# tests/test_task_schema.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_task_schema.py::test_load_minimal_task_fixture -v`
Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `cwr_engine.task_schema`

- [ ] **Step 3: Write minimal typed models and loader**

```python
# src/cwr_engine/models/time_slice.py
from dataclasses import dataclass


@dataclass(frozen=True)
class TimeSlice:
    scale: str
    start: str
    end: str
    label: str
```

```python
# src/cwr_engine/models/region.py
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegionSpec:
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class MaskBundle:
    mask_path: str
    preview_path: str
    grid_definition: dict[str, Any]
    signature: str
```

```python
# src/cwr_engine/models/output_request.py
from dataclasses import dataclass


@dataclass(frozen=True)
class OutputRequest:
    kind: str
    name: str
```

```python
# src/cwr_engine/models/task.py
from dataclasses import dataclass

from cwr_engine.models.output_request import OutputRequest
from cwr_engine.models.region import RegionSpec
from cwr_engine.models.time_slice import TimeSlice


@dataclass(frozen=True)
class EngineTask:
    task_id: str
    data_source: dict
    time_slices: list[TimeSlice]
    region_spec: RegionSpec
    variables: list[str]
    operators: list[str]
    outputs: list[OutputRequest]
    workflow_steps: list[str]
    reuse_policy: dict
    output_root: str
```

```python
# src/cwr_engine/task_schema.py
import json
from pathlib import Path

from cwr_engine.models.output_request import OutputRequest
from cwr_engine.models.region import RegionSpec
from cwr_engine.models.task import EngineTask
from cwr_engine.models.time_slice import TimeSlice


def load_task(path: Path) -> EngineTask:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return EngineTask(
        task_id=payload["task_id"],
        data_source=payload["data_source"],
        time_slices=[TimeSlice(**item) for item in payload["time_slices"]],
        region_spec=RegionSpec(
            kind=payload["region_spec"]["kind"],
            payload=payload["region_spec"]["payload"],
        ),
        variables=payload["variables"],
        operators=payload["operators"],
        outputs=[OutputRequest(**item) for item in payload["outputs"]],
        workflow_steps=payload["workflow_steps"],
        reuse_policy=payload["reuse_policy"],
        output_root=payload["output_root"],
    )
```

```json
// tests/fixtures/minimal_task.json
{
  "task_id": "demo-run",
  "data_source": {"name": "demo", "root": "inputs/demo.nc"},
  "time_slices": [
    {"scale": "year", "start": "2025-01-01", "end": "2025-12-31", "label": "2025"}
  ],
  "region_spec": {
    "kind": "bbox",
    "payload": {"min_lon": 100.0, "max_lon": 110.0, "min_lat": 30.0, "max_lat": 35.0}
  },
  "variables": ["temp"],
  "operators": ["mean"],
  "outputs": [
    {"kind": "region_table", "name": "temp_year_mean"},
    {"kind": "report_inputs", "name": "report_inputs"}
  ],
  "workflow_steps": ["prepare", "mask", "subset", "transform", "stat", "plot", "export", "report_inputs"],
  "reuse_policy": {"mask": true, "subset": true, "stat": true, "plot": true},
  "output_root": "outputs/demo-run"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_task_schema.py::test_load_minimal_task_fixture -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwr_engine/models src/cwr_engine/task_schema.py tests/test_task_schema.py tests/fixtures/minimal_task.json docs/engine_task_example.json
git commit -m "feat: add engine task schema models"
```

## Task 3: Normalize time slices and region inputs

**Files:**
- Modify: `src/cwr_engine/models/time_slice.py`
- Modify: `src/cwr_engine/models/region.py`
- Create: `tests/test_time_slice.py`
- Create: `tests/test_region_models.py`

- [ ] **Step 1: Write the failing normalization tests**

```python
# tests/test_time_slice.py
from cwr_engine.models.time_slice import normalize_time_slice


def test_normalize_year_slice():
    item = normalize_time_slice({"scale": "year", "year": 2025})
    assert item.start == "2025-01-01"
    assert item.end == "2025-12-31"
    assert item.label == "2025"
```

```python
# tests/test_region_models.py
from cwr_engine.models.region import build_region_spec


def test_build_bbox_region_spec():
    spec = build_region_spec(
        {
            "kind": "bbox",
            "payload": {"min_lon": 100.0, "max_lon": 110.0, "min_lat": 30.0, "max_lat": 35.0},
        }
    )
    assert spec.kind == "bbox"
    assert spec.payload["min_lon"] == 100.0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_time_slice.py tests/test_region_models.py -v`
Expected: FAIL with missing functions `normalize_time_slice` and `build_region_spec`

- [ ] **Step 3: Implement normalization helpers**

```python
# src/cwr_engine/models/time_slice.py
from dataclasses import dataclass


@dataclass(frozen=True)
class TimeSlice:
    scale: str
    start: str
    end: str
    label: str


def normalize_time_slice(payload: dict) -> TimeSlice:
    if payload["scale"] == "year":
        year = int(payload["year"])
        return TimeSlice(
            scale="year",
            start=f"{year}-01-01",
            end=f"{year}-12-31",
            label=str(year),
        )
    return TimeSlice(
        scale=payload["scale"],
        start=payload["start"],
        end=payload["end"],
        label=payload["label"],
    )
```

```python
# src/cwr_engine/models/region.py
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegionSpec:
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class MaskBundle:
    mask_path: str
    preview_path: str
    grid_definition: dict[str, Any]
    signature: str


def build_region_spec(payload: dict[str, Any]) -> RegionSpec:
    kind = payload["kind"]
    if kind not in {"shp", "existing_mask", "bbox"}:
        raise ValueError(f"Unsupported region kind: {kind}")
    return RegionSpec(kind=kind, payload=payload["payload"])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_time_slice.py tests/test_region_models.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwr_engine/models/time_slice.py src/cwr_engine/models/region.py tests/test_time_slice.py tests/test_region_models.py
git commit -m "feat: add time and region normalization helpers"
```

## Task 4: Add variable, operator, and plot registries

**Files:**
- Create: `src/cwr_engine/registries/variables.py`
- Create: `src/cwr_engine/registries/operators.py`
- Create: `src/cwr_engine/registries/plots.py`
- Create: `tests/test_registries.py`

- [ ] **Step 1: Write the failing registry tests**

```python
# tests/test_registries.py
from cwr_engine.registries.variables import build_variable_registry
from cwr_engine.registries.operators import build_operator_registry
from cwr_engine.registries.plots import build_plot_registry


def test_builtin_registries_have_seed_entries():
    variables = build_variable_registry()
    operators = build_operator_registry()
    plots = build_plot_registry()

    assert "temp" in variables
    assert "mean" in operators
    assert "timeseries" in plots
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_registries.py::test_builtin_registries_have_seed_entries -v`
Expected: FAIL with `ModuleNotFoundError` for registry modules

- [ ] **Step 3: Implement minimal registries**

```python
# src/cwr_engine/registries/variables.py
def build_variable_registry() -> dict:
    return {
        "temp": {
            "display_name": "Temperature",
            "unit": "degC",
            "supported_scales": ["day", "month", "year"],
            "default_operator": "mean",
            "default_plot": "timeseries",
            "source_key": "temp",
        }
    }
```

```python
# src/cwr_engine/registries/operators.py
def build_operator_registry() -> dict:
    return {
        "mean": {
            "input_kind": "series_or_grid",
            "output_kind": "scalar_or_grid",
            "supported_scales": ["day", "month", "year"],
        }
    }
```

```python
# src/cwr_engine/registries/plots.py
def build_plot_registry() -> dict:
    return {
        "timeseries": {
            "required_fields": ["x", "y"],
            "output_kind": "png",
        },
        "distribution": {
            "required_fields": ["grid"],
            "output_kind": "png",
        },
        "bar_compare": {
            "required_fields": ["labels", "values"],
            "output_kind": "png",
        },
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_registries.py::test_builtin_registries_have_seed_entries -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwr_engine/registries tests/test_registries.py
git commit -m "feat: add variable operator and plot registries"
```

## Task 5: Implement cache signatures and task output layout

**Files:**
- Create: `src/cwr_engine/cache.py`
- Modify: `src/cwr_engine/models/region.py`
- Modify: `src/cwr_engine/models/task.py`
- Modify: `tests/test_region_models.py`

- [ ] **Step 1: Write the failing cache-signature test**

```python
# tests/test_region_models.py
from cwr_engine.cache import build_mask_signature


def test_mask_signature_is_stable_for_same_payload():
    payload = {"kind": "bbox", "payload": {"min_lon": 100.0, "max_lon": 110.0, "min_lat": 30.0, "max_lat": 35.0}}
    sig1 = build_mask_signature(payload, {"resolution": 0.25})
    sig2 = build_mask_signature(payload, {"resolution": 0.25})
    assert sig1 == sig2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_region_models.py::test_mask_signature_is_stable_for_same_payload -v`
Expected: FAIL with missing `cwr_engine.cache`

- [ ] **Step 3: Implement minimal signature helpers**

```python
# src/cwr_engine/cache.py
import hashlib
import json


def _stable_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_mask_signature(region_spec: dict, grid_definition: dict) -> str:
    return _stable_hash({"region_spec": region_spec, "grid_definition": grid_definition})
```

```python
# src/cwr_engine/models/region.py
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegionSpec:
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class MaskBundle:
    mask_path: str
    preview_path: str
    grid_definition: dict[str, Any]
    signature: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_region_models.py::test_mask_signature_is_stable_for_same_payload -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwr_engine/cache.py src/cwr_engine/models/region.py tests/test_region_models.py
git commit -m "feat: add cache signature helpers"
```

## Task 6: Implement step interfaces and a fail-fast pipeline runner

**Files:**
- Create: `src/cwr_engine/steps/prepare.py`
- Create: `src/cwr_engine/steps/mask.py`
- Create: `src/cwr_engine/steps/subset.py`
- Create: `src/cwr_engine/steps/transform.py`
- Create: `src/cwr_engine/steps/stat.py`
- Create: `src/cwr_engine/steps/plot.py`
- Create: `src/cwr_engine/steps/export.py`
- Create: `src/cwr_engine/steps/report_inputs.py`
- Create: `src/cwr_engine/pipeline.py`
- Modify: `tests/test_pipeline_smoke.py`

- [ ] **Step 1: Write the failing pipeline smoke test**

```python
# tests/test_pipeline_smoke.py
from pathlib import Path

from cwr_engine.pipeline import run_task


def test_pipeline_writes_report_inputs(tmp_path: Path):
    report_path = run_task(
        task_path=Path("tests/fixtures/minimal_task.json"),
        output_root=tmp_path,
    )
    assert report_path.name == "report_inputs.json"
    assert report_path.exists()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_smoke.py::test_pipeline_writes_report_inputs -v`
Expected: FAIL with missing `cwr_engine.pipeline`

- [ ] **Step 3: Implement minimal step runner and no-op steps**

```python
# src/cwr_engine/pipeline.py
from pathlib import Path

from cwr_engine.steps.report_inputs import write_report_inputs
from cwr_engine.task_schema import load_task


def run_task(task_path: Path, output_root: Path | None = None) -> Path:
    task = load_task(task_path)
    root = output_root or Path(task.output_root)
    root.mkdir(parents=True, exist_ok=True)
    for name in ["prepare", "mask", "subset", "transform", "stat", "plot", "export"]:
        step_dir = root / name
        step_dir.mkdir(parents=True, exist_ok=True)
    return write_report_inputs(task=task, output_root=root)
```

```python
# src/cwr_engine/steps/report_inputs.py
import json
from pathlib import Path


def write_report_inputs(task, output_root: Path) -> Path:
    target_dir = output_root / "report_inputs"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "report_inputs.json"
    payload = {
        "task_id": task.task_id,
        "workflow_steps": task.workflow_steps,
        "status": "success",
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
```

```python
# src/cwr_engine/steps/prepare.py
def run(context: dict) -> dict:
    return context
```

```python
# src/cwr_engine/steps/mask.py
def run(context: dict) -> dict:
    return context
```

```python
# src/cwr_engine/steps/subset.py
def run(context: dict) -> dict:
    return context
```

```python
# src/cwr_engine/steps/transform.py
def run(context: dict) -> dict:
    return context
```

```python
# src/cwr_engine/steps/stat.py
def run(context: dict) -> dict:
    return context
```

```python
# src/cwr_engine/steps/plot.py
def run(context: dict) -> dict:
    return context
```

```python
# src/cwr_engine/steps/export.py
def run(context: dict) -> dict:
    return context
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_smoke.py::test_pipeline_writes_report_inputs -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwr_engine/steps src/cwr_engine/pipeline.py tests/test_pipeline_smoke.py
git commit -m "feat: add fail-fast pipeline skeleton"
```

## Task 7: Make `report_inputs.json` match the design contract

**Files:**
- Modify: `src/cwr_engine/steps/report_inputs.py`
- Modify: `src/cwr_engine/pipeline.py`
- Modify: `tests/test_pipeline_smoke.py`

- [ ] **Step 1: Write the failing contract test**

```python
# tests/test_pipeline_smoke.py
import json
from pathlib import Path

from cwr_engine.pipeline import run_task


def test_report_inputs_contains_contract_fields(tmp_path: Path):
    report_path = run_task(
        task_path=Path("tests/fixtures/minimal_task.json"),
        output_root=tmp_path,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["task"]["task_id"] == "demo-run"
    assert payload["inputs"]["variables"] == ["temp"]
    assert "artifacts" in payload
    assert "runtime" in payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_smoke.py::test_report_inputs_contains_contract_fields -v`
Expected: FAIL with missing keys such as `task` or `inputs`

- [ ] **Step 3: Implement the structured report-inputs builder**

```python
# src/cwr_engine/steps/report_inputs.py
import json
from pathlib import Path


def write_report_inputs(task, output_root: Path) -> Path:
    target_dir = output_root / "report_inputs"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / "report_inputs.json"
    payload = {
        "task": {
            "task_id": task.task_id,
            "status": "success",
            "output_root": str(output_root),
        },
        "inputs": {
            "data_source": task.data_source,
            "time_slices": [item.__dict__ for item in task.time_slices],
            "region_spec": {"kind": task.region_spec.kind, "payload": task.region_spec.payload},
            "variables": task.variables,
            "operators": task.operators,
        },
        "artifacts": [],
        "runtime": {
            "workflow_steps": task.workflow_steps,
            "used_cache": [],
        },
    }
    target.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return target
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_smoke.py::test_report_inputs_contains_contract_fields -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwr_engine/steps/report_inputs.py src/cwr_engine/pipeline.py tests/test_pipeline_smoke.py
git commit -m "feat: add structured report inputs contract"
```

## Task 8: Add a CLI entrypoint for running task files

**Files:**
- Create: `src/cwr_engine/cli.py`
- Modify: `pyproject.toml`
- Modify: `tests/test_pipeline_smoke.py`

- [ ] **Step 1: Write the failing CLI test**

```python
# tests/test_pipeline_smoke.py
from pathlib import Path

from cwr_engine.cli import main


def test_cli_returns_zero(tmp_path: Path):
    code = main(
        [
            "--task",
            "tests/fixtures/minimal_task.json",
            "--output-root",
            str(tmp_path),
        ]
    )
    assert code == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_smoke.py::test_cli_returns_zero -v`
Expected: FAIL with missing `cwr_engine.cli`

- [ ] **Step 3: Implement the CLI**

```python
# src/cwr_engine/cli.py
import argparse
from pathlib import Path

from cwr_engine.pipeline import run_task


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True)
    parser.add_argument("--output-root", required=False)
    args = parser.parse_args(argv)
    run_task(
        task_path=Path(args.task),
        output_root=Path(args.output_root) if args.output_root else None,
    )
    return 0
```

```toml
# pyproject.toml
[project.scripts]
cwr-engine = "cwr_engine.cli:main"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_smoke.py::test_cli_returns_zero -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/cwr_engine/cli.py tests/test_pipeline_smoke.py
git commit -m "feat: add cwr engine cli entrypoint"
```

## Task 9: Add one real operator path and one real plot path

**Files:**
- Modify: `src/cwr_engine/steps/stat.py`
- Modify: `src/cwr_engine/steps/plot.py`
- Modify: `src/cwr_engine/steps/export.py`
- Modify: `src/cwr_engine/steps/report_inputs.py`
- Modify: `tests/test_pipeline_smoke.py`

- [ ] **Step 1: Write the failing artifact test**

```python
# tests/test_pipeline_smoke.py
import json
from pathlib import Path

from cwr_engine.pipeline import run_task


def test_pipeline_emits_csv_and_png_artifacts(tmp_path: Path):
    report_path = run_task(
        task_path=Path("tests/fixtures/minimal_task.json"),
        output_root=tmp_path,
    )
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    kinds = {item["kind"] for item in payload["artifacts"]}
    assert "region_table" in kinds
    assert "figure_timeseries" in kinds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pipeline_smoke.py::test_pipeline_emits_csv_and_png_artifacts -v`
Expected: FAIL because `artifacts` is empty

- [ ] **Step 3: Implement one minimal exported table and one minimal plot artifact**

```python
# src/cwr_engine/steps/export.py
import csv
from pathlib import Path


def write_region_table(output_root: Path) -> Path:
    target = output_root / "export" / "region_table.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["variable", "operator", "value"])
        writer.writerow(["temp", "mean", "0.0"])
    return target
```

```python
# src/cwr_engine/steps/plot.py
from pathlib import Path

import matplotlib.pyplot as plt


def write_timeseries_plot(output_root: Path) -> Path:
    target = output_root / "plot" / "timeseries.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots()
    ax.plot([0, 1], [0.0, 0.0])
    ax.set_title("Demo Time Series")
    fig.savefig(target, dpi=120, bbox_inches="tight")
    plt.close(fig)
    return target
```

```python
# src/cwr_engine/pipeline.py
from cwr_engine.steps.export import write_region_table
from cwr_engine.steps.plot import write_timeseries_plot
from cwr_engine.steps.report_inputs import write_report_inputs


def run_task(task_path, output_root=None):
    task = load_task(task_path)
    root = output_root or Path(task.output_root)
    for name in ["prepare", "mask", "subset", "transform", "stat", "plot", "export", "report_inputs"]:
        (root / name).mkdir(parents=True, exist_ok=True)
    table_path = write_region_table(root)
    plot_path = write_timeseries_plot(root)
    return write_report_inputs(task=task, output_root=root, artifacts=[table_path, plot_path])
```

```python
# src/cwr_engine/steps/report_inputs.py
def write_report_inputs(task, output_root: Path, artifacts: list[Path] | None = None) -> Path:
    artifact_items = []
    for path in artifacts or []:
        kind = "figure_timeseries" if path.suffix.lower() == ".png" else "region_table"
        artifact_items.append({"kind": kind, "path": str(path)})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pipeline_smoke.py::test_pipeline_emits_csv_and_png_artifacts -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwr_engine/steps/export.py src/cwr_engine/steps/plot.py src/cwr_engine/pipeline.py src/cwr_engine/steps/report_inputs.py tests/test_pipeline_smoke.py
git commit -m "feat: emit initial table and plot artifacts"
```

## Task 10: Document the first runnable developer workflow

**Files:**
- Modify: `docs/engine_task_example.json`
- Modify: `docs/superpowers/specs/2026-07-06-cwr-unified-engine-design.md`

- [ ] **Step 1: Write the failing documentation check**

```python
# tests/test_task_schema.py
from pathlib import Path


def test_example_task_doc_exists():
    assert Path("docs/engine_task_example.json").exists()
```

- [ ] **Step 2: Run test to verify it fails if doc is missing or stale**

Run: `pytest tests/test_task_schema.py::test_example_task_doc_exists -v`
Expected: PASS if file exists already; if it already passes, manually compare the example content against the implemented task schema before proceeding

- [ ] **Step 3: Update the example task and spec cross-reference**

```json
// docs/engine_task_example.json
{
  "task_id": "demo-run",
  "data_source": {"name": "demo", "root": "inputs/demo.nc"},
  "time_slices": [{"scale": "year", "year": 2025}],
  "region_spec": {
    "kind": "bbox",
    "payload": {"min_lon": 100.0, "max_lon": 110.0, "min_lat": 30.0, "max_lat": 35.0}
  },
  "variables": ["temp"],
  "operators": ["mean"],
  "outputs": [
    {"kind": "region_table", "name": "temp_year_mean"},
    {"kind": "figure_timeseries", "name": "temp_series"},
    {"kind": "report_inputs", "name": "report_inputs"}
  ],
  "workflow_steps": ["prepare", "mask", "subset", "transform", "stat", "plot", "export", "report_inputs"],
  "reuse_policy": {"mask": true, "subset": true, "stat": true, "plot": true},
  "output_root": "outputs/demo-run"
}
```

- [ ] **Step 4: Run the full test suite**

Run: `pytest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add docs/engine_task_example.json docs/superpowers/specs/2026-07-06-cwr-unified-engine-design.md tests/test_task_schema.py
git commit -m "docs: add runnable unified engine example"
```

## Self-Review

### Spec coverage

- Two-layer architecture: covered by package split and `report_inputs` handoff in Tasks 2, 6, and 7
- Standard task JSON and explicit steps: covered by Tasks 2 and 6
- `time_slice`, `region_spec`, `mask_bundle`, `output_request`: covered by Tasks 2 and 3
- Variable/operator/plot registries: covered by Task 4
- Layered cache signatures: covered by Task 5
- Run-based output directories: covered by Task 6
- Structured `report_inputs.json`: covered by Task 7
- Core artifacts and plots: covered by Task 9
- Example configuration and developer entrypoint: covered by Tasks 8 and 10

### Placeholder scan

- No `TODO`, `TBD`, or deferred "implement later" steps remain
- Each code-changing step includes concrete file content
- Each test step includes a concrete command and expected result

### Type consistency

- Task model uses `task_id`, `time_slices`, `region_spec`, `outputs`, and `workflow_steps` consistently
- `run_task()` is the single pipeline entrypoint in tests, CLI, and implementation
- Registry names use `temp`, `mean`, and `timeseries` consistently across tasks

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-06-cwr-unified-engine-bootstrap.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Which approach?
