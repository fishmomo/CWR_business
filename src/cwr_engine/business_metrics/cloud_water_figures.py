from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MatplotlibPath
from matplotlib.ticker import FuncFormatter, MaxNLocator
import numpy as np
import xarray as xr

from cwr_engine.steps.mask import load_shp_geometry


IMAGE_SLOTS = [f"target_image{index}" for index in range(1, 6)]
MAP_COLORMAP = "YlGnBu"


def render_cloud_water_figures(
    metrics: dict[str, Any],
    spatial: xr.Dataset,
    region_spec: dict[str, Any],
    targets: dict[str, Path],
) -> None:
    if set(targets) != set(IMAGE_SLOTS):
        raise ValueError("Cloud-water figure targets must contain five images")
    mask = spatial["ind_area_bool"].values.astype(bool)
    if not mask.any():
        raise ValueError("Cloud-water figure mask contains no grid cells")
    geometry = _region_geometry(region_spec)
    _render_region_preview(
        spatial,
        mask,
        geometry,
        targets["target_image1"],
    )
    _render_monthly_sequence(metrics, targets["target_image2"])
    _render_annual_maps(spatial, mask, geometry, targets["target_image3"])
    _render_season_maps(
        spatial,
        mask,
        geometry,
        [f"pic4_{suffix}" for suffix in "abcd"],
        "mm",
        targets["target_image4"],
        zero_based=True,
    )
    _render_season_maps(
        spatial,
        mask,
        geometry,
        [f"pic5_{suffix}" for suffix in "abcd"],
        "mm",
        targets["target_image5"],
        zero_based=False,
    )


def _render_region_preview(
    spatial: xr.Dataset,
    mask: np.ndarray,
    geometry,
    target: Path,
) -> None:
    lon = spatial["lon"].values
    lat = spatial["lat"].values
    fig, ax = plt.subplots(figsize=(6.4, 3.2))
    try:
        selected_lat, selected_lon = np.where(mask)
        ax.scatter(
            lon[selected_lon],
            lat[selected_lat],
            s=18,
            color="#d62728",
            label="Grid centers",
            zorder=3,
        )
        _plot_mask_boundary(ax, lon, lat, mask, color="#1756d3", linewidth=1.8)
        if geometry is not None:
            _plot_geometry(
                ax,
                geometry,
                color="#188f38",
                linewidth=1.4,
                label="Region boundary",
            )
        ax.plot(
            [],
            [],
            color="#1756d3",
            linewidth=1.8,
            label="Mask boundary",
        )
        _configure_map_axis(
            ax,
            lon,
            lat,
            mask,
            geometry,
            padding=(0.12, 0.16),
            tick_labelsize=15,
        )
        ax.grid(color="#c8c8c8", linewidth=0.7, alpha=0.8)
        ax.set_title("Cloud-Water Evaluation Region", fontsize=22, pad=12)
        ax.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, -0.22),
            borderaxespad=0,
            columnspacing=1.1,
            frameon=False,
            handlelength=1.8,
            fontsize=22,
            ncol=2,
        )
        _save(fig, target, dpi=180)
    finally:
        plt.close(fig)


def _render_monthly_sequence(metrics: dict[str, Any], target: Path) -> None:
    monthly = metrics.get("monthly", [])
    if len(monthly) != 12:
        raise ValueError("Monthly sequence figure requires twelve months")
    required = {
        "month",
        "GMv_mm",
        "CEv",
        "GMh_mm",
        "MC_mm",
        "CWR_mm",
        "SP_mm",
        "RCh",
        "PEh",
    }
    for row in monthly:
        missing = sorted(required - set(row))
        if missing:
            raise ValueError(
                f"Monthly sequence figure is missing metric {missing[0]}"
            )
        values = np.asarray([row[key] for key in required - {"month"}])
        if not np.all(np.isfinite(values.astype(float))):
            raise ValueError("Monthly sequence figure contains non-finite data")

    panels = [
        ("GMv_mm", "CEv", "GMv (mm)", "CEv (%)"),
        ("GMh_mm", "MC_mm", "GMh (mm)", "Cvh (mm)"),
        ("CWR_mm", "SP_mm", "CWR (mm)", "Ps (mm)"),
        ("RCh", "PEh", "RTh (hour)", "PEh (%)"),
    ]
    months = np.arange(1, 13)
    fig, axes = plt.subplots(4, 1, figsize=(7.2, 8.5), sharex=True)
    try:
        for index, (bar_key, line_key, bar_label, line_label) in enumerate(
            panels
        ):
            ax = axes[index]
            twin = ax.twinx()
            bars = [float(row[bar_key]) for row in monthly]
            line = [float(row[line_key]) for row in monthly]
            ax.bar(months, bars, width=0.52, color="#1454d8", zorder=2)
            twin.plot(
                months,
                line,
                color="#111111",
                marker="o",
                linewidth=2.4,
                markersize=6.5,
                zorder=3,
            )
            ax.set_ylabel(bar_label, color="#1454d8", fontsize=16)
            twin.set_ylabel(line_label, color="#111111", fontsize=16)
            ax.tick_params(
                axis="y",
                colors="#1454d8",
                direction="out",
                labelsize=15,
            )
            twin.tick_params(
                axis="y",
                colors="#111111",
                direction="out",
                labelsize=15,
            )
            ax.text(
                0.015,
                0.82,
                f"({chr(ord('a') + index)})",
                transform=ax.transAxes,
                fontsize=24,
            )
            ax.grid(axis="y", color="#d8d8d8", linewidth=0.6, alpha=0.7)
            ax.margins(x=0.04)
        axes[-1].set_xticks(months)
        axes[-1].tick_params(axis="x", direction="out", labelsize=15)
        plt.setp(
            axes[-1].get_xticklabels(),
            ha="center",
            rotation=0,
        )
        axes[-1].set_xlabel("Month", fontsize=16)
        fig.subplots_adjust(hspace=0.22, left=0.17, right=0.83)
        _save(fig, target, dpi=180)
    finally:
        plt.close(fig)


def _render_annual_maps(
    spatial: xr.Dataset,
    mask: np.ndarray,
    geometry,
    target: Path,
    *,
    variables: list[str] | None = None,
) -> None:
    field_names = variables or [f"pic3_{suffix}" for suffix in "abcdef"]
    if len(field_names) != 6:
        raise ValueError("Annual figure requires six spatial fields")
    panels = list(zip(field_names, ["mm", "%", "mm", "mm", "mm", "%"]))
    fields = [_resolve_spatial_field(spatial, name) for name, _ in panels]
    fig, axes = plt.subplots(3, 2, figsize=(11.0, 7.4))
    try:
        for index, ((_, unit), field) in enumerate(zip(panels, fields)):
            row, column = divmod(index, 2)
            _draw_map_panel(
                fig,
                axes.flat[index],
                spatial,
                mask,
                geometry,
                field,
                f"({chr(ord('a') + index)})",
                unit,
                show_x_labels=row == 2,
                show_y_labels=column == 0,
            )
        fig.subplots_adjust(hspace=0.48, wspace=0.62)
        _save(fig, target, dpi=180)
    finally:
        plt.close(fig)


def _render_season_maps(
    spatial: xr.Dataset,
    mask: np.ndarray,
    geometry,
    variables: list[str | xr.DataArray],
    colorbar_label: str,
    target: Path,
    *,
    zero_based: bool,
) -> None:
    fields = [_resolve_spatial_field(spatial, variable) for variable in variables]
    values = np.concatenate(
        [field.values[mask].astype(float) for field in fields]
    )
    levels = _tidy_colorbar_levels(values, zero_based=zero_based)
    fig = plt.figure(figsize=(10.8, 5.8))
    grid = fig.add_gridspec(
        2,
        3,
        width_ratios=[1, 1, 0.045],
        hspace=0.25,
        wspace=0.18,
    )
    axes = [
        fig.add_subplot(grid[row, column])
        for row in range(2)
        for column in range(2)
    ]
    colorbar_axis = fig.add_subplot(grid[:, 2])
    try:
        contour = None
        for index, field in enumerate(fields):
            row, column = divmod(index, 2)
            contour = _draw_map_panel(
                fig,
                axes[index],
                spatial,
                mask,
                geometry,
                field,
                f"({chr(ord('a') + index)})",
                None,
                levels=levels,
                show_x_labels=row == 1,
                show_y_labels=column == 0,
            )
        if contour is None:
            raise ValueError("Seasonal figure produced no contour")
        colorbar = fig.colorbar(
            contour,
            cax=colorbar_axis,
            ticks=_colorbar_ticks(
                levels,
                max_ticks=6,
                equal_spacing=True,
            ),
            format=FuncFormatter(_tidy_colorbar_label),
        )
        colorbar.update_ticks()
        _style_colorbar(colorbar, colorbar_label)
        _save(fig, target, dpi=180)
    finally:
        plt.close(fig)


def _draw_map_panel(
    fig,
    ax,
    spatial: xr.Dataset,
    mask: np.ndarray,
    geometry,
    variable: str | xr.DataArray,
    panel_label: str,
    colorbar_label: str | None,
    *,
    levels: np.ndarray | None = None,
    show_x_labels: bool = True,
    show_y_labels: bool = True,
):
    lon = spatial["lon"].values
    lat = spatial["lat"].values
    field = _resolve_spatial_field(spatial, variable)
    field_name = field.name or "unnamed"
    source_data = field.values.astype(float)
    valid = source_data[mask]
    if not np.all(np.isfinite(valid)):
        raise ValueError(f"Spatial figure field {field_name} is non-finite")
    data = (
        source_data
        if geometry is not None
        else np.where(mask, source_data, np.nan)
    )
    panel_levels = (
        levels
        if levels is not None
        else _tidy_colorbar_levels(valid)
    )
    contour = ax.contourf(
        lon,
        lat,
        data,
        levels=panel_levels,
        cmap=MAP_COLORMAP,
    )
    if geometry is not None:
        _clip_contour_to_geometry(ax, contour, geometry)
        _plot_geometry(ax, geometry, color="#4d4d4d", linewidth=0.8)
    else:
        _plot_mask_boundary(
            ax,
            lon,
            lat,
            mask,
            color="#4d4d4d",
            linewidth=0.8,
        )
    _configure_map_axis(
        ax,
        lon,
        lat,
        mask,
        geometry,
        padding=(0.035, 0.07),
        tick_labelsize=15,
        show_x_labels=show_x_labels,
        show_y_labels=show_y_labels,
    )
    ax.text(
        0.02,
        0.95,
        panel_label,
        transform=ax.transAxes,
        fontsize=23,
        ha="left",
        va="top",
        zorder=6,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.72},
    )
    if colorbar_label is not None:
        colorbar = fig.colorbar(
            contour,
            ax=ax,
            fraction=0.055,
            pad=0.035,
            ticks=_colorbar_ticks(panel_levels, max_ticks=3),
            format=FuncFormatter(_tidy_colorbar_label),
        )
        colorbar.update_ticks()
        _style_colorbar(colorbar, colorbar_label)
    return contour


def _resolve_spatial_field(
    spatial: xr.Dataset,
    variable: str | xr.DataArray,
) -> xr.DataArray:
    if isinstance(variable, xr.DataArray):
        field = variable
    else:
        if variable not in spatial:
            raise ValueError(f"Figure is missing spatial field {variable}")
        field = spatial[variable]
    if field.dims != ("lat", "lon"):
        raise ValueError(
            f"Spatial figure field {field.name or 'unnamed'} must use lat/lon"
        )
    return field


def _colorbar_ticks(
    levels: np.ndarray,
    *,
    max_ticks: int,
    equal_spacing: bool = False,
) -> np.ndarray:
    levels = np.asarray(levels, dtype=float)
    if levels.size <= max_ticks:
        return levels
    if equal_spacing:
        stride = int(np.ceil(levels.size / max_ticks))
        return levels[::stride]
    indices = np.rint(np.linspace(0, levels.size - 1, max_ticks)).astype(int)
    return levels[np.unique(indices)]


def _style_colorbar(colorbar, label: str) -> None:
    colorbar.ax.tick_params(labelsize=23)
    colorbar.ax.set_title(label, fontsize=23, pad=12)


def _levels(values: np.ndarray, *, zero_based: bool = False) -> np.ndarray:
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        raise ValueError("Figure field has no finite values")
    lower = 0.0 if zero_based else float(finite.min())
    upper = float(finite.max())
    if np.isclose(lower, upper):
        spread = max(abs(upper) * 0.05, 1.0)
        lower -= spread
        upper += spread
    return np.linspace(lower, upper, 9)


def _tidy_colorbar_levels(
    values: np.ndarray,
    *,
    zero_based: bool = False,
) -> np.ndarray:
    levels = _levels(values, zero_based=zero_based)
    lower = float(levels[0])
    upper = float(levels[-1])
    raw_step = (upper - lower) / 8
    step = _nice_step(raw_step)
    if np.max(np.abs(levels)) >= 1000:
        step = max(100.0, step)
    tidy_lower = np.floor(lower / step) * step
    tidy_upper = np.ceil(upper / step) * step
    return np.arange(
        tidy_lower,
        tidy_upper + step * 0.5,
        step,
        dtype=float,
    )


def _nice_step(value: float) -> float:
    magnitude = 10 ** np.floor(np.log10(value))
    fraction = value / magnitude
    for candidate in (1.0, 2.0, 5.0, 10.0):
        if fraction <= candidate:
            return candidate * magnitude
    return 10.0 * magnitude


def _tidy_colorbar_label(value: float, _: int | None = None) -> str:
    if abs(value) < 1000:
        return f"{value:.1f}"
    rounded = round(value / 100) * 100
    return f"{rounded:.0f}"


def _region_geometry(region_spec: dict[str, Any]):
    if region_spec.get("kind") != "shp":
        return None
    payload = region_spec["payload"]
    return load_shp_geometry(Path(payload["path"]), payload)


def _plot_geometry(
    ax,
    geometry,
    *,
    color: str,
    linewidth: float,
    label: str | None = None,
) -> None:
    geometries = (
        list(geometry.geoms)
        if hasattr(geometry, "geoms")
        else [geometry]
    )
    first = True
    for item in geometries:
        if not hasattr(item, "exterior"):
            continue
        x, y = item.exterior.xy
        ax.plot(
            x,
            y,
            color=color,
            linewidth=linewidth,
            label=label if first else None,
            zorder=4,
        )
        first = False


def _clip_contour_to_geometry(ax, contour, geometry) -> None:
    vertices: list[tuple[float, float]] = []
    codes: list[int] = []
    geometries = (
        list(geometry.geoms)
        if hasattr(geometry, "geoms")
        else [geometry]
    )
    for item in geometries:
        if not hasattr(item, "exterior"):
            continue
        for ring in [item.exterior, *item.interiors]:
            coordinates = list(ring.coords)
            if len(coordinates) < 3:
                continue
            vertices.extend((float(x), float(y)) for x, y in coordinates)
            codes.extend(
                [
                    MatplotlibPath.MOVETO,
                    *([MatplotlibPath.LINETO] * (len(coordinates) - 2)),
                    MatplotlibPath.CLOSEPOLY,
                ]
            )
    if not vertices:
        raise ValueError("Region geometry has no polygon rings for clipping")
    patch = PathPatch(
        MatplotlibPath(vertices, codes),
        transform=ax.transData,
        facecolor="none",
        edgecolor="none",
    )
    if hasattr(contour, "set_clip_path"):
        contour.set_clip_path(patch)
        return
    for collection in contour.collections:
        collection.set_clip_path(patch)


def _plot_mask_boundary(
    ax,
    lon: np.ndarray,
    lat: np.ndarray,
    mask: np.ndarray,
    *,
    color: str,
    linewidth: float,
) -> None:
    lon_edges = _coordinate_edges(lon)
    lat_edges = _coordinate_edges(lat)
    for row, column in zip(*np.where(mask)):
        neighbors = [
            (row - 1, column, "north"),
            (row + 1, column, "south"),
            (row, column - 1, "west"),
            (row, column + 1, "east"),
        ]
        for neighbor_row, neighbor_column, side in neighbors:
            outside = (
                neighbor_row < 0
                or neighbor_row >= mask.shape[0]
                or neighbor_column < 0
                or neighbor_column >= mask.shape[1]
                or not mask[neighbor_row, neighbor_column]
            )
            if not outside:
                continue
            x0, x1 = lon_edges[column], lon_edges[column + 1]
            y0, y1 = lat_edges[row], lat_edges[row + 1]
            if side == "north":
                ax.plot([x0, x1], [y0, y0], color=color, linewidth=linewidth)
            elif side == "south":
                ax.plot([x0, x1], [y1, y1], color=color, linewidth=linewidth)
            elif side == "west":
                ax.plot([x0, x0], [y0, y1], color=color, linewidth=linewidth)
            else:
                ax.plot([x1, x1], [y0, y1], color=color, linewidth=linewidth)


def _coordinate_edges(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    if values.size == 1:
        return np.array([values[0] - 0.5, values[0] + 0.5])
    midpoints = (values[:-1] + values[1:]) / 2
    return np.concatenate(
        (
            [values[0] - (midpoints[0] - values[0])],
            midpoints,
            [values[-1] + (values[-1] - midpoints[-1])],
        )
    )


def _configure_map_axis(
    ax,
    lon: np.ndarray,
    lat: np.ndarray,
    mask: np.ndarray,
    geometry,
    *,
    padding: tuple[float, float],
    tick_labelsize: float = 8,
    show_x_labels: bool = True,
    show_y_labels: bool = True,
) -> None:
    lon_edges = _coordinate_edges(lon)
    lat_edges = _coordinate_edges(lat)
    selected_rows, selected_columns = np.where(mask)
    lon_bounds = (
        lon_edges[selected_columns.min()],
        lon_edges[selected_columns.max() + 1],
    )
    lat_bounds = (
        lat_edges[selected_rows.min()],
        lat_edges[selected_rows.max() + 1],
    )
    if geometry is not None:
        min_x, min_y, max_x, max_y = geometry.bounds
        lon_bounds = (min(min(lon_bounds), min_x), max(max(lon_bounds), max_x))
        lat_bounds = (min(min(lat_bounds), min_y), max(max(lat_bounds), max_y))
    lon_span = max(lon_bounds) - min(lon_bounds)
    lat_span = max(lat_bounds) - min(lat_bounds)
    lon_pad = max(lon_span * padding[0], 0.25)
    lat_pad = max(lat_span * padding[1], 0.25)
    ax.set_xlim(
        float(min(lon_bounds) - lon_pad),
        float(max(lon_bounds) + lon_pad),
    )
    ax.set_ylim(
        float(min(lat_bounds) - lat_pad),
        float(max(lat_bounds) + lat_pad),
    )
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}°E"))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _: f"{value:g}°N"))
    ax.xaxis.set_major_locator(
        MaxNLocator(nbins=2, steps=[1, 2, 2.5, 5, 10])
    )
    ax.yaxis.set_major_locator(
        MaxNLocator(nbins=3, steps=[1, 2, 2.5, 5, 10])
    )
    ax.tick_params(
        labelsize=tick_labelsize,
        direction="out",
        labelbottom=show_x_labels,
        labelleft=show_y_labels,
    )


def _save(fig, target: Path, *, dpi: int) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(target, dpi=dpi, bbox_inches="tight", facecolor="white")
