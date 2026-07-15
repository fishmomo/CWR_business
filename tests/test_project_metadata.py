from pathlib import Path
import tomllib


ROOT = Path(__file__).resolve().parents[1]


def test_project_requires_python_312_or_newer():
    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert metadata["project"]["requires-python"] == ">=3.12"


def test_conda_environment_is_named_cwr_py312():
    environment = (ROOT / "environment.yml").read_text(encoding="utf-8")
    assert "name: cwr_py312" in environment
    assert "- python=3.12" in environment
