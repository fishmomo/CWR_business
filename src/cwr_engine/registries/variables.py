def build_variable_registry() -> dict:
    common = {
        "supported_scales": ["day", "month", "year"],
        "default_operator": "mean",
        "default_plot": "timeseries",
    }
    return {
        "temp": {
            **common,
            "display_name": "Temperature",
            "unit": "degC",
            "source_keys": ["temp"],
        },
        "precip": {
            **common,
            "display_name": "Precipitation",
            "unit": "mm",
            "source_keys": ["precip"],
        },
        "GMv": {
            **common,
            "display_name": "Vertical cloud water resource",
            "unit": None,
            "source_keys": ["GMv"],
        },
        "GMh": {
            **common,
            "display_name": "Horizontal cloud water resource",
            "unit": None,
            "source_keys": ["GMh"],
        },
        "Cvh": {
            **common,
            "display_name": "Cloud water content",
            "unit": None,
            "source_keys": ["Cvh", "MC"],
        },
        "CWR": {
            **common,
            "display_name": "Cloud water resource",
            "unit": None,
            "source_keys": ["CWR"],
        },
        "Ps": {
            **common,
            "display_name": "Precipitation",
            "unit": None,
            "source_keys": ["Ps", "SP"],
        },
        "CEv": {
            **common,
            "display_name": "Cloud water efficiency",
            "unit": "%",
            "source_keys": ["CEv"],
        },
        "PEh": {
            **common,
            "display_name": "Precipitation efficiency",
            "unit": "%",
            "source_keys": ["PEh"],
        },
        "RTh": {
            **common,
            "display_name": "Residence time",
            "unit": "hour",
            "source_keys": ["RTh"],
        },
    }


def resolve_source_key(
    variable: str,
    registry: dict,
    dataset,
    variable_map: dict[str, str] | None = None,
) -> str:
    specification = registry[variable]
    mapped_key = (variable_map or {}).get(variable)
    candidates = [mapped_key] if mapped_key else specification["source_keys"]
    for source_key in candidates:
        if source_key in dataset.data_vars:
            return source_key
    raise ValueError(
        f"No source field found for variable {variable}: expected one of {candidates}"
    )
