def build_operator_registry() -> dict:
    return {
        "mean": {
            "input_kind": "series_or_grid",
            "output_kind": "scalar_or_grid",
            "supported_scales": ["day", "month", "year"],
        }
    }
