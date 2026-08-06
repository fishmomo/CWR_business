# Cloud-Water Multi-Year Report Contract

Status: approved on 2026-08-06.

## Confirmed Decisions

### Year Selection

The report accepts one contiguous inclusive year range through `start_year`
and `end_year`. For example, `2021` through `2025` represents exactly five
years: 2021, 2022, 2023, 2024, and 2025. `start_year` must not be later than
`end_year`. Arbitrary non-contiguous year lists are outside this report
contract.

### Product Completeness

Completeness is strict. Every selected year must have exactly one official
yearly product and twelve official monthly products, one for each calendar
month. Any missing or duplicate period fails the complete task before formal
artifacts are published. The workflow never skips an incomplete year or
computes climatology from partial months.

### Multi-Year Means

Selected years have equal weight. Annual regional metrics and annual spatial
fields use the arithmetic mean across yearly products. Each climatological
calendar month uses the arithmetic mean of that month across selected years.
Each seasonal value is first summed from its official monthly products within
each year and is then averaged across selected years. No day-count weighting
is applied, and period totals are not used as the report's primary values.

### Trend Wording

Interannual trends must include a significance test. The trend direction is
always reported. A result that passes the declared significance threshold is
worded as `显著增加` or `显著下降`; a result that does not pass is worded only
as `增加` or `下降`. Subjective intensity terms such as `缓慢`, `明显`, or
`快速` are not used. The historical defect that calculated `GMh_trend` from
precipitation data is explicitly rejected; each variable uses its own annual
series.

### Trend Method

Trend significance uses a two-sided Mann-Kendall test with `p < 0.05` as the
significance threshold. Trend magnitude uses the Theil-Sen slope. Artifacts
record the slope in the variable's physical unit per year, the slope relative
to the multi-year mean in `%/year`, the test statistic, the p-value, and the
significance boolean. Report prose follows the confirmed trend wording rule.

### Extrema and Ties

Maximum and minimum results retain every tied four-digit year. Second maximum
and second minimum refer to the next distinct numeric value and likewise
retain every tied year. Metrics artifacts store year arrays rather than one
abbreviated year. The implementation must correct the retained template's
hard-coded `20<<...>>` wording so complete year lists render correctly.

Ranking and tie detection use values rounded to the report's declared
one-decimal display precision. Raw values remain in the metrics artifact. This
prevents two values displayed identically in prose from being described as
different ranks.

The same rule applies to climatological months and seasons: all tied periods
are retained, and second-highest or second-lowest refers to the next distinct
numeric value. Month and season labels follow chronological order within a tie.

### Boundary Transport

Boundary transport is an annual mean, not a period accumulation. Input,
output, and net input are calculated independently for every boundary in every
selected year using the shared mask, then averaged with equal year weights.
Tables report `1e11 kg/year` (`亿吨/年`).

### Minimum Period

Contract version 1 requires at least five consecutive complete years. A
one-year request uses the single-year report workflow. The minimum is a
versioned validation rule and may be changed by a future approved contract
revision without changing the meaning of existing version-1 tasks.

### Numeric Precision

Report prose and tables format mass, depth, efficiency, residence time, and
boundary transport with one decimal place. Trend slopes use two decimal
places. P-values use three decimal places, with values below `0.001` displayed
as `<0.001`. Standard JSON artifacts retain computation precision; formatting
is applied only by figure and report consumers.

### Figure Set

The retained six-figure structure is mandatory:

1. Region geometry and compiled mask preview.
2. Twelve-month multi-year climatological evolution.
3. Interannual evolution across every selected year.
4. Multi-year mean annual six-variable spatial distribution.
5. Multi-year mean seasonal precipitation distribution.
6. Multi-year mean seasonal cloud-water-resource distribution.

Figure 3 mirrors figure 2's four stacked dual-axis panels, replacing calendar
month with complete four-digit report years: `GMv-CEv`, `GMh-MC`, `CWR-Ps`,
and `RTh-PEh`. This corrects the retained caption's mistaken reference to
monthly rather than interannual evolution.

Figure 3 does not overlay trend lines or significance annotations. Trend
statistics remain available in the metrics artifact and deterministic prose,
while the figure presents the observed annual series without added clutter.

Figure 4 uses an independent tidy colorbar for each of its six physical
variables: `GMv`, `CEv`, `CWR`, `GMh`, `Ps`, and `PEh`. Figure 5 shares one
tidy colorbar across four precipitation seasons. Figure 6 shares one tidy
colorbar across four cloud-water-resource seasons. Seasonal panels therefore
remain directly comparable.

### Template Management

Implementation will copy the retained external multi-year DOCX into the
repository and version it as the reproducible template authority. The external
file remains unchanged. The repository copy preserves layout and receives only
surgical corrections confirmed by this contract, including the figure-3
monthly/interannual wording defect and hard-coded two-digit year prefixes. A
new visual design is outside version 1.

## Retained Template Baseline

The retained template is:

`H:\BY_Weather\routine_bussiness\some_region_report\template\Multi-Year_Evaluation_Report-xizang-cm.docx`

The template contains 68 paragraphs, no prebuilt tables or images, 96 unique
slots, six image slots, and two generated boundary-table slots.

Its content groups are:

1. Evaluation region and period.
2. Multi-year mean regional assessment.
3. Mean boundary transport.
4. Climatological monthly evolution.
5. Interannual evolution and trend.
6. Multi-year mean annual spatial distribution.
7. Multi-year mean seasonal precipitation distribution.
8. Multi-year mean seasonal cloud-water-resource distribution.
9. Deterministic conclusions and discussion.

The template remains the layout authority. Contract design may identify
wording defects, but this stage does not edit the DOCX.

## Verified Product Availability

The authoritative NCEP yearly catalog currently contains one product for every
year from 2000 through 2025. The retained historical case requests 2021 through
2025, and all five yearly products are present.

Monthly-product availability is verified for the acceptance range: each year
from 2021 through 2025 has exactly twelve official monthly products, for a
total of sixty.

The version-1 real acceptance case is the Inner Mongolia central-western
seven-league study region for 2021 through 2025. It reuses the repository SHP
and compiles one mask for all five yearly and sixty monthly products.

## Fixed Inherited Rules

- `region_spec` is mandatory because all regional, boundary, spatial, and
  figure results depend on one compiled mask.
- Annual calculations read official yearly products.
- Monthly and seasonal calculations read official monthly products.
- Finer-scale products are not resampled to create coarser authoritative
  products.
- One compiled mask is reused for every selected year and month.
- Standardized metrics, spatial composites, figures, and DOCX remain separate
  artifacts indexed by one `report_inputs.json`.
- Spatial figures use polygon clipping for SHP regions and the accepted tidy
  colorbar rules.
- The workflow publishes all artifacts transactionally.

## Workflow Specification

Version 1 uses one JSON task:

```json
{
  "schema_version": 1,
  "workflow": "cloud_water_multi_year",
  "task_id": "nmg-zxb-cloud-water-2021-2025",
  "start_year": 2021,
  "end_year": 2025,
  "region_name": "内蒙古中西部七盟市研究区",
  "product_source": {
    "root": "H:\\result_china\\NCEP",
    "engine": "h5netcdf"
  },
  "region_spec": {
    "kind": "shp",
    "payload": {
      "path": "path/to/region.shp"
    }
  },
  "template": "data/templates/Multi-Year_Evaluation_Report-cwr-v1.docx",
  "output_root": "artifacts/runs/nmg-zxb-cloud-water-2021-2025",
  "report_filename": "2021-2025-Year_Evaluation_Report-nmg-zxb.docx",
  "image_width_inches": 4.0
}
```

`start_year` and `end_year` are the only report-period fields. The workflow
does not accept arbitrary year lists, retained CSV/NetCDF intermediates, or
explicit historical image paths.

## Calculation Contract

### Per-Year Regional Metrics

For each official yearly product, the workflow applies the accepted
single-year formulas independently and records:

- Regional `GMv`, `GMh`, `SP`, `CWR`, `MC`, `CEv`, `PEv`, `PEh`, `RCv`, and
  `RCh` values.
- Equivalent depths using that year's validated regional `dxy`.
- Water-vapor and hydrometeor input, output, and net input for west, east,
  south, north, and total boundaries.

The grid, coordinates, `dxy`, and compiled mask must be compatible across all
selected products. Ratios and efficiencies are calculated per official period
before cross-year averaging; they are not reconstructed as a ratio of
multi-year mean numerators and denominators.

### Monthly and Seasonal Climatology

Each of the twelve calendar-month records contains cross-year means for
`GMv`, `GMh`, `MC`, `CWR`, `SP`, `CEv`, `PEh`, and `RCh`, plus equivalent
depths where applicable. Seasons are spring (March-May), summer (June-August),
autumn (September-November), and winter (December-February). Winter is formed
within each calendar report year from January, February, and December before
cross-year averaging; no month from outside the selected range is required.

### Interannual Statistics

Annual `GMh`, `SP`, and `CWR` series provide value ranges, maximum, second
maximum, minimum, and second minimum records under the confirmed tie rule.
Each also provides the confirmed Mann-Kendall and Theil-Sen trend record.
An exactly zero Theil-Sen slope is described as `基本稳定` and is never called
significant.

## Standard Artifacts

### Business Metrics JSON

The schema-versioned `business_metrics` artifact contains:

- Task identity, region, inclusive period, year count, and source trace.
- One `annual_series` record per selected year.
- One `multi_year_mean` record.
- Exactly twelve `monthly_climatology` records.
- Exactly four `seasonal_climatology` records.
- Mean boundary transport rows and period-specific source values.
- Interannual extrema and trend records for `GMh`, `SP`, and `CWR`.

### Spatial Composite NetCDF

One NetCDF artifact contains the compiled `ind_area_bool` mask and semantic
variables rather than report-number names:

- `annual_mean_gmv_mm`, `annual_mean_cev_percent`, `annual_mean_cwr_mm`,
  `annual_mean_gmh_mm`, `annual_mean_sp_mm`, and
  `annual_mean_peh_percent`.
- `seasonal_mean_sp_mm` with a four-value `season` dimension.
- `seasonal_mean_cwr_mm` with the same `season` dimension.

Every annual field is derived for its year first and then averaged across
years. Every seasonal field is derived within each year first and then
averaged across years.

### Report Inputs Index

One `report_inputs.json` indexes exactly one metrics JSON, one spatial NetCDF,
six `profile_image` PNG files, and one final DOCX. All indexed paths point to
the published output root.

## Figure Contracts

- Figure 1 reuses the accepted padded region, SHP, and compiled-mask preview.
- Figure 2 uses four stacked dual-axis panels for the twelve climatological
  months: `GMv-CEv`, `GMh-MC`, `CWR-SP`, and `RCh-PEh`.
- Figure 3 uses the same four panels for complete four-digit years and does not
  draw trend lines.
- Figure 4 is a 3-by-2 annual-mean map of `GMv`, `CEv`, `CWR`, `GMh`, `SP`,
  and `PEh`, with one tidy colorbar per panel.
- Figure 5 is a 2-by-2 seasonal precipitation map with one shared tidy
  colorbar.
- Figure 6 is a 2-by-2 seasonal cloud-water-resource map with one shared tidy
  colorbar.

SHP maps contour the complete continuous field and then clip it to the source
geometry. Existing-mask and bounding-box regions use masked values. Map
padding and colorbar formatting follow the accepted single-year rules.

## Table Contracts

Both generated three-line tables have columns `边界名称`, `输入`, `输出`, and
`净输入`, with rows ordered west, east, south, north, and total. Table 1 uses
water vapor; table 2 uses hydrometeors. Values are annual means in `亿吨/年`
with one decimal place.

## Template Slot Mapping

The versioned template maps every slot into one of these declared groups:

- Identity and period: `first_year`, `last_year`, `year_period`, and
  `region_name`.
- Multi-year means: `GMv_Kg`, `GMv_mm`, `GMh_Kg`, `GMh_mm`, `SP_Kg`,
  `SP_mm`, `CWR_Kg`, `CWR_mm`, `CEv_values`, `PEh_values`, `RTv_values`,
  `RTh_values`, `PEh_level`, and `RTh_level`.
- Monthly and seasonal narrative: `SP_season_1` through `SP_season_4`,
  `SP_max_month`, `SP_min_month`, `SP_win`, `SP_sum`, `SP_ratio`,
  `CWR_peak_feature`, `CWR_maximum_month`, `CWR_second_maximum_month`,
  `CWR_minimum_month`, `CWR_second_minimum_month`, and `CWR_season_1`
  through `CWR_season_4`.
- Interannual extrema and trend: `GMh_Kg_min`, `GMh_Kg_max`, `GMh_mm_min`,
  `GMh_mm_max`, `GMh_maximum_year`, `GMh_second_maximum_year`,
  `GMh_minimum_year`, `SP_Kg_min`, `SP_Kg_max`, `SP_mm_min`, `SP_mm_max`,
  `SP_maximum_year`, `SP_second_maximum_year`, `SP_minimum_year`,
  `SP_second_minimum_year`, `CWR_maximum_year`,
  `CWR_second_maximum_year`, `CWR_minimum_year`,
  `CWR_second_minimum_year`, `GMh_trend`, `SP_trend`, and `CWR_trend`.
- Boundary narrative: all `Vinput_*`, `Voutput_*`, `Dv_*`, `Hinput_*`,
  `Houtput_*`, `Dh_*`, and `scale` slots.
- Spatial narrative: `pic4_a`, `pic4_b`, `pic4_c`, `pic4_e`, `pic4_f`, all
  `pic5_*`, and all `pic6_*` slots.
- Tables: `table_for_TFdatav` and `table_for_TFdatah`.
- Images: `target_image1` through `target_image6`.

The implementation must enumerate the exact final slot set in a test and fail
for any unmapped or unresolved slot.

## Deterministic Narrative Rules

Narratives are generated from standardized metrics without a language-model
dependency. Existing accepted single-year rules are reused for seasonal order,
monthly peaks, spatial direction, efficiency level, residence-time level, and
boundary dominance. Confirmed tie and trend rules override historical code.

## Template Corrections

The repository template copy receives these reviewed corrections:

- Replace the figure-3 description of `逐月演变` with `年际变化`.
- Replace hard-coded `20<<year>>` fragments with complete-year slots that can
  contain multiple tied years.
- Rename the condensation-efficiency slot from historical `PEv_values` to
  `CEv_values` and bind it to `CEv`.
- Correct the stray `图2给出了年...` wording.
- Replace hard-coded dataset end-year wording with versioned source-coverage
  slots where it appears.
- Ensure conclusion trend wording uses each variable's own trend record.

No other prose, style, pagination, or layout change is authorized in version
1 unless required by render verification.

## Failure and Transaction Rules

Validation fails before formal publication for invalid or shorter-than-five
periods, missing or duplicate products, incompatible grids, missing variables,
non-finite values, empty masks, unmapped slots, malformed figures, or
unresolved report placeholders. Metrics, spatial data, six figures, index, and
DOCX are built in a sibling staging directory and published together. A failed
rerun preserves the previous accepted output.

## Version-1 Acceptance

The real acceptance task is Inner Mongolia central-western seven-league region
for 2021-2025. Acceptance requires:

- Five yearly and sixty monthly official products are read exactly once per
  required period.
- One SHP-derived mask is used by every regional, boundary, spatial, and
  figure calculation.
- Metrics contain five annual, twelve monthly-climatology, four seasonal, four
  boundary plus total, three extrema, and three trend result groups.
- Trend fixtures verify significant increase, significant decrease,
  non-significant increase/decrease, stability, and tied extrema.
- Spatial fixtures verify derive-then-average semantics for nonlinear fields.
- Six PNGs pass data and layout checks, including shared scales and tidy
  colorbars.
- The DOCX contains two three-line tables, six images, no unresolved slots,
  and the expected period and region text.
- Failure after metric generation leaves no partial formal output.
- The full test suite passes in `cwr_py312`.
