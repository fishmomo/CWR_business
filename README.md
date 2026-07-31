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

Real NetCDF product catalogs and their `D/M/Y` directory contract are
documented in `docs/real-product-data-source-contract.md`.

Standard time-series, distribution, and comparison figure requests are
documented in `docs/standard-plot-contract.md`.

Single-template DOCX assembly from `report_inputs.json` is documented in
`docs/report-product-contract.md`.

```powershell
conda run -n cwr_py312 cwr-report --spec path/to/report_spec.json
```

The retained single-year cloud-water business template is supported through
the explicit profile contract in
`docs/cloud-water-single-year-profile-contract.md`.

Build its standardized direct-product metrics first, as documented in
`docs/cloud-water-business-metrics-contract.md`.

```powershell
conda run -n cwr_py312 cwr-engine --business-metrics-spec path/to/metrics.json
```

```powershell
conda run -n cwr_py312 cwr-report --profile-spec path/to/profile.json
```

The accepted direct-product single-year workflow can run both components from
one transactional specification. Its contract is documented in
`docs/cloud-water-single-year-workflow-contract.md`.

```powershell
conda run -n cwr_py312 cwr-engine --workflow-spec path/to/workflow.json
```

## Repository data

- `data/inputs/` contains versioned representative source data.
- `examples/legacy-configs/` preserves pre-engine business configuration
  records; these are not CWR engine task-schema files.
- `artifacts/examples/` contains curated reference outputs.
- Write new pipeline results under `artifacts/runs/`; that directory is ignored.

## Delivery stages

Development follows explicit stage gates. Each stage declares its scope,
acceptance criteria, and stop condition before implementation begins. See
`docs/project-stage-gates.md` for the current stage boundary.
