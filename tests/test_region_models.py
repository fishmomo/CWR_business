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
