import csv
import json
from pathlib import Path

from docx import Document
import matplotlib.pyplot as plt
import numpy as np
import pytest
import shapefile
import xarray as xr

from cwr_engine.business_metrics.cloud_water import (
    build_cloud_water_business_metrics,
)
from cwr_report.profiles.cloud_water_single_year import (
    IMAGE_SLOTS,
    TEXT_SLOT_NAMES,
    build_cloud_water_single_year_report,
)


def _write_profile_case(tmp_path: Path) -> Path:
    annual_path = tmp_path / "annual.csv"
    annual_row = {
        "time": "2025-01-01T00:00:00",
        "GMv": 1000e11,
        "GMh": 100e11,
        "SP": 40e11,
        "CWR": 60e11,
        "PEh": 55,
        "PEv": 20,
        "PEw": 25,
        "RCv": 10,
        "RCh": 6,
        "dxy": 10e9,
        "INv_W": 40e11,
        "OTv_W": 10e11,
        "INv_E": 10e11,
        "OTv_E": 50e11,
        "INv_N": 30e11,
        "OTv_N": 20e11,
        "INv_S": 20e11,
        "OTv_S": 15e11,
        "INh_W": 4e11,
        "OTh_W": 1e11,
        "INh_E": 1e11,
        "OTh_E": 5e11,
        "INh_N": 3e11,
        "OTh_N": 2e11,
        "INh_S": 2e11,
        "OTh_S": 1.5e11,
    }
    _write_csv(annual_path, [annual_row])

    monthly_path = tmp_path / "monthly.csv"
    monthly_rows = [
        {
            "time": f"2025-{month:02d}-01T00:00:00",
            "SP": float(month * 10e9),
            "CWR": float((13 - month) * 8e9),
            "dxy": 10e9,
        }
        for month in range(1, 13)
    ]
    _write_csv(monthly_path, monthly_rows)

    lat = [30.0, 31.0, 32.0]
    lon = [100.0, 101.0, 102.0]
    base = np.arange(9, dtype=float).reshape(3, 3)
    spatial_variables = {}
    for index, name in enumerate(
        [
            "pic3_a",
            "pic3_b",
            "pic3_c",
            "pic3_d",
            "pic3_e",
            "pic3_f",
            "pic4_a",
            "pic4_b",
            "pic4_c",
            "pic4_d",
            "pic5_a",
            "pic5_b",
            "pic5_c",
            "pic5_d",
        ]
    ):
        spatial_variables[name] = (("lat", "lon"), base + index)
    spatial_path = tmp_path / "spatial.nc"
    xr.Dataset(
        spatial_variables,
        coords={"lat": lat, "lon": lon},
    ).to_netcdf(spatial_path, engine="scipy")

    mask_path = tmp_path / "mask.nc"
    xr.Dataset(
        {"ind_area_bool": (("lat", "lon"), np.ones((3, 3), dtype=bool))},
        coords={"lat": lat, "lon": lon},
    ).to_netcdf(mask_path, engine="scipy")

    images = {}
    for index, slot in enumerate(IMAGE_SLOTS, start=1):
        image_path = tmp_path / f"image{index}.png"
        fig, ax = plt.subplots()
        ax.imshow(base + index)
        fig.savefig(image_path)
        plt.close(fig)
        images[slot] = str(image_path)

    standard_inputs = tmp_path / "standard-report-inputs.json"
    standard_inputs.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "task": {"task_id": "standard", "status": "success"},
                "inputs": {
                    "time_slices": [
                        {"scale": "year", "year": 2025, "label": "2025"}
                    ]
                },
                "artifacts": [],
                "runtime": {},
                "stats": [],
            }
        ),
        encoding="utf-8",
    )

    template_path = tmp_path / "template.docx"
    template = Document()
    for slot in sorted(TEXT_SLOT_NAMES):
        template.add_paragraph(f"<<{slot}>>")
    template.add_paragraph("<<table_for_TFdatav>>")
    template.add_paragraph("<<table_for_TFdatah>>")
    for slot in IMAGE_SLOTS:
        template.add_paragraph(f"<<{slot}>>")
    template.save(template_path)

    profile_path = tmp_path / "profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "profile": "cloud_water_single_year",
                "report_id": "cloud-water-2025",
                "year": 2025,
                "region_name": "测试区域",
                "report_inputs": str(standard_inputs),
                "annual_csv": str(annual_path),
                "monthly_csv": str(monthly_path),
                "mask_nc": str(mask_path),
                "spatial_nc": str(spatial_path),
                "template": str(template_path),
                "output": "output/report.docx",
                "image_width_inches": 3.0,
                "images": images,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return profile_path


def test_cloud_water_profile_populates_complete_single_year_report(
    tmp_path: Path,
):
    profile_path = _write_profile_case(tmp_path)

    output = build_cloud_water_single_year_report(profile_path)

    document = Document(output)
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "<<" not in text
    assert "测试区域" in text
    assert "1000.0" in text
    assert "10000.0" in text
    assert "西边界" in text
    assert len(document.tables) == 2
    assert len(document.inline_shapes) == 5
    assert [
        [cell.text for cell in row.cells] for row in document.tables[0].rows
    ] == [
        ["边界名称", "输入", "输出", "净输入"],
        ["西边界", "40.0", "10.0", "30.0"],
        ["东边界", "10.0", "50.0", "-40.0"],
        ["南边界", "20.0", "15.0", "5.0"],
        ["北边界", "30.0", "20.0", "10.0"],
        ["合计", "100.0", "95.0", "5.0"],
    ]


def test_cloud_water_profile_rejects_missing_month_without_output(tmp_path: Path):
    profile_path = _write_profile_case(tmp_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    monthly_path = Path(profile["monthly_csv"])
    rows = list(csv.DictReader(monthly_path.open(encoding="utf-8")))
    _write_csv(monthly_path, rows[:-1])

    with pytest.raises(ValueError, match="missing months"):
        build_cloud_water_single_year_report(profile_path)

    assert not (tmp_path / "output" / "report.docx").exists()


def test_business_metrics_are_indexed_and_drive_equivalent_report(
    tmp_path: Path,
):
    compatibility_profile_path = _write_profile_case(tmp_path)
    compatibility_profile = json.loads(
        compatibility_profile_path.read_text(encoding="utf-8")
    )
    compatibility_output = build_cloud_water_single_year_report(
        compatibility_profile_path
    )

    metrics_spec_path = tmp_path / "metrics-spec.json"
    metrics_spec_path.write_text(
        json.dumps(
            {
                "metric_profile": "cloud_water_single_year",
                "task_id": "cloud-water-metrics-2025",
                "year": 2025,
                "region_name": "测试区域",
                "annual_csv": compatibility_profile["annual_csv"],
                "monthly_csv": compatibility_profile["monthly_csv"],
                "mask_nc": compatibility_profile["mask_nc"],
                "spatial_nc": compatibility_profile["spatial_nc"],
                "output_root": "metrics-run",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    report_inputs_path = build_cloud_water_business_metrics(metrics_spec_path)
    report_inputs = json.loads(
        report_inputs_path.read_text(encoding="utf-8")
    )
    assert [item["kind"] for item in report_inputs["artifacts"]] == [
        "business_metrics",
        "spatial_composite",
    ]

    metrics_path = Path(report_inputs["artifacts"][0]["path"])
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert metrics["schema_version"] == 1
    assert len(metrics["monthly"]) == 12
    assert metrics["seasons"]["spring"]["months"] == [3, 4, 5]
    assert metrics["seasons"]["spring"]["SP_mm"] == pytest.approx(12.0)
    assert metrics["boundaries"]["water_vapor"][-1] == {
        "boundary": "total",
        "input": 100.0,
        "output": 95.0,
        "net_input": 5.0,
    }

    standardized_profile = {
        key: value
        for key, value in compatibility_profile.items()
        if key
        not in {
            "report_id",
            "year",
            "region_name",
            "annual_csv",
            "monthly_csv",
            "mask_nc",
            "spatial_nc",
        }
    }
    standardized_profile["report_inputs"] = str(report_inputs_path)
    standardized_profile["output"] = "standard-output/report.docx"
    standardized_profile_path = tmp_path / "standard-profile.json"
    standardized_profile_path.write_text(
        json.dumps(standardized_profile, ensure_ascii=False),
        encoding="utf-8",
    )

    standardized_output = build_cloud_water_single_year_report(
        standardized_profile_path
    )
    compatibility_document = Document(compatibility_output)
    standardized_document = Document(standardized_output)
    assert [
        paragraph.text for paragraph in standardized_document.paragraphs
    ] == [paragraph.text for paragraph in compatibility_document.paragraphs]
    assert [
        [[cell.text for cell in row.cells] for row in table.rows]
        for table in standardized_document.tables
    ] == [
        [[cell.text for cell in row.cells] for row in table.rows]
        for table in compatibility_document.tables
    ]
    assert len(standardized_document.inline_shapes) == 5


def test_business_metrics_fail_before_artifacts_for_missing_month(
    tmp_path: Path,
):
    profile_path = _write_profile_case(tmp_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    monthly_path = Path(profile["monthly_csv"])
    rows = list(csv.DictReader(monthly_path.open(encoding="utf-8")))
    _write_csv(monthly_path, rows[:-1])
    metrics_spec_path = tmp_path / "metrics-spec.json"
    metrics_spec_path.write_text(
        json.dumps(
            {
                "metric_profile": "cloud_water_single_year",
                "task_id": "cloud-water-metrics-2025",
                "year": 2025,
                "region_name": "测试区域",
                "annual_csv": profile["annual_csv"],
                "monthly_csv": profile["monthly_csv"],
                "mask_nc": profile["mask_nc"],
                "spatial_nc": profile["spatial_nc"],
                "output_root": "metrics-run",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="missing months"):
        build_cloud_water_business_metrics(metrics_spec_path)

    assert not (tmp_path / "metrics-run").exists()


def test_business_metrics_reject_coordinate_mismatch_before_artifacts(
    tmp_path: Path,
):
    profile_path = _write_profile_case(tmp_path)
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    mask_path = Path(profile["mask_nc"])
    with xr.open_dataset(mask_path, engine="scipy") as source:
        mismatched_mask = source.load().assign_coords(lon=[99.0, 100.0, 101.0])
    mismatched_mask.to_netcdf(mask_path, engine="scipy")
    metrics_spec_path = tmp_path / "metrics-spec.json"
    metrics_spec_path.write_text(
        json.dumps(
            {
                "metric_profile": "cloud_water_single_year",
                "task_id": "cloud-water-metrics-2025",
                "year": 2025,
                "region_name": "测试区域",
                "annual_csv": profile["annual_csv"],
                "monthly_csv": profile["monthly_csv"],
                "mask_nc": profile["mask_nc"],
                "spatial_nc": profile["spatial_nc"],
                "output_root": "metrics-run",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="coordinates are incompatible"):
        build_cloud_water_business_metrics(metrics_spec_path)

    assert not (tmp_path / "metrics-run").exists()


def test_business_metrics_are_derived_directly_from_product_catalog(
    tmp_path: Path,
):
    root = tmp_path / "products"
    (root / "Y").mkdir(parents=True)
    (root / "M").mkdir()
    lat = [32.0, 31.0, 30.0]
    lon = [100.0, 101.0, 102.0]
    shape = (3, 3)
    base_values = {
        "SP": 10.0,
        "Mv0": 2.0,
        "MvT": 3.0,
        "aveMv": 4.0,
        "Mh0": 5.0,
        "MhT": 6.0,
        "aveMh": 6.0,
        "MC": 7.0,
        "ME": 8.0,
        "GMv": 100.0,
        "GMh": 20.0,
        "CWR": 10.0,
        "CEv": 25.0,
        "PEh": 50.0,
        "dxy": 100.0,
    }
    for component, incoming, outgoing in (
        ("qv", 1.0, 0.5),
        ("qc", 0.2, 0.1),
    ):
        for side in ("W", "E", "N", "S"):
            base_values[f"{component}_QDataIn_{side}Temp"] = incoming
            base_values[f"{component}_QDataOut_{side}Temp"] = outgoing
    dataset = xr.Dataset(
        {
            name: (("latitude", "longitude"), np.full(shape, value))
            for name, value in base_values.items()
        },
        coords={"latitude": lat, "longitude": lon},
    )
    column_gradient = np.tile([1.0, 10.0, 100.0], (3, 1))
    row_gradient = np.tile([[2.0], [20.0], [200.0]], (1, 3))
    dataset["qv_QDataIn_WTemp"] = (
        ("latitude", "longitude"),
        column_gradient,
    )
    dataset["qv_QDataIn_ETemp"] = (
        ("latitude", "longitude"),
        column_gradient,
    )
    dataset["qv_QDataIn_NTemp"] = (
        ("latitude", "longitude"),
        row_gradient,
    )
    dataset["qv_QDataIn_STemp"] = (
        ("latitude", "longitude"),
        row_gradient,
    )
    dataset.to_netcdf(
        root / "Y" / "ResultGrid_Y_2025-01-01-00_2026-01-01-00.nc",
        engine="scipy",
    )
    for month in range(1, 13):
        dataset.to_netcdf(
            root
            / "M"
            / (
                f"ResultGrid_M_2025-{month:02d}-01-00_"
                f"2025-{month % 12 + 1:02d}-01-00.nc"
            ),
            engine="scipy",
        )
    shp_path = tmp_path / "direct-region.shp"
    with shapefile.Writer(str(shp_path)) as writer:
        writer.field("id", "N")
        writer.poly(
            [
                [
                    (99.5, 29.5),
                    (99.5, 32.5),
                    (102.5, 32.5),
                    (102.5, 29.5),
                    (99.5, 29.5),
                ]
            ]
        )
        writer.record(1)
    spec_path = tmp_path / "direct-metrics.json"
    spec_path.write_text(
        json.dumps(
            {
                "metric_profile": "cloud_water_single_year",
                "task_id": "direct-products-2025",
                "year": 2025,
                "region_name": "直接产品测试区",
                "product_source": {
                    "root": str(root),
                    "engine": "scipy",
                },
                "region_spec": {
                    "kind": "shp",
                    "payload": {
                        "path": str(shp_path),
                    },
                },
                "output_root": "direct-run",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    report_inputs_path = build_cloud_water_business_metrics(spec_path)
    report_inputs = json.loads(
        report_inputs_path.read_text(encoding="utf-8")
    )
    metrics = json.loads(
        Path(report_inputs["artifacts"][0]["path"]).read_text(encoding="utf-8")
    )
    assert metrics["input_mode"] == "product_catalog"
    assert metrics["source"]["annual_product_count"] == 1
    assert metrics["source"]["monthly_product_count"] == 12
    assert metrics["monthly"][0]["GMv_mm"] == pytest.approx(96.0 / 900.0)
    assert metrics["monthly"][0]["GMh_mm"] == pytest.approx(110.4 / 900.0)
    assert metrics["monthly"][0]["MC_mm"] == pytest.approx(63.0 / 900.0)
    assert metrics["monthly"][0]["CEv"] == pytest.approx(65.625)
    assert metrics["monthly"][0]["PEh"] == pytest.approx(81.522)
    assert metrics["monthly"][0]["RCh"] == pytest.approx(446.4)
    assert metrics["annual"]["values"]["dxy"] == 900.0
    assert metrics["annual"]["values"]["GMv"] == pytest.approx(96.0)
    assert metrics["annual"]["values"]["GMh"] == pytest.approx(110.4)
    assert metrics["annual"]["values"]["CWR"] == pytest.approx(20.4)
    assert metrics["boundaries"]["water_vapor"][-1] == {
        "boundary": "total",
        "input": 909.0 / 1e11,
        "output": 6.0 / 1e11,
        "net_input": 903.0 / 1e11,
    }
    spatial_path = Path(report_inputs["artifacts"][1]["path"])
    with xr.open_dataset(spatial_path, engine="scipy") as spatial:
        assert np.allclose(spatial["pic3_a"], 1.0)
        assert np.allclose(spatial["pic3_d"], 0.2)
        assert np.allclose(spatial["pic4_a"], 0.3)
        assert np.allclose(spatial["pic5_d"], 0.3)
        assert bool(spatial["ind_area_bool"].all())
    image_artifacts = [
        item
        for item in report_inputs["artifacts"]
        if item["kind"] == "profile_image"
    ]
    assert [item["name"] for item in image_artifacts] == IMAGE_SLOTS
    for artifact in image_artifacts:
        image = plt.imread(artifact["path"])
        assert image.shape[0] > 100
        assert image.shape[1] > 100

    report_case = tmp_path / "report-case"
    report_case.mkdir()
    compatibility_profile_path = _write_profile_case(report_case)
    compatibility_profile = json.loads(
        compatibility_profile_path.read_text(encoding="utf-8")
    )
    direct_profile_path = report_case / "direct-profile.json"
    direct_profile_path.write_text(
        json.dumps(
            {
                "profile": "cloud_water_single_year",
                "report_inputs": str(report_inputs_path),
                "template": compatibility_profile["template"],
                "output": "direct-report.docx",
                "image_width_inches": 3.0,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    direct_report = build_cloud_water_single_year_report(direct_profile_path)
    assert len(Document(direct_report).inline_shapes) == 5


def test_direct_business_metrics_fail_before_artifacts_without_products(
    tmp_path: Path,
):
    product_root = tmp_path / "empty-products"
    product_root.mkdir()
    mask_path = tmp_path / "mask.nc"
    xr.Dataset(
        {"ind_area_bool": (("lat", "lon"), [[True]])},
        coords={"lat": [30.0], "lon": [100.0]},
    ).to_netcdf(mask_path, engine="scipy")
    spec_path = tmp_path / "missing-products.json"
    spec_path.write_text(
        json.dumps(
            {
                "metric_profile": "cloud_water_single_year",
                "task_id": "missing-products",
                "year": 2025,
                "region_name": "测试区域",
                "product_source": {
                    "root": str(product_root),
                    "engine": "scipy",
                },
                "region_spec": {
                    "kind": "existing_mask",
                    "payload": {"path": str(mask_path)},
                },
                "output_root": "missing-run",
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="Expected one annual product"):
        build_cloud_water_business_metrics(spec_path)

    assert not (tmp_path / "missing-run").exists()


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
