from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np


def derive_boundary_tables(
    annual: dict[str, str],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    from cwr_report.profiles.cloud_water_single_year import (
        _derive_boundary_tables,
    )

    return _derive_boundary_tables(annual)


def derive_scalar_text(spec, annual, months) -> dict[str, str]:
    from cwr_report.profiles.cloud_water_single_year import _derive_scalar_text

    return _derive_scalar_text(spec, annual, months)


def image_width_overrides(
    value: Any,
    slots: list[str],
) -> dict[str, float]:
    from cwr_report.profiles.cloud_water_single_year import (
        _image_width_overrides,
    )

    return _image_width_overrides(value, slots)


def seasonal_spatial_text(
    dataset,
    mask: np.ndarray,
    variables: list[str],
    prefix: str,
) -> dict[str, str]:
    from cwr_report.profiles.cloud_water_single_year import (
        _seasonal_spatial_text,
    )

    return _seasonal_spatial_text(dataset, mask, variables, prefix)


def spatial_description(dataset, variable: str, mask: np.ndarray) -> str:
    from cwr_report.profiles.cloud_water_single_year import (
        _spatial_description,
    )

    return _spatial_description(dataset, variable, mask)


def template_slots(path: Path) -> set[str]:
    from cwr_report.profiles.cloud_water_single_year import _template_slots

    return _template_slots(path)
