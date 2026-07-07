import numpy as np
import xarray as xr


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("prepare")
    task = context["task"]
    if task.data_source["name"] != "demo":
        raise ValueError(f"Unsupported data source for current bootstrap engine: {task.data_source['name']}")

    times = np.array([f"2025-{month:02d}-01" for month in range(1, 13)], dtype="datetime64[ns]")
    lats = np.array([30.0, 31.0, 32.0, 33.0, 34.0, 35.0])
    lons = np.array([100.0, 102.0, 104.0, 106.0, 108.0, 110.0])

    time_component = np.arange(1, len(times) + 1, dtype=float)[:, None, None]
    lat_component = np.arange(len(lats), dtype=float)[None, :, None]
    lon_component = np.arange(len(lons), dtype=float)[None, None, :]
    temp = time_component + lat_component + lon_component

    dataset = xr.Dataset(
        data_vars={
            "temp": (("time", "lat", "lon"), temp),
        },
        coords={
            "time": times,
            "lat": lats,
            "lon": lons,
        },
        attrs={"source_name": "demo"},
    )
    context["prepared_dataset"] = dataset
    return context
