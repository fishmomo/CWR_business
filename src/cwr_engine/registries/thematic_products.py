from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

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


ProductLoader = Callable[[Path], Any]
ProductBuilder = Callable[[Path], Path]


@dataclass(frozen=True)
class ThematicProduct:
    name: str
    protocol_name: str
    protocol_version: int
    loader: ProductLoader
    builder: ProductBuilder
    capabilities: frozenset[str]


class ThematicProductRegistry:
    def __init__(self, products: Iterable[ThematicProduct] = ()) -> None:
        self._products: dict[str, ThematicProduct] = {}
        for product in products:
            self.register(product)

    def register(self, product: ThematicProduct) -> None:
        if product.name in self._products:
            raise ValueError(f"Duplicate thematic product: {product.name}")
        self._products[product.name] = product

    def resolve(self, name: str) -> ThematicProduct:
        try:
            return self._products[name]
        except KeyError as exc:
            raise LookupError(f"Unsupported request set: {name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._products))


def build_thematic_product_registry() -> ThematicProductRegistry:
    return ThematicProductRegistry(
        [
            ThematicProduct(
                name="cloud_water_single_year",
                protocol_name="cloud-water-single-year-request-set",
                protocol_version=1,
                loader=load_request_set,
                builder=build_cloud_water_single_year_request_set,
                capabilities=frozenset(
                    {"annual", "monthly", "figures", "docx_report"}
                ),
            ),
            ThematicProduct(
                name="cloud_water_multi_year",
                protocol_name="cloud-water-multi-year-request-set",
                protocol_version=1,
                loader=load_multi_year_request_set,
                builder=build_cloud_water_multi_year_request_set,
                capabilities=frozenset(
                    {
                        "annual",
                        "monthly",
                        "trend_significance",
                        "figures",
                        "docx_report",
                    }
                ),
            ),
            ThematicProduct(
                name="daily_precipitation_analysis",
                protocol_name="daily-precipitation-request-set",
                protocol_version=1,
                loader=load_daily_precipitation_request_set,
                builder=build_daily_precipitation_request_set,
                capabilities=frozenset(
                    {"daily", "regional_csv", "grid_netcdf", "figures"}
                ),
            ),
        ]
    )


THEMATIC_PRODUCTS = build_thematic_product_registry()
