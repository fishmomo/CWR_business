import numpy as np
import xarray as xr

from cwr_engine.data_sources.netcdf import load_netcdf_source


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("prepare")
    task = context["task"]
    source_name = task.data_source["name"]
    if source_name == "demo":
        context["prepared_dataset"] = _build_demo_dataset()
        return context
    if source_name in {"nc", "netcdf"}:
        dataset, trace = load_netcdf_source(context)
        context["prepared_dataset"] = dataset
        context["runtime"]["data_source"] = trace
        return context
    raise ValueError(f"Unsupported data source for current bootstrap engine: {source_name}")


def _build_demo_dataset() -> xr.Dataset:
    times = np.array(["2025-01-01"], dtype="datetime64[ns]")
    lats = np.array([30.0, 31.0, 32.0, 33.0, 34.0, 35.0])
    lons = np.array([100.0, 102.0, 104.0, 106.0, 108.0, 110.0])

    base_component = np.array([6.5], dtype=float)[:, None, None]
    lat_component = np.arange(len(lats), dtype=float)[None, :, None]
    lon_component = np.arange(len(lons), dtype=float)[None, None, :]
    temp = base_component + lat_component + lon_component

    dataset = xr.Dataset(
        data_vars={
            "temp": (("time", "lat", "lon"), temp),
        },
        coords={
            "time": times,
            "lat": lats,
            "lon": lons,
        },
        attrs={"source_name": "demo", "time_scale": "year"},
    )
    return dataset
