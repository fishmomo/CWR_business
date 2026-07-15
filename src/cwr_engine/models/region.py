from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegionSpec:
    kind: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class MaskBundle:
    mask_path: str
    preview_path: str
    grid_definition: dict[str, Any]
    spatial_bounds: dict[str, float]
    signature: str


def build_region_spec(payload: dict[str, Any]) -> RegionSpec:
    kind = payload["kind"]
    if kind not in {"shp", "existing_mask", "bbox"}:
        raise ValueError(f"Unsupported region kind: {kind}")
    return RegionSpec(kind=kind, payload=payload["payload"])
