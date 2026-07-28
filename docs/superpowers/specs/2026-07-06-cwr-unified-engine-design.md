# CWR Unified Engine Design

Date: 2026-07-06

## 1. Goal

Build a two-layer architecture for CWR business workflows:

- A bottom-layer unified computation engine
- Top-layer report products, thematic products, and future simplified entrypoints

The bottom layer should not be report-centric. It should standardize data preparation, space-time slicing, transformation, statistics, plotting, and export so that many business workflows can reuse the same engine.

## 2. Architecture

The overall flow is:

`business request -> upper-layer task translation -> bottom-layer standard task -> standard outputs + report_inputs`

Responsibilities are split as follows:

- Upper layer:
  - Accept business-facing requests
  - Translate business actions into standard engine task requests
  - Consume bottom-layer outputs and `report_inputs.json`
- Bottom layer:
  - Execute standard computation tasks
  - Produce standard files such as `csv`, `nc`, and `png`
  - Produce a structured `report_inputs.json` for upper-layer consumption

## 3. Bottom-Layer Responsibility Boundary

The first version of the bottom layer is responsible up to the step before final report assembly.

It must cover:

- Data source discovery and standardized reading
- Region mask preparation
- Space-time slicing
- Source-scale validation and variable transformations
- Statistical computation
- Plot generation
- Export of standard artifacts
- Generation of structured `report_inputs`

It does not include:

- Final DOCX report assembly
- Report template filling
- Full upper-layer product presentation logic

## 4. Standard Task Model

Each engine run is represented by:

- One standard JSON task file
- One explicit workflow step chain

The task file should contain at least:

- `data_source`: source location, product type, readable format
- `time_slices`: explicit time-slice collection
- `region_spec`: user-provided region definition
- `variables`: requested physical variables
- `operators`: requested statistical operators
- `outputs`: requested output artifact types
- `workflow_steps`: explicit steps to execute
- `reuse_policy`: caching and reuse policy
- `output_root`: task output location

## 5. Workflow Steps

The first-version workflow is:

`prepare -> mask -> subset -> transform -> stat -> plot -> export -> report_inputs`

Step boundaries:

- `prepare`
  - Raw data discovery
  - Data reading
  - Field normalization
  - Coordinate normalization
  - Time-dimension normalization
- `mask`
  - Compile `region_spec` into `mask_bundle`
- `subset`
  - Pure space-time clipping only
  - No statistics
  - No aggregation
- `transform`
  - Unit conversion
  - Derived-variable generation
  - Necessary variable re-expression
- `stat`
  - Execute registered operators
  - Produce statistical outputs
- `plot`
  - Produce graphics from registered plot types
- `export`
  - Export formal task artifacts
- `report_inputs`
  - Build the structured summary JSON for upper-layer consumption

## 6. Time Model

The bottom layer accepts explicit time-slice collections only.

Use a standard object named `time_slice`.

Each `time_slice` should include:

- `scale`: such as `day`, `month`, `year`, or `range`
- Standard start and end bounds
- A stable label for output naming and plot titles

Examples of business requests that all normalize into `time_slice` objects:

- One year
- Multiple years
- Specific months within one or more years
- A date interval

The upper layer may keep friendly business forms, but once a request enters the engine it must be normalized into a standard `time_slice` list.

The source product must declare its own `time_scale`. Day, month, and year
requests use the corresponding day, month, and year source products. The
engine does not resample a finer-scale source into another official product
scale.

## 7. Space Model

### 7.1 User-Facing Region Input

Use `region_spec` as the user-input layer object.

The first version supports:

- `shp`
- `existing_mask`
- `bbox`

### 7.2 Engine Execution Object

All region inputs must be compiled into a standard execution object named `mask_bundle`.

`mask_bundle` is mandatory because downstream computation depends on it.

It should contain at least:

- Standard mask data
- Spatial extent
- Grid resolution or grid definition
- CRS or coordinate metadata
- Mask source metadata
- Preview image path
- Reuse signature metadata

Rule:

- External input may have multiple forms
- Internal computation only accepts `mask_bundle`

## 8. Output Model

The bottom layer does not accept business phrases such as "generate report chart" or "generate thematic product".

It accepts only standard output requests, represented as `output_request`.

The first version should standardize at least:

- `region_table`
- `grid_nc`
- `figure_timeseries`
- `figure_distribution`
- `report_inputs`

Upper-layer business actions must be translated into these standard output requests.

## 9. Registry-Based Extensibility

The engine should expand through registries rather than scattered product-specific logic.

### 9.1 Variable Registry

Use `variable_registry` to define each physical variable.

Each variable entry should include at least:

- Unified variable name
- Chinese name or display name
- Unit
- Supported time scales
- Default statistical behavior
- Default plotting guidance
- Raw field name or read key
- Missing-value rule
- Valid-range rule

### 9.2 Operator Registry

Use `operator_registry` to define statistical operators.

Examples:

- Mean
- Maximum
- Minimum
- Accumulation
- Anomaly
- Trend
- Area proportion
- Quantile

Each operator should define:

- Required input data shape
- Output structure
- Supported time scales
- Whether it supports regional outputs, gridded outputs, or both

### 9.3 Plot Registry

Use `plot_registry` for core plot types.

The first version should only cover a small number of high-frequency plot types:

- Time-series plot
- Spatial distribution plot
- Bar comparison plot

Each plot type should define:

- Accepted input data structure
- Required fields
- Adjustable parameters
- Default title, color, legend, and output-size rules

## 10. Plot Strategy

The first version uses a plot-type registry, but only for a small number of core plot types.

It does not yet require a fully unified `plot_data` protocol across all future graphics.

This keeps the first version controlled while still avoiding product-by-product plotting scripts for the most common cases.

## 11. Intermediate Result Strategy

Artifacts should still be written as separate files, but the engine must also generate one unified summary file:

- `report_inputs.json`

This means:

- Actual data files and image files remain on disk in their normal formats
- Upper-layer products read a single structured index file instead of discovering files ad hoc

## 12. Execution Mode

The first version uses explicit step orchestration.

That means the task file clearly states which workflow steps run and in what order.

Reason:

- Easier to control
- Easier to debug
- Better aligned with current workflow reality

Future upper-layer declaration-based entrypoints may be added later, but the first version should remain explicit.

## 13. Reuse and Cache Strategy

The first version uses layered reuse rather than simple "file exists, then reuse".

At minimum, define four cache layers:

- `mask_cache`
  - Determined by `region_spec + grid_definition + mask_rules`
- `subset_cache`
  - Determined by `data_source + time_slices + mask_bundle + variables`
- `stat_cache`
  - Determined by `subset_result + transform_config + operators`
- `plot_cache`
  - Determined by `stat_or_grid_result + plot_type + plot_params`

This allows:

- Reusing masks independently
- Reusing subset results independently
- Reusing statistical results independently
- Replotting without recomputing earlier stages

## 14. Output Directory Organization

The first version uses one independent output directory per task run, keyed by `run_id`.

Recommended structure:

- `prepare/`
- `mask/`
- `subset/`
- `transform/`
- `stat/`
- `plot/`
- `export/`
- `report_inputs/`

This supports:

- Traceability
- Easier debugging
- Run-by-run comparison
- Cleaner cache and artifact management

## 15. Failure Policy

The first version uses:

- Fail fast

If any step fails, the task stops immediately.

Reason:

- Simplest for first-version stability
- Clearer failure localization
- Avoids partial-success state complexity too early

## 16. Configuration Format

The first version uses:

- JSON task files

Reason:

- Consistent with current usage habits
- Easy to audit
- Easy to rerun
- Easy for later upper-layer tools to generate

## 17. Meaning of Prepare, Transform, and Subset

To prevent step-boundary drift:

- `prepare`
  - Only raw data discovery, reading, and normalization
- `transform`
  - Only unit conversion, derived variables, and required re-expression
- `subset`
  - Only pure space-time clipping

`subset` does not absorb:

- Statistics
- Aggregation
- General filtering logic beyond its clipping role

## 18. First-Version Scope

### 18.1 Must Have

- Standard JSON task file
- Explicit workflow chain
- `region_spec` with `shp / existing_mask / bbox`
- Internal `mask_bundle`
- Explicit `time_slice` model
- Variable registry
- Operator registry
- Small plot registry with core plot types
- Layered cache
- `run_id`-based output directory
- Standard `report_inputs.json`
- Fail-fast execution

### 18.2 Not in First Version

- Final DOCX report assembly inside the bottom layer
- Over-abstracting many plot types at once
- Complex declarative task DSL
- Heavy multi-data-source adaptation framework
- Automatic fault-tolerant continuation
- GUI or Web UI
- One-shot support for every business variation

## 19. First-Version Success Criteria

The first version is successful if it can:

- Support the current main business workflow without being report-centric
- Separate time, space, variable, operator, plot type, and output as independent dimensions
- Add new demands mostly by extending one dimension instead of rewriting the full chain
- Produce stable standard outputs and one structured `report_inputs.json`

## 20. Summary

This design turns the current workflow from a report-led pipeline into a standard computation engine with upper-layer consumers.

Its key principles are:

- Two-layer architecture
- Explicit task execution
- Mandatory internal `mask_bundle`
- Standardized `time_slice`
- Registry-based extension for variables, operators, and plots
- Layered caching
- Independent run directories
- Structured `report_inputs.json` as the upper-layer contract

This gives the first version enough structure to support most current workflows while leaving room for future expansion without re-coupling everything back into report-specific code.
