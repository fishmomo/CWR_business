# CWR Engine

## Runtime

All development, tests, and agent work use the Conda environment `cwr_py312`
(Python 3.12).

```powershell
conda env update -n cwr_py312 -f environment.yml --prune
conda run -n cwr_py312 python -m pip install -e . --no-deps
conda run -n cwr_py312 python -m pytest -p no:cacheprovider -q
```

Run a task through the installed CLI:

```powershell
conda run -n cwr_py312 cwr-engine --task tests/fixtures/minimal_task.json --output-root artifacts/runs/smoke
```

## Repository data

- `data/inputs/` contains versioned representative source data.
- `examples/legacy-configs/` preserves pre-engine business configuration
  records; these are not CWR engine task-schema files.
- `artifacts/examples/` contains curated reference outputs.
- Write new pipeline results under `artifacts/runs/`; that directory is ignored.
