# Standard Output Contract Design

## Goal

Make an engine task's `outputs` collection the authoritative request for
standard artifacts. A task may request CSV data, a time-series figure, a
processed NetCDF grid, structured report inputs, or any supported combination.

## Boundary

The computation engine creates reusable standard artifacts only. It does not
fill a DOCX template or invoke report-generation code. When requested,
`report_inputs.json` indexes the standard artifacts for an independent,
optional report consumer.

## Output Requests

The first delivery recognizes these request kinds:

| Kind | Produced file | Source data |
| --- | --- | --- |
| `region_table` | `export/<name>.csv` | `stat_results` |
| `figure_timeseries` | `plot/<name>.png` | concatenated regional time series |
| `grid_nc` | `export/<name>.nc` | time-mean, region-masked grid data |
| `report_inputs` | `report_inputs/<name>.json` | task metadata, artifacts, runtime, statistics |

`OutputRequest.name` supplies the output filename stem. The engine rejects an
unknown output kind before writing artifacts.

## Execution Rules

1. Workflow steps still control computation dependencies. `prepare`, `mask`,
   `subset`, `transform`, and `stat` run when present in `workflow_steps`.
2. `export` writes only requested `region_table` and `grid_nc` artifacts.
3. `plot` writes only requested `figure_timeseries` artifacts.
4. `report_inputs` is written only when it is explicitly requested and the
   `report_inputs` workflow step is present.
5. A task that requests only CSV or only a figure therefore produces no report
   input file. A task that requests report inputs receives an artifact index
   containing only files actually created during that run.

## Python API Result

`run_task()` returns the path to the requested report-input JSON when the task
requests `report_inputs`; otherwise it returns the task output root. This
preserves the existing report-consuming call pattern while giving artifact-only
tasks a stable, existing return path.

## Compatibility

Existing task examples already request `region_table`, `figure_timeseries`,
and `report_inputs`; their output types remain available. Their names change
the file stems from fixed names to the task-provided names. New example tasks
will use `artifacts/runs/` for generated results rather than the retired
`outputs/` directory.

## Validation

Automated tests will prove that:

- CSV-only tasks create only their requested CSV.
- Figure-only tasks create only their requested PNG.
- A `grid_nc` request creates an openable NetCDF file with the requested
  variable and regional grid dimensions.
- A report-input request indexes exactly the artifacts created for its task.
- An unknown output kind fails fast with a clear error.
