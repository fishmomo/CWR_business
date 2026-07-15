import json
from pathlib import Path

from cwr_engine.cache import build_mask_signature
from cwr_engine.models.region import MaskBundle
import numpy as np
import pyproj
import shapefile
import xarray as xr
from shapely.geometry import Point, shape
from shapely.ops import transform, unary_union


def run(context: dict) -> dict:
    context["runtime"]["executed_steps"].append("mask")
    task = context["task"]
    output_root: Path = context["output_root"]
    payload = task.region_spec.payload
    dataset = context["prepared_dataset"]
    mask_dir = output_root / "mask"
    bundle_path = mask_dir / "mask_bundle.json"

    if task.region_spec.kind == "existing_mask":
        mask_data = _load_existing_mask(context)
        mask_path = _resolve_path(payload["path"], context["task_path"])
    elif task.region_spec.kind == "shp":
        mask_data = _build_shp_mask(context)
        mask_path = _resolve_path(payload["path"], context["task_path"])
    else:
        mask_data = _build_bbox_mask(dataset, payload)
        mask_path = bundle_path

    grid_definition = {
        "lat": "lat",
        "lon": "lon",
        "shape": [int(mask_data.sizes["lat"]), int(mask_data.sizes["lon"])],
    }
    spatial_bounds = _derive_bounds(mask_data)
    signature = build_mask_signature(
        {"kind": task.region_spec.kind, "payload": payload},
        grid_definition,
    )
    bundle = MaskBundle(
        mask_path=str(mask_path),
        preview_path=str(mask_dir / "mask_preview.png"),
        grid_definition=grid_definition,
        spatial_bounds=spatial_bounds,
        signature=signature,
    )
    bundle_path.write_text(
        json.dumps(
            {
                "mask_path": bundle.mask_path,
                "preview_path": bundle.preview_path,
                "grid_definition": bundle.grid_definition,
                "spatial_bounds": bundle.spatial_bounds,
                "signature": bundle.signature,
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    context["mask_bundle"] = bundle
    context["mask_data"] = mask_data
    return context


def _load_existing_mask(context: dict) -> xr.DataArray:
    payload = context["task"].region_spec.payload
    mask_path = _resolve_path(payload["path"], context["task_path"])
    engine = payload.get("engine")
    if engine:
        dataset = xr.load_dataset(mask_path, engine=engine)
    else:
        dataset = xr.load_dataset(mask_path)
    variable = payload.get("variable")
    if variable is None:
        variable = next(iter(dataset.data_vars))
    mask_data = dataset[variable].astype(bool)
    return mask_data


def _build_bbox_mask(dataset: xr.Dataset, payload: dict) -> xr.DataArray:
    sample = dataset[next(iter(dataset.data_vars))].isel(time=0)
    lon_mask = (dataset["lon"] >= payload["min_lon"]) & (dataset["lon"] <= payload["max_lon"])
    lat_mask = (dataset["lat"] >= payload["min_lat"]) & (dataset["lat"] <= payload["max_lat"])
    return (lat_mask.broadcast_like(sample) & lon_mask.broadcast_like(sample)).rename("mask")


def _build_shp_mask(context: dict) -> xr.DataArray:
    task = context["task"]
    dataset = context["prepared_dataset"]
    payload = task.region_spec.payload
    shp_path = _resolve_path(payload["path"], context["task_path"])
    geometry = _load_shp_geometry(shp_path, payload)
    sample = dataset[next(iter(dataset.data_vars))].isel(time=0)
    lon_values = sample["lon"].values
    lat_values = sample["lat"].values
    mask = np.zeros((len(lat_values), len(lon_values)), dtype=bool)
    for lat_index, lat in enumerate(lat_values):
        for lon_index, lon in enumerate(lon_values):
            mask[lat_index, lon_index] = geometry.covers(Point(float(lon), float(lat)))
    return xr.DataArray(mask, coords={"lat": lat_values, "lon": lon_values}, dims=("lat", "lon"), name="mask")


def _load_shp_geometry(shp_path: Path, payload: dict):
    reader = shapefile.Reader(str(shp_path))
    geometries = [shape(item.__geo_interface__) for item in reader.shapes()]
    geometry = unary_union(geometries)
    source_crs = _detect_source_crs(shp_path, payload)
    target_crs = payload.get("target_crs", "EPSG:4326")
    if source_crs and target_crs and source_crs != target_crs:
        transformer = pyproj.Transformer.from_crs(source_crs, target_crs, always_xy=True)
        geometry = transform(transformer.transform, geometry)
    return geometry


def _detect_source_crs(shp_path: Path, payload: dict) -> str | None:
    if payload.get("source_crs"):
        return payload["source_crs"]
    prj_path = shp_path.with_suffix(".prj")
    if not prj_path.exists():
        return None
    prj_text = prj_path.read_text(encoding="utf-8")
    return pyproj.CRS.from_wkt(prj_text).to_string()


def _derive_bounds(mask_data: xr.DataArray) -> dict[str, float]:
    return {
        "min_lon": float(mask_data["lon"].min().item()),
        "max_lon": float(mask_data["lon"].max().item()),
        "min_lat": float(mask_data["lat"].min().item()),
        "max_lat": float(mask_data["lat"].max().item()),
    }


def _resolve_path(raw_path: str, task_path: Path) -> Path:
    path = Path(raw_path)
    if path.is_absolute():
        return path
    return (task_path.parent / path).resolve()
