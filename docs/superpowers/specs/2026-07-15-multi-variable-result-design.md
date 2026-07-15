# Multi-Variable Result Design

## Goal

Allow one engine task to compute and export every requested variable rather
than silently using only the first item in `task.variables`.

## Scope

This delivery supports multiple variables with the already registered `mean`
operator. The requested operator collection must be exactly `["mean"]`; other
operators fail fast until the following registry-driven operator delivery adds
their implementations.

## Result Model

`transform` stores a `variable_results` mapping keyed by variable name. Each
value contains:

- `transformed_slices`: one masked time-series and time-mean grid per
  `time_slice`;
- `timeseries_data`: all slice series concatenated and sorted by time;
- `grid_mean_data`: the first requested slice's time-mean, region-masked grid.

`stat` produces one row per `(time_slice, variable, operator)` tuple. The
existing CSV artifact therefore includes every requested variable as separate
rows.

## Output Behavior

- `region_table`: one requested CSV contains all statistics rows.
- `grid_nc`: one requested NC file contains a data variable for every requested
  task variable, each using `lat` and `lon` dimensions.
- `figure_timeseries`: each requested figure template produces one PNG per
  task variable, named `<request.name>_<variable>.png`.
- `report_inputs`: indexes every artifact actually created; the artifact kind
  remains `figure_timeseries` for each variable-specific PNG.

## Validation

Tests use a two-variable NetCDF fixture and prove that a single task produces:

- two CSV statistics rows for `temp` and `precip`;
- a NetCDF artifact containing both data variables;
- two named figures from one figure request;
- a clear `ValueError` for unregistered requested operators.
