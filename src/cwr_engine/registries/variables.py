def build_variable_registry() -> dict:
    return {
        "temp": {
            "display_name": "Temperature",
            "unit": "degC",
            "supported_scales": ["day", "month", "year"],
            "default_operator": "mean",
            "default_plot": "timeseries",
            "source_key": "temp",
        }
    }
