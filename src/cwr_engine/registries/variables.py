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
            "unit": "kg",
            "source_keys": ["GMv"],
        },
        "GMh": {
            **common,
            "display_name": "Horizontal cloud water resource",
            "unit": "kg",
            "source_keys": ["GMh"],
        },
        "Dv": {
            **common,
            "display_name": "Net vertical water vapor transport",
            "unit": "kg",
            "source_groups": [["Dv"], ["INv", "OTv"]],
            "source_operation": "difference",
        },
        "Dh": {
            **common,
            "display_name": "Net horizontal hydrometeor transport",
            "unit": "kg",
            "source_groups": [["Dh"], ["INh", "OTh"]],
            "source_operation": "difference",
        },
        "Cvh": {
            **common,
            "display_name": "Cloud water content",
            "unit": "kg",
            "source_keys": ["Cvh", "MC"],
        },
        "CWR": {
            **common,
            "display_name": "Cloud water resource",
            "unit": "kg",
            "source_keys": ["CWR"],
        },
        "Ps": {
            **common,
            "display_name": "Precipitation",
            "unit": "kg",
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
        "PEv": {
            **common,
            "display_name": "Vertical precipitation efficiency",
            "unit": "%",
            "source_keys": ["PEv"],
        },
        "Qvi": {
            **common,
            "display_name": "Incoming water vapor transport",
            "unit": "kg",
            "source_keys": ["Qvi", "INv"],
        },
        "Qvo": {
            **common,
            "display_name": "Outgoing water vapor transport",
            "unit": "kg",
            "source_keys": ["Qvo", "OTv"],
        },
        "Qhi": {
            **common,
            "display_name": "Incoming hydrometeor transport",
            "unit": "kg",
            "source_keys": ["Qhi", "INh"],
        },
        "Qho": {
            **common,
            "display_name": "Outgoing hydrometeor transport",
            "unit": "kg",
            "source_keys": ["Qho", "OTh"],
        },
        "RTv": {
            **common,
            "display_name": "Vertical residence time",
            "unit": "day",
            "source_keys": ["RTv", "RCv"],
        },
        "RTh": {
            **common,
            "display_name": "Horizontal residence time",
            "unit": "hour",
            "source_keys": ["RTh", "RCh"],
        },
    }


def resolve_source_keys(
    variable: str,
    registry: dict,
    dataset,
    variable_map: dict[str, str] | None = None,
) -> list[str]:
    specification = registry[variable]
    mapped_key = (variable_map or {}).get(variable)
    if mapped_key:
        groups = [[mapped_key]]
    elif "source_groups" in specification:
        groups = specification["source_groups"]
    else:
        groups = [[key] for key in specification["source_keys"]]
    for group in groups:
        if all(source_key in dataset.data_vars for source_key in group):
            return list(group)
    raise ValueError(
        f"No source field found for variable {variable}: expected one of {groups}"
    )


def resolve_source_key(
    variable: str,
    registry: dict,
    dataset,
    variable_map: dict[str, str] | None = None,
) -> str:
    source_keys = resolve_source_keys(variable, registry, dataset, variable_map)
    if len(source_keys) != 1:
        raise ValueError(f"Variable {variable} requires multiple source fields")
    return source_keys[0]
