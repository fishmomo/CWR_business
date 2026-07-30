# Cloud-Water Business Metrics

## Purpose

The `cloud_water_single_year` metric workflow converts retained annual and
monthly regional tables plus the spatial composite inputs into two standardized
artifacts:

- A schema-versioned `business_metrics` JSON document.
- A normalized `spatial_composite` NetCDF document containing the region mask.

Both artifacts are indexed by one standard `report_inputs.json`. Report
products consume that index and do not receive the source CSV or source
spatial NetCDF paths.

## Build Specification

```json
{
  "metric_profile": "cloud_water_single_year",
  "task_id": "nmg-zxb-cloud-water-2025",
  "year": 2025,
  "region_name": "内蒙古中西部七盟市研究区",
  "annual_csv": "nmg-zxb_NCEP_00to25_Y.csv",
  "monthly_csv": "nmg-zxb_NCEP_00to25_M.csv",
  "mask_nc": "nmg-zxb.nc",
  "spatial_nc": "nmg-zxb_picdata.nc",
  "output_root": "artifacts/runs/nmg-zxb-business-metrics-2025"
}
```

Relative paths resolve from the build-specification directory.

## Artifacts

The metrics JSON uses `schema_version: 1` and records:

- Annual source values and equivalent depths.
- Exactly twelve monthly `SP` and `CWR` values.
- Spring, summer, autumn, and winter summaries.
- Water-vapor and hydrometeor input, output, and net input for four boundaries
  plus totals.
- The expected spatial-composite artifact name, mask, and variables.

The spatial NetCDF contains `ind_area_bool` and the retained `pic3_*`,
`pic4_*`, and `pic5_*` composite variables. Large gridded arrays are not
embedded in JSON.

Equivalent monthly and seasonal depths use the annual regional `dxy`, matching
the retained single-year calculation.

## Failure Rules

The workflow validates all source files before creating formal artifacts. It
fails for a missing or duplicate annual row, missing or duplicate month,
missing column, non-finite number, zero area, missing spatial variable,
incompatible mask/grid shape, or unsupported NetCDF format.

## Command

```powershell
conda run -n cwr_py312 cwr-engine --business-metrics-spec path/to/spec.json
```
