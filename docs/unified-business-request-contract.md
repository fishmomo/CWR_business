# Unified Business Request Contract

## Purpose

The version-1 business request is the user-facing entrypoint for common
computations. It describes the data source, mandatory region, source-product
time scale and periods, physical variables, operators, and requested files.
The adapter validates and compiles it into the existing bottom-layer engine
task; it does not implement a second calculation pipeline.

Run a request with:

```powershell
conda run -n cwr_py312 cwr-engine --request path/to/request.json
```

`--output-root` may override the configured output directory.

## Complete Example

```json
{
  "schema_version": 1,
  "request_id": "monthly-analysis",
  "data_source": {
    "kind": "netcdf",
    "root": "H:\\result_china\\NCEP",
    "engine": "h5netcdf"
  },
  "region": {
    "kind": "shp",
    "path": "../data/region.shp"
  },
  "period": {
    "scale": "month",
    "year_range": [2021, 2025],
    "months": [4, 5, 6]
  },
  "variables": ["GMv", "CWR", "Ps"],
  "operators": ["mean", "max"],
  "results": [
    {"scope": "region", "format": "csv", "name": "regional"},
    {"scope": "grid", "format": "netcdf", "name": "gridded"},
    {
      "scope": "region",
      "format": "figure",
      "plot": "time_series",
      "name": "series"
    },
    {
      "scope": "grid",
      "format": "figure",
      "plot": "distribution",
      "name": "maps"
    }
  ],
  "output_root": "../artifacts/runs/monthly-analysis"
}
```

Input paths and `output_root` are resolved relative to the request file unless
they are absolute. A CLI `--output-root` is resolved from the current working
directory.

## Data And Region

`data_source.kind` is `netcdf`. `root` may point to one file, one scale
directory, or a catalog root containing `D`, `M`, and `Y`. Optional fields are
`engine`, `pattern`, `coordinate_map`, and `variable_map`.

`region` is mandatory. Accepted forms are:

```json
{"kind": "shp", "path": "region.shp"}
```

```json
{"kind": "existing_mask", "path": "mask.nc", "variable": "mask"}
```

```json
{
  "kind": "bbox",
  "min_lon": 100.0,
  "max_lon": 110.0,
  "min_lat": 30.0,
  "max_lat": 35.0
}
```

Every form is compiled into the mandatory internal mask before slicing or
calculation. Supplying an existing mask skips SHP compilation but not the mask
stage.

## Period Selection

One request uses exactly one official source-product scale. The engine does
not resample daily products into monthly products or monthly products into
annual products.

Annual requests accept explicit years or one inclusive range:

```json
{"scale": "year", "years": [2021, 2023, 2025]}
```

```json
{"scale": "year", "year_range": [2021, 2025]}
```

Monthly requests accept exact year-month items or the cross product of years
and months:

```json
{"scale": "month", "items": ["2024-12", "2025-01"]}
```

```json
{"scale": "month", "years": [2024, 2025], "months": [6, 7, 8]}
```

Daily requests accept explicit dates or one inclusive date range:

```json
{"scale": "day", "dates": ["2025-01-01", "2025-01-03"]}
```

```json
{"scale": "day", "date_range": ["2025-01-01", "2025-01-31"]}
```

All requested source periods are required. A missing product fails the whole
request before formal result files are completed.

## Variables And Results

Registered general variables are `temp` and `precip`. The standardized cloud-
water names are `GMv`, `GMh`, `Dv`, `Dh`, `CWR`, `CEv`, `PEv`, `PEh`, `Qvi`,
`Qvo`, `Qhi`, `Qho`, `Cvh`, `Ps`, `RTv`, and `RTh`. Historical source keys are
resolved by the registry, including `MC` to `Cvh`, `SP` to `Ps`, and `RCv/RCh`
to `RTv/RTh`.

Supported operators are `mean`, `max`, `min`, and `sum`. Each result uses one
of these combinations:

| Scope | Format | Plot | Product |
| --- | --- | --- | --- |
| `region` | `csv` | omitted | Regional statistics table |
| `grid` | `netcdf` | omitted | Masked gridded result |
| `region` | `figure` | `time_series` | Regional time series |
| `region` | `figure` | `bar_compare` | Regional comparison bars |
| `grid` | `figure` | `distribution` | Spatial distribution |

Figure `params` use the standard plot contract. Multiple selected periods are
preserved in NetCDF as a `period` dimension. A single selected period retains
the compatible two-dimensional `lat × lon` structure. Standard gridded results
are written as NetCDF4/HDF5 through `h5netcdf`.

Every successful run also writes
`report_inputs/request_manifest.json`, which indexes the generated artifacts
for optional upper-layer reports or thematic products.

## Failure Policy

The schema is strict: unknown fields, duplicate values or output names,
unsupported combinations, invalid dates, missing region definitions, and
unregistered variables/operators are rejected. Protocol and plot-validation
errors occur before the output directory is created. Runtime source or grid
errors stop execution immediately; transactional publication remains the
responsibility of an upper-layer report workflow.
