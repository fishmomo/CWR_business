from cwr_engine.plotting.renderers import (
    render_bar_compare,
    render_distribution,
    render_timeseries,
)


def build_plot_registry() -> dict:
    return {
        "timeseries": {
            "request_kind": "figure_timeseries",
            "renderer": render_timeseries,
            "required_fields": ["x", "y"],
            "required_steps": ["transform"],
            "output_kind": "png",
            "allowed_params": {
                "title",
                "figsize",
                "dpi",
                "ylabel",
                "line_color",
            },
            "title_fields": {"variable"},
            "defaults": {
                "title": "{variable} Time Series",
                "figsize": [6.4, 4.8],
                "dpi": 120,
                "ylabel": None,
                "line_color": "#246a73",
            },
        },
        "distribution": {
            "request_kind": "figure_distribution",
            "renderer": render_distribution,
            "required_fields": ["grid"],
            "required_steps": ["transform"],
            "output_kind": "png",
            "allowed_params": {
                "title",
                "figsize",
                "dpi",
                "cmap",
                "vmin",
                "vmax",
                "colorbar_label",
            },
            "title_fields": {"label", "variable", "operator"},
            "defaults": {
                "title": "{label} {variable} {operator}",
                "figsize": [7.2, 5.2],
                "dpi": 120,
                "cmap": "YlGnBu",
                "vmin": None,
                "vmax": None,
                "colorbar_label": None,
            },
        },
        "bar_compare": {
            "request_kind": "figure_bar_compare",
            "renderer": render_bar_compare,
            "required_fields": ["labels", "values"],
            "required_steps": ["transform", "stat"],
            "output_kind": "png",
            "allowed_params": {
                "title",
                "figsize",
                "dpi",
                "ylabel",
                "bar_color",
            },
            "title_fields": {"variable", "operator"},
            "defaults": {
                "title": "{variable} {operator}",
                "figsize": [7.2, 4.8],
                "dpi": 120,
                "ylabel": None,
                "bar_color": "#c65d2e",
            },
        },
    }
