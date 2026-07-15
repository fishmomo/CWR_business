# CWR Python 3.12 Project Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Declare `cwr_py312` as the reproducible CWR runtime, organize versioned samples under stable paths, remove disposable repository residue, and fix verified execution defects.

**Architecture:** Conda environment metadata and PEP 621 metadata define the same Python 3.12 dependency contract. Runnable CWR tasks live under `examples/tasks/`, source data under `data/inputs/`, and curated reference results under `artifacts/examples/`; task data paths resolve relative to each task. Generated run output remains untracked.

**Tech Stack:** Python 3.12, Conda, setuptools/PEP 621, pytest, NumPy, xarray, SciPy, PyShp, Shapely, PyProj, Matplotlib.

## Global Constraints

- Use `conda run -n cwr_py312` for every Python command, test, and utility execution.
- Support Python `>=3.12` only; never reintroduce Python 3.9 compatibility changes.
- Preserve all user business samples; only relocate them to the paths named below.
- Do not track Python bytecode, pytest cache, or newly generated runtime output outside `artifacts/examples/`.
- Before changing production behavior for a bug, add a failing regression test and observe the expected failure.

---

### Task 1: Declare the Python 3.12 environment and package dependencies

**Files:**
- Create: `environment.yml`
- Create: `README.md`
- Modify: `pyproject.toml:5-19`

**Interfaces:**
- Consumes: Conda environment name `cwr_py312`.
- Produces: `conda env create -f environment.yml` and `pip install -e .[test]` setup paths.

- [ ] **Step 1: Add environment metadata regression checks**

Create `tests/test_project_metadata.py` with assertions that the project requires Python 3.12 and that the Conda environment file names `cwr_py312`:

```python
from pathlib import Path
import tomllib

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_project_requires_python_312_or_newer():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["requires-python"] == ">=3.12"


def test_conda_environment_is_named_cwr_py312():
    environment = yaml.safe_load((ROOT / "environment.yml").read_text(encoding="utf-8"))
    assert environment["name"] == "cwr_py312"
    assert "python=3.12" in environment["dependencies"]
```

- [ ] **Step 2: Run the metadata test to verify it fails**

Run: `conda run -n cwr_py312 python -m pytest tests/test_project_metadata.py -q`

Expected: FAIL because `environment.yml` and the Python 3.12 requirement are absent.

- [ ] **Step 3: Add the environment contract**

Replace `pyproject.toml` project metadata with:

```toml
[project]
name = "cwr-engine"
version = "0.1.0"
description = "Unified computation engine for CWR workflows"
requires-python = ">=3.12"
dependencies = [
  "matplotlib>=3.8",
  "numpy>=1.26",
  "pyproj>=3.6",
  "pyshp>=2.3",
  "scipy>=1.11",
  "shapely>=2.0",
  "xarray>=2024.1",
]

[project.optional-dependencies]
test = ["pytest>=8.0", "pyyaml>=6.0"]
```

Create `environment.yml`:

```yaml
name: cwr_py312
channels:
  - conda-forge
dependencies:
  - python=3.12
  - matplotlib>=3.8
  - numpy>=1.26
  - pyproj>=3.6
  - pyshp>=2.3
  - pytest>=8.0
  - pyyaml>=6.0
  - scipy>=1.11
  - shapely>=2.0
  - xarray>=2024.1
```

Create `README.md` with the exact setup and test commands:

```markdown
# CWR Engine

## Runtime

All development, tests, and agent work use the Conda environment `cwr_py312` (Python 3.12).

```powershell
conda env update -n cwr_py312 -f environment.yml --prune
conda run -n cwr_py312 python -m pytest -q
```
```

- [ ] **Step 4: Run the metadata test to verify it passes**

Run: `conda run -n cwr_py312 python -m pytest tests/test_project_metadata.py -q`

Expected: PASS.

- [ ] **Step 5: Commit the environment contract**

```powershell
git add pyproject.toml environment.yml README.md tests/test_project_metadata.py
git commit -m "build: declare cwr_py312 environment"
```

### Task 2: Move business samples to stable repository locations

**Files:**
- Move: `inputs/` → `data/inputs/`
- Move: `outputs/` → `artifacts/examples/`
- Move: `cwr_pipeline_config_template.json`, `hlj_dxal_lq_test_pipeline_config.json`, `qh_xz_pipeline_config.json`, `xizang_2021_2025_pipeline_config.json` → `examples/legacy-configs/`
- Modify: `.gitignore`
- Modify: `README.md`

**Interfaces:**
- Consumes: preserved user samples and legacy configurations.
- Produces: stable versioned paths for business assets and a documented distinction between reference artifacts and generated output.

- [ ] **Step 1: Add a failing repository-layout test**

Extend `tests/test_project_metadata.py`:

```python
def test_versioned_samples_use_standard_locations():
    assert (ROOT / "data" / "inputs").is_dir()
    assert (ROOT / "artifacts" / "examples").is_dir()
    assert (ROOT / "examples" / "legacy-configs").is_dir()
    assert not (ROOT / "inputs").exists()
    assert not (ROOT / "outputs").exists()
```

- [ ] **Step 2: Run the layout test to verify it fails**

Run: `conda run -n cwr_py312 python -m pytest tests/test_project_metadata.py::test_versioned_samples_use_standard_locations -q`

Expected: FAIL because the new directories do not yet exist.

- [ ] **Step 3: Move retained samples and set generated-output policy**

Run these exact repository moves, preserving Git history where applicable:

```powershell
New-Item -ItemType Directory -Force data, artifacts, examples, examples/legacy-configs
git mv inputs data/inputs
git mv outputs artifacts/examples
Move-Item -LiteralPath cwr_pipeline_config_template.json, hlj_dxal_lq_test_pipeline_config.json, qh_xz_pipeline_config.json, xizang_2021_2025_pipeline_config.json -Destination examples/legacy-configs
```

Append the following rules to `.gitignore`:

```gitignore
# Regenerated pipeline runs; curated examples live in artifacts/examples/.
artifacts/runs/
```

Append this section to `README.md`:

```markdown
## Repository data

- `data/inputs/` contains versioned representative source data.
- `examples/legacy-configs/` preserves pre-engine business configuration records; these are not CWR engine task-schema files.
- `artifacts/examples/` contains curated reference outputs.
- Write new pipeline results under `artifacts/runs/`; that directory is ignored.
```

- [ ] **Step 4: Run the layout test to verify it passes**

Run: `conda run -n cwr_py312 python -m pytest tests/test_project_metadata.py::test_versioned_samples_use_standard_locations -q`

Expected: PASS.

- [ ] **Step 5: Commit the sample organization**

```powershell
git add .gitignore README.md data artifacts examples
git commit -m "chore: organize versioned CWR samples"
```

### Task 3: Validate checked-in task artifacts and report residual defects

**Files:**
- Modify: `README.md`
- Modify: `examples/tasks/` if runnable CWR-engine task copies are added.

**Interfaces:**
- Consumes: `cwr-engine` task schema (`task_id`, `data_source`, `time_slices`, `region_spec`, `variables`, `operators`, `outputs`, `workflow_steps`, `reuse_policy`, `output_root`).
- Produces: a verified command sequence and a documented distinction between runnable engine tasks and preserved legacy configurations.

- [ ] **Step 1: Run representative checks in the declared environment**

Run:

```powershell
conda run -n cwr_py312 python --version
conda run -n cwr_py312 python -m pytest -q
conda run -n cwr_py312 cwr-engine --task tests/fixtures/minimal_task.json --output-root artifacts/runs/smoke
```

Expected: Python `3.12.*`, all tests pass, and the CLI returns exit code 0.

- [ ] **Step 2: Classify each root JSON before moving/rewriting it**

Record in `README.md` that the four retained JSON files are legacy business configuration records, not runnable CWR engine tasks, because they lack the required engine-task fields. Do not rewrite their external `H:\` source references.

- [ ] **Step 3: Inspect output quality and residual errors**

Check `artifacts/runs/smoke/report_inputs/report_inputs.json` and verify it contains `status: "success"`, an exported CSV artifact, and a figure artifact. Then run `git status --short` and record remaining non-cache changes in the final handoff rather than deleting them.

- [ ] **Step 4: Commit documentation changes**

```powershell
git add README.md examples artifacts data .gitignore
git commit -m "docs: document CWR samples and validation"
```
