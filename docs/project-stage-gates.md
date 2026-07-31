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

Every stage-completion report must also state the next planned stage, summarize
its intended outcome, and say explicitly whether that stage is active.

## Current baseline

The runnable baseline includes:

- Standard JSON tasks and an explicit step pipeline.
- Demo plus single-file and `D/M/Y` multi-file NetCDF product catalogs.
- `bbox`, existing-mask, and SHP region inputs compiled to an internal mask.
- Day, month, year, and multiple time-slice selection.
- Multiple requested variables.
- Requested regional CSV, gridded NetCDF, time-series PNG, and report-input
  artifacts.
- An independent single-template DOCX report consumer.

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

The acceptance checks pass.

## Completed stage: standard plotting system

Status: completed on 2026-07-28.

### Outcome

Generate the three common figure types through the plot registry using standard
engine results and validated output parameters.

### Included

- Registry dispatch for time-series, spatial-distribution, and bar-comparison
  figures.
- Plot parameters for title templates, figure size, DPI, labels, colors, and
  distribution color limits.
- One time-series figure per requested variable.
- One distribution figure per time slice, variable, and operator.
- One comparison bar figure per variable and operator.
- Structured figure metadata in `report_inputs.json`.
- Validation before output creation for unsupported parameters and malformed
  title templates.

### Excluded

- Administrative boundaries, projection selection, and cartographic layouts.
- Product-specific multi-panel figures and report-specific styling.
- Interactive figures, animation, GUI, and Web presentation.
- Cache execution and report assembly.

### Acceptance

- One task can request all three standard figure types.
- Multiple time slices and operators produce unambiguous filenames.
- Masked values remain invisible in distribution figures.
- Valid size, DPI, title, color, and color-limit parameters are honored.
- Invalid plot parameters fail before output directories are created.
- Existing time-series requests remain compatible.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends after all acceptance checks pass and the result is committed.
No report-specific plotting is added within this stage.

The acceptance checks pass. No subsequent stage is active.

## Completed stage: upper-layer report product integration

Status: completed on 2026-07-28.

### Outcome

Consume standardized statistics, figures, and `report_inputs` to populate report
templates with data, images, and generated analysis text, then assemble a
complete report.

### Included

- An independent report consumer that does not invoke computation steps.
- One DOCX template per report specification.
- `<<...>>` slots for text, deterministic narrative, statistics tables, and
  standard figure artifacts.
- Configuration-driven source paths, artifact selectors, labels, and image
  widths.
- Strict validation that prevents unresolved or partial reports.
- One representative single-period report acceptance run.

### Excluded

- Multi-year-specific business analysis.
- PDF output and office-format conversion.
- Large-language-model narrative generation.
- Multiple templates in one report task.
- Product-specific formulas not present in `report_inputs`.

### Acceptance

- A report specification can populate all four supported slot types.
- Placeholders split across Word runs are replaced correctly.
- Statistics and standard figure artifacts are selected from
  `report_inputs.json`.
- A deterministic Chinese analysis paragraph is generated from statistics.
- Missing inputs, ambiguous figures, and unresolved slots fail without a DOCX.
- The generated DOCX opens successfully and passes structural checks.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends after one representative single-period DOCX is generated,
verified, and committed. PDF, multi-year reports, and additional business
templates remain outside this stage.

The acceptance checks pass. No subsequent stage is active.

## Completed stage: single-year cloud-water report profile

Status: completed on 2026-07-28.

### Outcome

Adapt the existing `Simple-Year_Evaluation_Report-xizang-cm.docx` through a
configuration-driven business profile. Derive its cloud-water-specific text
values and tables from standardized engine results, map the required figures,
and generate one complete single-year business report in the retained
historical layout. Multi-year templates, PDF conversion, and
large-language-model narratives remain outside that stage.

### Included

- Require a successful standard `report_inputs.json` for task identity and
  report-year consistency.
- Declare annual CSV, monthly CSV, mask NetCDF, spatial-analysis NetCDF, and
  five figure files as explicit profile inputs.
- Derive all single-year text placeholders and both boundary-flow tables.
- Generate deterministic spatial and seasonal distribution descriptions.
- Populate the retained historical DOCX without unresolved placeholders.
- Preserve the historical three-line table treatment and five-image layout.

### Excluded

- Recomputing the supplemental CSV, spatial NetCDF, or five legacy figures.
- Moving boundary-flow calculations into the generalized computation core.
- Multi-year template adaptation.
- PDF conversion and large-language-model narratives.

### Acceptance

- Exactly one annual row and all twelve monthly rows are required for the
  report year.
- All text, table, and image slots in the retained template are populated.
- Missing columns, periods, spatial variables, masks, or figures fail without
  a DOCX.
- The generated report contains two fixed-geometry three-line tables and five
  images.
- A real Inner Mongolia 2025 report is generated and structurally audited.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends after the real 2025 single-year report passes acceptance and is
committed. Multi-year work and generalized supplemental-metric computation do
not begin within this stage.

The acceptance checks pass. No subsequent stage is active.

## Completed stage: standardized supplemental business metrics

Status: completed on 2026-07-30.

### Outcome

Move boundary-flow metrics, monthly seasonal summaries, and report-specific
spatial composites into versioned engine artifacts. The single-year profile can
then consume standardized artifacts instead of transitional annual/monthly CSV
and spatial NetCDF inputs.

### Included

- Add a versioned `business_metrics` JSON artifact indexed by
  `report_inputs.json`.
- Standardize annual regional totals, twelve monthly values, four seasonal
  summaries, and boundary input/output/net-input metrics.
- Keep gridded spatial composites in a separate NetCDF artifact referenced by
  the metrics JSON.
- Validate metric-profile parameters and required source variables before
  formal artifacts are written.
- Change the single-year cloud-water profile to resolve the standardized
  artifacts from `report_inputs.json`.
- Retain the transitional supplemental-input profile contract only as an
  explicitly marked compatibility path during this stage.

### Excluded

- New physical formulas unrelated to the existing single-year cloud-water
  report.
- Day-to-month or month-to-year resampling; existing source products remain
  authoritative at each time scale.
- Recreating the five historical report figures.
- Multi-year report templates, PDF conversion, GUI, and Web UI.
- Removing the compatibility path before the standardized real-data
  acceptance run passes.

### Acceptance

- One engine workflow writes a schema-versioned metrics JSON and spatial
  NetCDF, and indexes both in `report_inputs.json`.
- Metrics contain exactly one requested year, all twelve months, four seasons,
  and four boundaries plus totals.
- Boundary inputs, outputs, and net inputs agree with the retained historical
  calculation to the declared numeric precision.
- Missing periods, variables, incompatible grids, or unsupported metric
  profiles fail before formal artifacts are created.
- The real Inner Mongolia 2025 single-year report is reproduced using only
  `report_inputs.json`, the retained template, and the five figure files.
- The transitional and standardized profile paths produce equivalent report
  text and tables for the real acceptance case.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends immediately after the standardized real-data report is
structurally verified and the implementation is committed. Compatibility-path
removal and additional business metric profiles require a separate stage.

The acceptance checks pass. No subsequent stage is active.

## Completed stage: direct product-derived business metrics

Status: completed on 2026-07-30.

### Outcome

Derive annual, monthly, seasonal, boundary-flow, and spatial-composite business
metrics directly from the authoritative day/month/year product catalogs and
the compiled region mask. This removes the metrics builder's remaining
ingestion dependency on retained regional CSV and spatial-analysis NetCDF
files.

### Included

- Discover exactly one requested annual product and all twelve requested
  monthly products from the `Y/M` catalog directories.
- Compile `shp`, existing-mask, or bounding-box region specifications on the
  product grid.
- Compute annual regional metrics and directional boundary transport directly
  from product variables.
- Compute monthly and seasonal metrics from official monthly products without
  cross-scale resampling.
- Derive the single-year spatial composite directly from annual and monthly
  gridded products.
- Preserve the retained CSV/spatial-input builder as an explicitly named
  compatibility path.

### Excluded

- Reading daily products when no accepted single-year metric uses daily data.
- Recreating the five historical figure layouts.
- Correcting or overwriting retained historical artifacts that used a
  different mask.
- Additional business profiles, multi-year reports, PDF, GUI, and Web UI.

### Acceptance

- Synthetic products verify regional aggregation, segmented directional
  boundaries, annual fields, and seasonal spatial composites.
- Missing products, variables, invalid values, empty masks, and incompatible
  grids fail before formal artifacts are written.
- The real 2025 annual spatial fields match the authoritative NCEP product
  exactly.
- One mask compiled from the retained SHP is used consistently for regional,
  boundary, and spatial metrics.
- A real Inner Mongolia 2025 report is generated from direct-product metrics
  with no unresolved slots.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends after direct-product artifacts and the real single-year report
pass structural and formula-based acceptance and are committed. Figure
regeneration and historical-artifact correction require separate stages.

The acceptance checks pass. The real run selected 52 cells from the source
SHP, read one annual and twelve monthly products, and produced all 13 spatial
composite fields without reading daily data. Annual values match the retained
CSV exactly except for a 0.5 kg floating-point summation difference in `GMv`;
the largest boundary difference is 0.125 kg, and the spatial-field maximum
absolute difference is zero. The retained standalone 72-cell mask is preserved
as historical data and is not used by the direct workflow. The generated
report contains 58 paragraphs, two tables, five images, and no unresolved text
slots. The full suite passes with 60 tests in `cwr_py312`.

## Completed stage: standard figure regeneration

Status: completed on 2026-07-31.

### Outcome

Regenerate the five single-year report figures from standardized direct-product
artifacts and the corrected compiled mask. This removes the report's final
runtime dependency on retained historical PNG files while preserving the
accepted business layout and narrative semantics.

### Technology rule

Use the mature existing stack: `xarray` and `NumPy` for data, `Shapely` for
region geometry, and `Matplotlib` for headless PNG rendering. Add only a thin
cloud-water figure adapter. Do not introduce a new plotting framework,
workflow platform, or projection dependency within this stage.

### Included

- Add the missing annual `GMh` grid to the standardized spatial composite.
- Standardize the monthly metrics required by the four-panel sequence figure.
- Generate the region/mask preview, monthly sequence figure, annual six-panel
  distribution figure, seasonal precipitation figure, and seasonal
  cloud-water-resource figure.
- Index all five figures as `profile_image` artifacts in
  `report_inputs.json`.
- Make the standardized single-year report resolve figures from
  `report_inputs.json`; keep explicit historical images only as compatibility
  fallback.

### Excluded

- Pixel-for-pixel reproduction of historical PNG files.
- Cartographic basemaps or projections that require a new dependency.
- Rewriting the retained historical figures or 72-cell mask.
- Multi-year figures and reports, PDF, GUI, Web UI, and task scheduling.

### Acceptance

- Synthetic direct products verify all monthly figure metrics, the fourteenth
  spatial field, five PNG artifacts, and report-input indexing.
- Figure generation fails before formal artifacts are written when required
  data are missing or invalid.
- The real 2025 run uses one corrected 52-cell mask for metrics, spatial
  fields, and figures.
- The real single-year report is generated without an `images` configuration
  and has five visible figures with no unresolved slots.
- Figure PNGs and rendered report pages pass visual inspection.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends after all five figures pass data, layout, and real-report
acceptance and the implementation is committed. Multi-year reports, PDF,
GUI, and Web UI remain outside that stage.

The acceptance checks pass with one documented environment limitation. The
real run uses the corrected 52-cell mask, writes fourteen spatial fields and
five indexed PNG figures, and generates the report without an `images`
configuration. All fourteen spatial fields match the retained authoritative
product-derived fields exactly. The largest monthly mass difference from the
retained CSV is 0.125 kg; efficiency and residence-time fields match exactly.
All five PNGs passed visual inspection, and the DOCX contains 58 paragraphs,
two tables, five images, and no unresolved text slots. DOCX page rasterization
could not run because LibreOffice is absent and the local Microsoft Office type
library is damaged; structural and embedded-image checks were used as the
document-skill fallback. The full suite passes with 60 tests in `cwr_py312`.

A corrective visual pass on 2026-07-31 changed SHP maps from pre-contour
grid-mask `NaN` handling to full-field contouring followed by polygon clipping.
It also added proportional map padding, especially for the region preview.
The synthetic direct-product test now exercises the SHP clipping path.

## Completed stage: single-year end-to-end orchestration

Status: completed on 2026-07-31.

### Outcome

Run product discovery, mask compilation, business metrics, standard figures,
and DOCX assembly from one task specification and one command. Preserve the
current component contracts while removing the manual handoff between the
metrics and report commands.

### Included

- Define one versioned workflow specification for the direct-product
  single-year cloud-water report.
- Reuse the existing metrics, figure, and report-profile builders without
  duplicating their calculation or rendering logic.
- Stage every artifact outside the formal output directory.
- Publish metrics, spatial data, five figures, report inputs, and DOCX together
  only after the complete workflow succeeds.
- Preserve an existing successful output directory when a rerun fails.
- Index the generated DOCX in the published `report_inputs.json`.

### Excluded

- Removing the independent metrics and report commands or compatibility mode.
- Multi-year orchestration, PDF conversion, GUI, Web UI, scheduling, retries,
  or distributed workflow platforms.
- New physical formulas, figure layouts, or report templates.
- Generalizing this first business workflow into a plugin framework.

### Acceptance

- One workflow specification and one `cwr-engine` command build the complete
  accepted single-year product.
- Published `report_inputs.json` contains valid final paths for metrics,
  spatial data, five figures, and the DOCX.
- A failure after metric generation leaves no new formal output and preserves
  any previously published run.
- The real Inner Mongolia 2025 workflow reproduces the accepted report.
- The full test suite passes in `cwr_py312`.

### Stop condition

The stage ends after one transactional command reproduces the accepted real
2025 report, failure leaves no partial formal outputs, the full suite passes,
and the implementation is committed. Compatibility cleanup and multi-year
work remain separate stages.

The acceptance checks pass. One `--workflow-spec` command reads the real 2025
annual and monthly products, compiles the corrected 52-cell SHP mask, writes
the standardized metrics, fourteen spatial fields plus the mask, five figures,
and the final DOCX, then publishes them as one run. The published
`report_inputs.json` indexes all eight artifacts with valid final paths. The
DOCX contains 58 paragraphs, two tables, five images, and no unresolved slots.
Failure-path tests preserve an existing published run after metrics have
already completed. The full suite passes with 62 tests in `cwr_py312`.

## Next planned stage: compatibility-path retirement

Status: planned, not active.

### Outcome

Inventory remaining users of the transitional annual/monthly CSV, spatial
analysis NetCDF, and explicit historical PNG profile inputs. Migrate retained
examples that still require those paths, then remove only compatibility code
that has no verified caller. Multi-year report implementation remains a
separate later decision.

### Stop condition

The stage ends after every compatibility path has an explicit keep-or-remove
decision, supported paths have regression coverage, unused paths are removed,
the full suite passes, and the result is committed.
