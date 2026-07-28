def _mean(data, dim=None):
    return data.mean(dim=dim, skipna=True, keep_attrs=True)


def _maximum(data, dim=None):
    return data.max(dim=dim, skipna=True, keep_attrs=True)


def _minimum(data, dim=None):
    return data.min(dim=dim, skipna=True, keep_attrs=True)


def _sum(data, dim=None):
    return data.sum(dim=dim, skipna=True, min_count=1, keep_attrs=True)


def build_operator_registry() -> dict:
    common = {
        "input_kind": "series_or_grid",
        "output_kind": "scalar_or_grid",
        "supported_scales": ["day", "month", "year"],
    }
    return {
        "mean": {**common, "apply": _mean},
        "max": {**common, "apply": _maximum},
        "min": {**common, "apply": _minimum},
        "sum": {**common, "apply": _sum},
    }
