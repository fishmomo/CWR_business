# Cloud-Water Single-Year Report Profile

## Boundary

The `cloud_water_single_year` profile adapts the retained
`Simple-Year_Evaluation_Report-xizang-cm.docx` template. It is an upper-layer
report product and does not invoke generalized computation steps.

The profile requires a successful standard `report_inputs.json` that indexes
exactly one `cloud_water_single_year` business-metrics artifact and one spatial
composite. When the index also contains the five standard `profile_image`
artifacts, task identity, report year, region name, annual/monthly values,
boundary metrics, spatial variables, and figures are all resolved from that
single index.

The standard report profile directly declares only the retained template and
output. It does not receive the source CSV, mask, source spatial NetCDF, or
historical figure paths.

The former supplemental CSV/NetCDF inputs and explicit historical image paths
are no longer accepted. Reports must consume the standardized artifacts and
five `profile_image` records indexed by `report_inputs.json`.

## Profile Specification

```json
{
  "profile": "cloud_water_single_year",
  "report_inputs": "run/report_inputs/report_inputs.json",
  "template": "Simple-Year_Evaluation_Report-xizang-cm.docx",
  "output": "report.docx",
  "image_width_inches": 4.0,
  "image_widths_inches": {
    "target_image3": 6.2
  }
}
```

Relative paths resolve from the profile specification directory.
`image_width_inches` is the default for every image. The optional
`image_widths_inches` object overrides known image slots individually; unknown
slots and non-positive widths fail validation.

## Derivation Rules

- Annual totals are converted to `亿吨` with a divisor of `1e11`.
- Equivalent water depth divides annual or monthly totals by `dxy`.
- Spring is March-May, summer June-August, autumn September-November,
  and winter December-February.
- Boundary tables report input, output, and net input for west, east, south,
  north, and the total.
- Spatial descriptions use a normalized two-dimensional trend plane to assign
  one of eight directions from low values to high values.
- All numbers inserted into the retained template use explicit one-decimal
  formatting unless a profile rule states otherwise.

## Failure Rules

The profile fails without a DOCX when the standard task is unsuccessful; the
required indexed artifacts are missing, duplicated, or incompatible; any month
or required metric is missing; standard profile images are partial,
duplicated, or missing on disk; or any template slot remains unresolved.

## Command

```powershell
conda run -n cwr_py312 cwr-report --profile-spec path/to/profile.json
```
