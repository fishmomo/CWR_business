"""Daily precipitation-class statistics for gridded CWR data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
import xarray as xr


@dataclass(frozen=True)
class PrecipitationClass:
    """A right-closed daily precipitation interval in millimetres."""

    name: str
    lower_mm: float
    upper_mm: float | None


DEFAULT_PRECIPITATION_CLASSES = (
    PrecipitationClass("light", 0.0, 9.9),
    PrecipitationClass("small", 9.9, 24.9),
    PrecipitationClass("medium", 24.9, 49.9),
    PrecipitationClass("heavy", 49.9, None),
)


def classify_precipitation_cwr(
    precipitation_mm: xr.DataArray,
    cwr_mm: xr.DataArray,
    region_mask: xr.DataArray,
    classes: Iterable[PrecipitationClass] = DEFAULT_PRECIPITATION_CLASSES,
) -> xr.Dataset:
    """Return gridded occurrence counts and cumulative CWR for each class.

    ``precipitation_mm`` and ``cwr_mm`` must contain a ``time`` dimension and
    have matching spatial dimensions.  Values outside ``region_mask`` are kept
    as NaN, so the result can be plotted directly without leaking outside the
    study area.
    """

    if "time" not in precipitation_mm.dims or "time" not in cwr_mm.dims:
        raise ValueError("precipitation_mm and cwr_mm must both have a time dimension")
    if precipitation_mm.dims != cwr_mm.dims:
        raise ValueError("precipitation_mm and cwr_mm must have identical dimensions")

    precipitation_mm, cwr_mm, region_mask = xr.align(
        precipitation_mm, cwr_mm, region_mask, join="exact"
    )
    mask = region_mask.astype(bool)
    class_list = tuple(classes)
    if not class_list:
        raise ValueError("at least one precipitation class is required")

    result: dict[str, xr.DataArray] = {}
    for precipitation_class in class_list:
        selected = precipitation_mm > precipitation_class.lower_mm
        if precipitation_class.upper_mm is not None:
            selected = selected & (precipitation_mm <= precipitation_class.upper_mm)
        selected = selected & mask
        result[f"{precipitation_class.name}_days"] = selected.sum("time").where(mask)
        result[f"{precipitation_class.name}_cwr_mm"] = cwr_mm.where(selected).sum("time").where(mask)

    dataset = xr.Dataset(result)
    dataset.attrs.update(
        {
            "description": "Daily precipitation-class occurrence and cumulative cloud water resources",
            "precipitation_classes": "; ".join(
                f"{item.name}: ({item.lower_mm}, "
                f"{item.upper_mm if item.upper_mm is not None else 'inf'}] mm"
                for item in class_list
            ),
            "sample_days": int(precipitation_mm.sizes["time"]),
        }
    )
    for name, array in dataset.data_vars.items():
        array.attrs["units"] = "days" if name.endswith("_days") else "mm"
    return dataset
