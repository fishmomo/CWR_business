# Multi-Variable Result Design

## Goal

Allow one engine task to compute and export every requested variable rather
than silently using only the first item in `task.variables`.

## Scope

This delivery supports multiple variables and the registered `mean`, `max`,
`min`, and `sum` operators. Every requested operator is applied to every
requested variable.

## Result Model

`transform` stores a `variable_results` mapping keyed by variable name. Each
value contains:

- `transformed_slices`: masked source data and one regional time series per
  `time_slice`;
- `timeseries_data`: all slice series concatenated and sorted by time;
- `source_key`: the source NetCDF field selected through the variable registry.

`stat` reduces all masked values in a time slice and produces one row per
`(time_slice, variable, operator)` tuple.

## Output Behavior

- `region_table`: one requested CSV contains all statistics rows.
- `grid_nc`: operators reduce only the time dimension and preserve the masked
  spatial grid. A single operator retains the variable name; multiple operators
  use `<variable>_<operator>`.
- `figure_timeseries`: each requested figure template produces one PNG per
  task variable, named `<request.name>_<variable>.png`.
- `report_inputs`: indexes every artifact actually created; the artifact kind
  remains `figure_timeseries` for each variable-specific PNG.

## Validation

Tests use a two-variable NetCDF fixture and prove that a single task produces:

- CSV statistics for every variable/operator combination;
- a NetCDF artifact containing every requested variable/operator grid;
- two named figures from one figure request;
- a clear `ValueError` for unregistered requested operators.
