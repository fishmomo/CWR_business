import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from cwr_engine.workflows.cloud_water_request_contract import (
    merge_request_member,
    resolve_request_product,
    validate_request_members,
    validate_request_set_header,
    validate_shared_request,
    write_mask_bundle,
)


def _payload(tmp_path: Path) -> dict:
    template = tmp_path / "template.docx"
    template.write_bytes(b"template")
    return {
        "schema_version": 1,
        "request_set": "cloud_water_test",
        "request_set_id": "shared-contract",
        "shared_request": {
            "data_source": {"kind": "netcdf", "root": "products"},
            "region": {
                "kind": "bbox",
                "payload": {"bounds": [100.0, 40.0, 101.0, 41.0]},
            },
        },
        "requests": {
            "annual": {
                "request_id": "annual",
                "period": {"scale": "year", "years": [2025]},
                "variables": ["CWR"],
                "operators": ["mean"],
                "results": [],
            },
            "monthly": {
                "request_id": "monthly",
                "period": {
                    "scale": "month",
                    "years": [2025],
                    "months": list(range(1, 13)),
                },
                "variables": ["CWR"],
                "operators": ["mean"],
                "results": [],
            },
        },
        "product": {
            "region_name": "test region",
            "template": "template.docx",
            "report_filename": "report.docx",
        },
        "output_root": "run",
    }


def test_shared_contract_normalizes_common_request_fields(tmp_path: Path) -> None:
    payload = validate_request_set_header(_payload(tmp_path), "cloud_water_test")
    shared = validate_shared_request(payload["shared_request"])
    members = validate_request_members(payload["requests"])
    annual = merge_request_member(shared, members["annual"])
    product = resolve_request_product(payload["product"], tmp_path, ["target_image1"])

    assert annual["schema_version"] == 1
    assert annual["data_source"] is shared["data_source"]
    assert annual["region"] is shared["region"]
    assert product == {
        "region_name": "test region",
        "template": tmp_path / "template.docx",
        "report_filename": "report.docx",
        "image_width_inches": 4.0,
        "image_widths_inches": {},
    }


def test_shared_contract_rejects_unknown_nested_fields(tmp_path: Path) -> None:
    payload = _payload(tmp_path)
    payload["shared_request"]["data_source"]["pattern"] = "*.nc"

    validate_request_set_header(payload, "cloud_water_test")
    with pytest.raises(ValueError, match="pattern is not a recognized field"):
        validate_shared_request(payload["shared_request"])


def test_shared_mask_bundle_has_stable_metadata(tmp_path: Path) -> None:
    mask = xr.DataArray(
        np.array([[True, False], [True, True]]),
        dims=("lat", "lon"),
        coords={"lat": [40.0, 41.0], "lon": [100.0, 101.0]},
    )
    region = {
        "kind": "bbox",
        "payload": {"bounds": [100.0, 40.0, 101.0, 41.0]},
    }

    bundle = write_mask_bundle(mask, region, tmp_path)
    payload = json.loads(
        (tmp_path / "mask" / "mask_bundle.json").read_text(encoding="utf-8")
    )

    assert bundle.grid_definition == {
        "lat": "lat",
        "lon": "lon",
        "shape": [2, 2],
    }
    assert payload["mask_path"] == bundle.mask_path
    assert payload["spatial_bounds"] == bundle.spatial_bounds
    assert payload["signature"] == bundle.signature
