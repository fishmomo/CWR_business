# CWR Engine Stage Gates

## Working rule

Every implementation stage must define five items before work starts:

1. A single outcome.
2. Features included in the stage.
3. Features explicitly excluded from the stage.
4. Executable acceptance checks.
5. A stop condition.

Once the acceptance checks pass, the stage stops and is committed as a
reproducible milestone. Additional ideas are recorded for a later stage instead
of being added to the active scope.

## Current baseline

The runnable baseline includes:

- Standard JSON tasks and an explicit step pipeline.
- Demo plus single-file and `D/M/Y` multi-file NetCDF product catalogs.
- `bbox`, existing-mask, and SHP region inputs compiled to an internal mask.
- Day, month, year, and multiple time-slice selection.
- Multiple requested variables.
- Requested regional CSV, gridded NetCDF, time-series PNG, and report-input
  artifacts.

## Completed stage: generalized computation core

Status: completed on 2026-07-28.

### Outcome

Make computation behavior registry-driven so common calculations can be added
without changing the pipeline orchestration.

### Included

- Execute every requested operator for every requested variable.
- Implement and register the initial common operators.
- Select day, month, or year source products explicitly and validate that the
  source scale matches the requested time-slice scale.
- Never derive a monthly or yearly product by resampling a finer-scale source.
- Dispatch variables and operators through their registries.
- Preserve the existing multi-variable regional CSV and gridded NetCDF output
  contracts.

### Excluded

- Spatial-distribution and bar-comparison plot implementation.
- A general plot-data protocol or product-specific plot styling.
- DOCX/PDF report assembly and automatic narrative generation.
- GUI, Web UI, and business-language task translation.
- Cache execution and fault-tolerant continuation.

### Acceptance

- One task can request at least two variables and at least two operators.
- Day, month, and year tasks use their corresponding source products.
- A source/time-slice scale mismatch fails before artifacts are created.
- Regional CSV contains one unambiguous row per time slice, variable, and
  operator.
- Gridded NetCDF retains requested variables, coordinates, masks, and units.
- Unsupported variable/operator/scale combinations fail before artifacts are
  created.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends immediately after all acceptance checks pass and the result is
committed. Plot-system expansion and upper-layer report integration begin only
after a separate scope decision.

The acceptance checks pass.

## Completed stage: real product data sources

Status: completed on 2026-07-28.

### Outcome

Read requested periods directly from the existing day, month, and year product
directories and normalize them into the engine's `time/lat/lon` data model.

### Included

- Discover `ResultGrid_D`, `ResultGrid_M`, and `ResultGrid_Y` NetCDF files.
- Filter files from requested time slices before loading their data.
- Combine multiple product files in chronological order.
- Normalize scalar time coordinates and spatial coordinate names/dimensions.
- Support explicit coordinate and variable mappings.
- Detect missing periods, duplicate times, missing variables, and incompatible
  grids.
- Record source-file trace information in runtime metadata.

### Excluded

- Cross-scale resampling or aggregation.
- GRIB and non-NetCDF source formats.
- Remote object storage and databases.
- Plot expansion, cache execution, and report assembly.

### Acceptance

- Representative day, month, and year product files can be read.
- A multi-file task selects only files required by its time slices.
- Coordinates are normalized to ascending `time/lat/lon`.
- Missing periods and duplicate internal times fail without formal artifacts.
- Requested registered variables resolve from every selected file.
- A real one-period task from an accessible product directory succeeds.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends after all acceptance checks pass and the result is committed.
No plotting or caching work starts within this stage.

The acceptance checks pass. No subsequent stage is active.
