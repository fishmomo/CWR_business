# Real Product Data Source Contract

## Directory layout

The supported NetCDF catalog layout is:

```text
<root>/
  D/ResultGrid_D_<start>_<end>.nc
  M/ResultGrid_M_<start>_<end>.nc
  Y/ResultGrid_Y_<start>_<end>.nc
```

`data_source.time_scale` selects `D`, `M`, or `Y`. A task may instead point
`root` directly at one scale directory or at one NetCDF file.

## Task fields

```json
{
  "name": "nc",
  "root": "H:\\result_china\\NCEP",
  "time_scale": "month",
  "pattern": "ResultGrid_M_*.nc",
  "coordinate_map": {
    "time": "time",
    "lat": "latitude",
    "lon": "longitude"
  },
  "variable_map": {
    "Cvh": "MC",
    "Ps": "SP"
  }
}
```

`pattern`, `coordinate_map`, and `variable_map` are optional. Default discovery
matches the existing `ResultGrid_D/M/Y` filenames. Coordinate detection
recognizes `time`, `lat/latitude`, and `lon/longitude`.

## Selection and validation

The first date encoded in each filename identifies its product period. The
engine filters filenames against requested time slices before opening files.
It then:

1. Loads only requested source variables.
2. Converts scalar time coordinates into a time dimension.
3. Normalizes spatial coordinates and dimensions to `lat` and `lon`.
4. Sorts coordinates in ascending order.
5. Combines files and rejects duplicate internal times.
6. Verifies that every requested day, month, or year period exists.

The engine does not derive one official product scale from another.
