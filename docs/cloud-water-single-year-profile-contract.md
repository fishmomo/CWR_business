# Cloud-Water Single-Year Report Profile

## Boundary

The `cloud_water_single_year` profile adapts the retained
`Simple-Year_Evaluation_Report-xizang-cm.docx` template. It is an upper-layer
report product and does not invoke generalized computation steps.

The profile requires a successful standard `report_inputs.json` for task
identity and report-year consistency. Until boundary-flow metrics and
report-specific spatial composites are standard engine artifacts, the profile
also declares these supplemental inputs explicitly:

- One annual regional CSV.
- One monthly regional CSV containing all twelve months.
- One region-mask NetCDF.
- One single-year spatial-analysis NetCDF.
- Five figure files matching the retained template.

The supplemental files are transitional, visible dependencies. They are not
described as generalized engine outputs.

## Profile Specification

```json
{
  "profile": "cloud_water_single_year",
  "report_id": "nmg-zxb-2025",
  "year": 2025,
  "region_name": "内蒙古中西部七盟市研究区",
  "report_inputs": "run/report_inputs/report_inputs.json",
  "annual_csv": "annual.csv",
  "monthly_csv": "monthly.csv",
  "mask_nc": "mask.nc",
  "spatial_nc": "single-year-picdata.nc",
  "template": "Simple-Year_Evaluation_Report-xizang-cm.docx",
  "output": "report.docx",
  "image_width_inches": 4.0,
  "images": {
    "target_image1": "mask.png",
    "target_image2": "monthly.png",
    "target_image3": "annual-spatial.png",
    "target_image4": "seasonal-precipitation.png",
    "target_image5": "seasonal-cloud-water.png"
  }
}
```

Relative paths resolve from the profile specification directory.

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

The profile fails without a DOCX when the standard task is unsuccessful or
does not cover the report year; the annual year is missing or duplicated; any
month is missing or duplicated; a required CSV column or spatial variable is
missing; mask and grid shapes differ; an image is missing; or any template slot
remains unresolved.

## Command

```powershell
conda run -n cwr_py312 cwr-report --profile-spec path/to/profile.json
```
