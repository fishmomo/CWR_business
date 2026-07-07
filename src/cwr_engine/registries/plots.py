def build_plot_registry() -> dict:
    return {
        "timeseries": {
            "required_fields": ["x", "y"],
            "output_kind": "png",
        },
        "distribution": {
            "required_fields": ["grid"],
            "output_kind": "png",
        },
        "bar_compare": {
            "required_fields": ["labels", "values"],
            "output_kind": "png",
        },
    }
