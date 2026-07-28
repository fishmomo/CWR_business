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
- Demo and single-file NetCDF data sources.
- `bbox`, existing-mask, and SHP region inputs compiled to an internal mask.
- Day, month, year, and multiple time-slice selection.
- Multiple requested variables.
- Requested regional CSV, gridded NetCDF, time-series PNG, and report-input
  artifacts.

## Active stage: generalized computation core

### Outcome

Make computation behavior registry-driven so common calculations can be added
without changing the pipeline orchestration.

### Included

- Execute every requested operator for every requested variable.
- Implement and register the initial common operators.
- Convert source time scales to requested day, month, and year result scales
  with explicit aggregation rules.
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
- Daily source data can produce verified monthly and yearly results.
- Monthly source data can produce verified yearly results.
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
