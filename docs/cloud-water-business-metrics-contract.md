# Cloud-Water Business Metrics

## Purpose

The `cloud_water_single_year` metric workflow reads the authoritative annual
and monthly product catalogs and compiles the requested region into two
standardized artifacts:

- A schema-versioned `business_metrics` JSON document.
- A normalized `spatial_composite` NetCDF document containing the region mask.
- Five `profile_image` PNG documents generated from those standard data
  products.

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
  "product_source": {
    "root": "H:\\result_china\\NCEP",
    "engine": "h5netcdf"
  },
  "region_spec": {
    "kind": "shp",
    "payload": {
      "path": "region.shp"
    }
  },
  "output_root": "artifacts/runs/nmg-zxb-business-metrics-2025"
}
```

Relative paths resolve from the build-specification directory.

`region_spec` supports `shp`, `existing_mask`, and `bbox`, using the same
region semantics as standard engine tasks. The direct cloud-water profile reads
one official annual product and all twelve official monthly products. It does
not resample daily data because no current single-year report metric requires
daily input.

The former `annual_csv`, `monthly_csv`, `mask_nc`, and `spatial_nc` input set is
no longer accepted. The authoritative product catalog and a mandatory
`region_spec` are the only supported inputs.

## Artifacts

The metrics JSON uses `schema_version: 1` and records:

- Annual source values and equivalent depths.
- Exactly twelve monthly `SP`, `CWR`, `GMv`, `GMh`, `MC`, `CEv`, `RCh`, and
  `PEh` values in direct-product mode.
- Spring, summer, autumn, and winter summaries.
- Water-vapor and hydrometeor input, output, and net input for four boundaries
  plus totals.
- The expected spatial-composite artifact name, mask, and variables.

The spatial NetCDF contains the compiled `ind_area_bool` mask and fourteen
directly derived `pic3_*`, `pic4_*`, and `pic5_*` composite variables,
including the annual `GMh` field required by the six-panel annual figure.
Large gridded arrays are not embedded in JSON.

Direct-product mode also writes five `profile_image` artifacts: the region and
mask preview, monthly four-panel sequence, annual six-panel distribution,
seasonal precipitation distribution, and seasonal cloud-water-resource
distribution. Figure rendering uses `Matplotlib` and the same compiled mask as
the metrics and spatial artifacts.

The cloud-water-resource seasonal figure uses tidy shared colorbar levels.
Values below 1000 display one decimal, while four- and five-digit ranges use
hundred-aligned integer ticks.

For an SHP region, spatial figures draw the complete gridded field first and
then clip the contour set to the source polygon. Setting values outside the
grid mask to `NaN` before contouring is reserved for `existing_mask` and
`bbox` inputs that have no polygon geometry. Map extents include proportional
padding outside the region bounds so boundaries and grid centers are not
visually cramped.

Equivalent monthly and seasonal depths use the annual regional `dxy`, matching
the retained single-year calculation.

## Inner Mongolia Reference Note

The retained 2025 regional CSV values match a fresh compilation of the source
SHP with 52 selected product-grid cells. The separately retained mask contains
72 selected cells, so it is not the mask that produced those CSV values. The
direct-product workflow recompiles the SHP and consistently uses the resulting
52-cell mask for regional, boundary, and spatial metrics. Retained artifacts
remain unchanged as historical reference data and are not runtime inputs.

## Failure Rules

The workflow validates all source files before creating formal artifacts. It
fails for missing or duplicate annual/monthly products, missing variables,
non-finite regional or boundary values, zero area, an empty region, an
incompatible mask/product grid, or an unsupported NetCDF format.

## Command

```powershell
conda run -n cwr_py312 cwr-engine --business-metrics-spec path/to/spec.json
```
