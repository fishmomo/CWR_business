import csv
import json
from pathlib import Path

from docx import Document
import matplotlib.pyplot as plt
import numpy as np
import pytest
import xarray as xr

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


def _write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
