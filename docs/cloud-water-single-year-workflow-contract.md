# Cloud-Water Single-Year Workflow Contract

## Purpose

The `cloud_water_single_year` workflow runs the accepted direct-product
single-year business product from one JSON specification. It discovers the
official annual and monthly NetCDF products, compiles the required region mask,
derives standardized metrics and figures, and assembles the DOCX report.

The workflow is a thin orchestration layer. The independent business-metrics
and report-profile commands remain supported.

## Specification

```json
{
  "schema_version": 1,
  "workflow": "cloud_water_single_year",
  "task_id": "region-cloud-water-2025",
  "year": 2025,
  "region_name": "Region name",
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
  "template": "path/to/template.docx",
  "output_root": "artifacts/runs/region-cloud-water-2025",
  "report_filename": "2025-cloud-water-report.docx",
  "image_width_inches": 4.0,
  "image_widths_inches": {
    "target_image3": 6.2,
    "target_image4": 6.2,
    "target_image5": 6.2
  }
}
```

`product_source` and `region_spec` use the direct business-metrics contracts.
The region is mandatory because the compiled mask is required by every
downstream calculation and map.

`report_filename` must be a filename with the `.docx` suffix. It is written
under the published run's `report` directory. `image_width_inches` is optional
and defaults to `4.0`. `image_widths_inches` optionally overrides that default
for named report image slots.

## Execution

```powershell
conda run -n cwr_py312 cwr-engine --workflow-spec path/to/workflow.json
```

The command returns the final DOCX path.

## Published Layout

The output root contains:

- `business_metrics/`
- `spatial_composite/`
- `profile_image/`
- `report_inputs/report_inputs.json`
- `report/<report_filename>`

All paths recorded in `report_inputs.json` refer to the published output root.

## Transaction Rule

The workflow builds into a sibling staging directory. The formal output root
is replaced only after metrics, figures, and the DOCX all succeed. If any step
fails, staging data are removed and an existing published output is unchanged.
