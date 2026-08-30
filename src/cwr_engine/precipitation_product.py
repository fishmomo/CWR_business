from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from mpl_toolkits.axes_grid1 import make_axes_locatable
import numpy as np
import xarray as xr

from cwr_engine.precipitation import (
    DEFAULT_PRECIPITATION_CLASSES,
    classify_precipitation_cwr,
)


@dataclass(frozen=True)
class DailyPrecipitationProduct:
    rows: list[dict[str, float | str]]
    classes: xr.Dataset


def derive_daily_precipitation_product(
    dataset: xr.Dataset,
    region_mask: xr.DataArray,
) -> DailyPrecipitationProduct:
    required = {"SP", "GMh", "CWR", "dxy"}
    missing = sorted(required - set(dataset.data_vars))
    if missing:
        raise ValueError(f"Daily precipitation source is missing {missing[0]}")
    dataset, region_mask = xr.align(dataset, region_mask, join="exact")
    mask = region_mask.astype(bool)
    if not bool(mask.any().item()):
        raise ValueError("The region mask contains no grid cells")

    spatial_dims = ("lat", "lon")
    area = dataset["dxy"].where(mask).sum(spatial_dims, skipna=True)
    sp = dataset["SP"].where(mask).sum(spatial_dims, skipna=True)
    gmh = dataset["GMh"].where(mask).sum(spatial_dims, skipna=True)
    if bool((area <= 0).any().item()):
        raise ValueError("Regional grid area must be positive for every day")

    precipitation = sp / area
    efficiency = xr.where(gmh != 0, sp / gmh * 100.0, np.nan)
    rows = []
    for index, value in enumerate(dataset["time"].values):
        rows.append(
            {
                "date": np.datetime_as_string(value, unit="D"),
                "precipitation_mm": float(precipitation.isel(time=index).item()),
                "precipitation_efficiency_pct": float(
                    efficiency.isel(time=index).item()
                ),
                "sp_kg": float(sp.isel(time=index).item()),
                "gmh_kg": float(gmh.isel(time=index).item()),
                "grid_area_m2": float(area.isel(time=index).item()),
            }
        )

    precipitation_grid = dataset["SP"] / dataset["dxy"]
    cwr_grid = dataset["CWR"] / dataset["dxy"]
    classes = classify_precipitation_cwr(precipitation_grid, cwr_grid, mask)
    return DailyPrecipitationProduct(rows=rows, classes=classes)


def write_daily_precipitation_product(
    product: DailyPrecipitationProduct,
    output_root: Path,
    output_prefix: str,
) -> list[dict[str, str]]:
    daily_dir = output_root / "daily_precipitation"
    class_dir = output_root / "precipitation_classes"
    daily_dir.mkdir(parents=True, exist_ok=True)
    class_dir.mkdir(parents=True, exist_ok=True)

    daily_csv = daily_dir / f"{output_prefix}_daily_precipitation_pe.csv"
    daily_figure = daily_dir / f"{output_prefix}_daily_precipitation_pe.png"
    class_nc = class_dir / f"{output_prefix}_precipitation_class_distribution.nc"
    class_figure = class_dir / f"{output_prefix}_precipitation_class_distribution.png"
    class_summary = class_dir / f"{output_prefix}_precipitation_class_summary.csv"
    class_dual = class_dir / f"{output_prefix}_precipitation_classes_dual_axis.png"

    _write_daily_rows(product.rows, daily_csv)
    _plot_daily_rows(product.rows, daily_figure)
    product.classes.to_netcdf(class_nc, engine="h5netcdf")
    _plot_class_distributions(product.classes, class_figure)
    _write_class_summary(product.classes, class_summary)
    _plot_class_summary(product.classes, class_dual)

    return [
        {"kind": "daily_precipitation_table", "name": "daily_precipitation", "path": str(daily_csv)},
        {"kind": "daily_precipitation_figure", "name": "daily_precipitation", "path": str(daily_figure)},
        {"kind": "precipitation_class_grid", "name": "precipitation_classes", "path": str(class_nc)},
        {"kind": "precipitation_class_figure", "name": "precipitation_classes", "path": str(class_figure)},
        {"kind": "precipitation_class_table", "name": "precipitation_classes", "path": str(class_summary)},
        {"kind": "precipitation_class_figure", "name": "precipitation_class_summary", "path": str(class_dual)},
    ]


def _write_daily_rows(rows: list[dict[str, float | str]], path: Path) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _plot_daily_rows(rows: list[dict[str, float | str]], path: Path) -> None:
    dates = [datetime.strptime(str(row["date"]), "%Y-%m-%d") for row in rows]
    precipitation = [float(row["precipitation_mm"]) for row in rows]
    efficiency = [float(row["precipitation_efficiency_pct"]) for row in rows]
    figure, axes = plt.subplots(2, 1, sharex=True, figsize=(16, 9), dpi=180)
    axes[0].bar(dates, precipitation, width=0.8, color="#2864DC", alpha=0.85)
    axes[1].plot(dates, efficiency, color="#111111", linewidth=1.8)
    axes[0].set_ylabel("Precipitation (mm)", fontsize=16)
    axes[1].set_ylabel("PEh (%)", fontsize=16)
    axes[1].set_xlabel("Date", fontsize=16)
    for index, axis in enumerate(axes):
        axis.text(
            0.012,
            0.94,
            f"({chr(97 + index)})",
            transform=axis.transAxes,
            fontsize=16,
            va="top",
        )
        axis.tick_params(axis="both", labelsize=15)
        axis.grid(axis="y", alpha=0.22)
    axes[1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    axes[1].tick_params(axis="x", rotation=0)
    axes[1].set_xlim(dates[0], dates[-1])
    figure.tight_layout()
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)


def _plot_class_distributions(dataset: xr.Dataset, path: Path) -> None:
    classes = DEFAULT_PRECIPITATION_CLASSES
    figure, axes = plt.subplots(2, len(classes), figsize=(22, 10), dpi=180)
    first = dataset[f"{classes[0].name}_days"]
    valid_lat = first["lat"].where(first.notnull().any("lon"), drop=True)
    valid_lon = first["lon"].where(first.notnull().any("lat"), drop=True)
    x_limits = (float(valid_lon.min()) - 0.5, float(valid_lon.max()) + 0.5)
    y_limits = (float(valid_lat.min()) - 0.5, float(valid_lat.max()) + 0.5)
    for column, item in enumerate(classes):
        upper = f"{item.upper_mm:g}" if item.upper_mm is not None else r"$\infty$"
        class_label = f"({item.lower_mm:g}, {upper}] mm"
        for row, suffix, cmap, unit in (
            (0, "days", "YlGnBu", "days"),
            (1, "cwr_mm", "YlOrRd", "mm"),
        ):
            axis = axes[row, column]
            field = dataset[f"{item.name}_{suffix}"]
            image = axis.pcolormesh(
                field["lon"], field["lat"], field, shading="auto", cmap=cmap
            )
            divider = make_axes_locatable(axis)
            color_axis = divider.append_axes("right", size="4%", pad=0.18)
            colorbar = figure.colorbar(image, cax=color_axis)
            colorbar.set_label(unit, fontsize=16, labelpad=12)
            colorbar.ax.tick_params(labelsize=15)
            panel_index = row * len(classes) + column
            axis.text(0.02, 0.96, f"({chr(97 + panel_index)})", transform=axis.transAxes, fontsize=16, va="top")
            axis.text(0.98, 0.96, class_label, transform=axis.transAxes, fontsize=15, ha="right", va="top")
            axis.set_xlabel("Longitude", fontsize=16)
            if column == 0:
                axis.set_ylabel("Latitude", fontsize=16)
            axis.tick_params(axis="both", labelsize=15)
            axis.set_xlim(*x_limits)
            axis.set_ylim(*y_limits)
    figure.tight_layout()
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)


def _class_summary(dataset: xr.Dataset) -> tuple[list[str], list[float], list[float]]:
    labels = []
    mean_days = []
    mean_cwr = []
    for item in DEFAULT_PRECIPITATION_CLASSES:
        upper = f"{item.upper_mm:g}" if item.upper_mm is not None else "inf"
        labels.append(f"({item.lower_mm:g}, {upper}]")
        mean_days.append(float(dataset[f"{item.name}_days"].mean(skipna=True)))
        mean_cwr.append(float(dataset[f"{item.name}_cwr_mm"].mean(skipna=True)))
    return labels, mean_days, mean_cwr


def _write_class_summary(dataset: xr.Dataset, path: Path) -> None:
    labels, mean_days, mean_cwr = _class_summary(dataset)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "class",
                "precipitation_range_mm",
                "mean_precipitation_days",
                "mean_cumulative_cwr_mm",
            ]
        )
        for index, item in enumerate(DEFAULT_PRECIPITATION_CLASSES):
            writer.writerow(
                [item.name, labels[index], f"{mean_days[index]:.3f}", f"{mean_cwr[index]:.3f}"]
            )


def _plot_class_summary(dataset: xr.Dataset, path: Path) -> None:
    labels, mean_days, mean_cwr = _class_summary(dataset)
    labels[-1] = r"(49.9, $\infty$]"
    positions = np.arange(len(labels))
    figure, left = plt.subplots(figsize=(12, 6.5), dpi=180)
    right = left.twinx()
    left.plot(positions, mean_days, color="#2864DC", marker="o", linewidth=2.4)
    right.plot(positions, mean_cwr, color="#C82423", marker="s", linewidth=2.4)
    left.set_xticks(positions, labels)
    left.set_xlabel("Daily precipitation class (mm)", fontsize=16)
    left.set_ylabel("Mean precipitation days", color="#2864DC", fontsize=16)
    right.set_ylabel("Mean cumulative CWR (mm)", color="#C82423", fontsize=16, labelpad=12)
    left.tick_params(axis="both", labelsize=15)
    right.tick_params(axis="y", labelsize=15)
    left.set_ylim(bottom=0)
    right.set_ylim(bottom=0)
    left.grid(axis="y", alpha=0.22)
    figure.tight_layout()
    figure.savefig(path, bbox_inches="tight")
    plt.close(figure)
