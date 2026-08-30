import json
from pathlib import Path

import pytest

from cwr_engine.cli import main
from cwr_engine.registries.thematic_products import (
    THEMATIC_PRODUCTS,
    ThematicProduct,
    ThematicProductRegistry,
    build_thematic_product_registry,
)
from cwr_engine.workflows.cloud_water_multi_year_request import (
    build_cloud_water_multi_year_request_set,
    load_multi_year_request_set,
)
from cwr_engine.workflows.cloud_water_single_year_request import (
    build_cloud_water_single_year_request_set,
    load_request_set,
)
from cwr_engine.workflows.daily_precipitation_request import (
    build_daily_precipitation_request_set,
    load_daily_precipitation_request_set,
)


def test_builtin_registry_declares_all_thematic_products() -> None:
    assert THEMATIC_PRODUCTS.names() == (
        "cloud_water_multi_year",
        "cloud_water_single_year",
        "daily_precipitation_analysis",
    )

    single_year = THEMATIC_PRODUCTS.resolve("cloud_water_single_year")
    assert single_year.loader is load_request_set
    assert single_year.builder is build_cloud_water_single_year_request_set
    assert single_year.protocol_name == "cloud-water-single-year-request-set"
    assert single_year.protocol_version == 1
    assert {"annual", "monthly", "docx_report"} <= single_year.capabilities

    multi_year = THEMATIC_PRODUCTS.resolve("cloud_water_multi_year")
    assert multi_year.loader is load_multi_year_request_set
    assert multi_year.builder is build_cloud_water_multi_year_request_set
    assert "trend_significance" in multi_year.capabilities

    precipitation = THEMATIC_PRODUCTS.resolve("daily_precipitation_analysis")
    assert precipitation.loader is load_daily_precipitation_request_set
    assert precipitation.builder is build_daily_precipitation_request_set
    assert {"daily", "regional_csv", "grid_netcdf"} <= precipitation.capabilities


def test_registry_rejects_duplicate_product_names() -> None:
    product = ThematicProduct(
        name="example",
        protocol_name="example-request-set",
        protocol_version=1,
        loader=lambda path: path,
        builder=lambda path: path,
        capabilities=frozenset(),
    )

    with pytest.raises(ValueError, match="Duplicate thematic product: example"):
        ThematicProductRegistry([product, product])


def test_registry_rejects_unknown_product_name() -> None:
    registry = build_thematic_product_registry()

    with pytest.raises(
        LookupError,
        match="Unsupported request set: missing_product",
    ):
        registry.resolve("missing_product")


def test_cli_reports_unknown_thematic_product(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    request_path = tmp_path / "unknown-product.json"
    request_path.write_text(
        json.dumps({"request_set": "missing_product"}),
        encoding="utf-8",
    )

    with pytest.raises(SystemExit) as exc_info:
        main(["--request", str(request_path)])

    assert exc_info.value.code == 2
    assert "Unsupported request set: missing_product" in capsys.readouterr().err


def test_cli_rejects_retired_workflow_spec(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(
            [
                "--task",
                "placeholder-task.json",
                "--workflow-spec",
                "retired-workflow.json",
            ]
        )

    assert exc_info.value.code == 2
    assert "unrecognized arguments: --workflow-spec" in capsys.readouterr().err


def test_registry_instances_do_not_share_mutable_state() -> None:
    first = build_thematic_product_registry()
    second = build_thematic_product_registry()
    first.register(
        ThematicProduct(
            name="example",
            protocol_name="example-request-set",
            protocol_version=1,
            loader=lambda path: Path(path),
            builder=lambda path: Path(path),
            capabilities=frozenset(),
        )
    )

    assert "example" in first.names()
    assert "example" not in second.names()
