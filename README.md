# CWR Engine

## Runtime

All development, tests, and agent work use the Conda environment `cwr_py312`
(Python 3.12).

```powershell
conda env update -n cwr_py312 -f environment.yml --prune
conda run -n cwr_py312 python -m pytest -p no:cacheprovider -q
```
