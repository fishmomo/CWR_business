from __future__ import annotations

from pathlib import Path
from typing import Any


def required_text(payload: dict[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty string")
    return value


def resolve_path(base: Path, payload: dict[str, Any], key: str) -> Path:
    path = Path(required_text(payload, key))
    return path if path.is_absolute() else (base / path).resolve()


def existing_file(base: Path, payload: dict[str, Any], key: str) -> Path:
    path = resolve_path(base, payload, key)
    if not path.is_file():
        raise ValueError(f"{key} does not exist: {path}")
    return path


def normalize_product_source(
    base: Path,
    value: Any,
    *,
    serialize_root: bool = False,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("product_source must be an object")
    raw_root = value.get("root")
    if not isinstance(raw_root, str) or not raw_root.strip():
        raise ValueError("product_source.root must be a non-empty path")
    root = Path(raw_root)
    root = root if root.is_absolute() else (base / root).resolve()
    if not root.is_dir():
        raise ValueError(f"product_source.root does not exist: {root}")
    source = {**value, "root": str(root) if serialize_root else root}
    for key in ("coordinate_map", "variable_map"):
        if key in source and not isinstance(source[key], dict):
            raise ValueError(f"product_source.{key} must be an object")
    for key in ("annual_pattern", "monthly_pattern", "engine"):
        if key in source and (
            not isinstance(source[key], str) or not source[key].strip()
        ):
            raise ValueError(f"product_source.{key} must be a non-empty string")
    return source


def normalize_region_spec(base: Path, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError("region_spec must be an object")
    kind = value.get("kind")
    payload = value.get("payload")
    if kind not in {"shp", "existing_mask", "bbox"}:
        raise ValueError("region_spec.kind must be shp, existing_mask, or bbox")
    if not isinstance(payload, dict):
        raise ValueError("region_spec.payload must be an object")
    resolved = dict(payload)
    if kind in {"shp", "existing_mask"}:
        raw_path = payload.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("region_spec.payload.path must be a non-empty path")
        path = Path(raw_path)
        path = path if path.is_absolute() else (base / path).resolve()
        if not path.is_file():
            raise ValueError(f"region_spec path does not exist: {path}")
        resolved["path"] = str(path)
    elif {"min_lon", "max_lon", "min_lat", "max_lat"} - set(payload):
        missing = sorted(
            {"min_lon", "max_lon", "min_lat", "max_lat"} - set(payload)
        )
        raise ValueError(f"bbox region_spec is missing {missing[0]}")
    return {"kind": kind, "payload": resolved}
