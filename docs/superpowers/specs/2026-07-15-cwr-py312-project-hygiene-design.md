# CWR Python 3.12 Environment and Project Hygiene

## Goal

Make `cwr_py312` (Python 3.12) the documented and reproducible runtime for
the CWR engine. Keep representative task inputs and generated examples under
clear repository locations, while excluding disposable caches and regenerated
run artifacts.

## Environment Contract

The supported local environment is the Conda environment `cwr_py312`. Project
metadata will require Python 3.12 or newer, matching the type-hint syntax used
by the source. An `environment.yml` will provide a direct Conda creation/update
path, and the package metadata will list runtime/test dependencies required by
the engine and its tests.

## Repository Layout

Business samples remain versioned and are moved as follows:

| Current material | Target location | Purpose |
| --- | --- | --- |
| `inputs/` | `data/inputs/` | Representative source data used by example tasks |
| Root pipeline JSON files | `examples/tasks/` | Runnable example and acceptance-task definitions |
| `outputs/` | `artifacts/examples/` | Small checked-in reference manifests/results |
| `scripts/` | `scripts/` | Developer utilities; retained in place |

Tasks will locate their data relative to their own JSON file, so moving an
example does not depend on the current working directory. References to checked
in examples will be adjusted to their new locations.

## Artifact Policy

Python bytecode and pytest caches are not tracked. Generated runtime outputs
are ignored by default, except for the deliberate reference artifacts under
`artifacts/examples/`. Previously tracked bytecode files are removed from the
repository index.

## Validation and Bug Triage

All verification will run through `conda run -n cwr_py312`. The work includes:

1. Running the full test suite and representative example tasks.
2. Fixing reproducible failures in source code, task definitions, dependency
   metadata, or path handling.
3. Adding regression tests before each source-code bug fix.
4. Reporting findings that require a product decision rather than silently
   changing behavior.

## Non-goals

This work does not delete business sample data, redesign the computational
workflow, or publish/commit unrelated existing edits.
