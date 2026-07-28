from cwr_engine.registries.operators import build_operator_registry
from cwr_engine.registries.plots import build_plot_registry
from cwr_engine.registries.variables import build_variable_registry


def test_builtin_registries_have_seed_entries():
    variables = build_variable_registry()
    operators = build_operator_registry()
    plots = build_plot_registry()

    assert "temp" in variables
    assert "precip" in variables
    assert "mean" in operators
    assert {"mean", "max", "min", "sum"} <= operators.keys()
    assert "timeseries" in plots
