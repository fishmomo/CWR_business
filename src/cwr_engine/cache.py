import hashlib
import json


def _stable_hash(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def build_mask_signature(region_spec: dict, grid_definition: dict) -> str:
    return _stable_hash(
        {
            "region_spec": region_spec,
            "grid_definition": grid_definition,
        }
    )
