from cwr_engine.cache import build_mask_signature
from cwr_engine.models.region import build_region_spec


def test_build_bbox_region_spec():
    spec = build_region_spec(
        {
            "kind": "bbox",
            "payload": {
                "min_lon": 100.0,
                "max_lon": 110.0,
                "min_lat": 30.0,
                "max_lat": 35.0,
            },
        }
    )
    assert spec.kind == "bbox"
    assert spec.payload["min_lon"] == 100.0


def test_mask_signature_is_stable_for_same_payload():
    payload = {
        "kind": "bbox",
        "payload": {
            "min_lon": 100.0,
            "max_lon": 110.0,
            "min_lat": 30.0,
            "max_lat": 35.0,
        },
    }
    sig1 = build_mask_signature(payload, {"resolution": 0.25})
    sig2 = build_mask_signature(payload, {"resolution": 0.25})
    assert sig1 == sig2
