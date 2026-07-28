# Report Product Contract

## Boundary

`cwr-report` is an upper-layer consumer. It reads a completed
`report_inputs.json` and never invokes or modifies the computation pipeline.
The computation engine therefore remains reusable by reports and other
products. Newly generated report inputs declare `schema_version: 1`; an omitted
version is treated as the legacy form of version 1.

The first report stage produces one DOCX from one template. PDF conversion,
multi-year-specific logic, and large-language-model text generation are not
part of this contract.

## Report Specification

A report specification is a JSON object with these required paths:

```json
{
  "report_id": "single-year-example",
  "report_inputs": "run/report_inputs/report_inputs.json",
  "template": "templates/single-year.docx",
  "output": "run/report/example.docx",
  "text_slots": {},
  "narrative_slots": {},
  "table_slots": {},
  "image_slots": {}
}
```

Relative paths are resolved from the report specification directory. The
output must use the `.docx` suffix.

## Template Slots

Templates use the existing `<<slot_name>>` notation. A slot name must occur
exactly once for a table or image. Text and narrative slots may occur more than
once. Placeholders may be split across multiple Word runs.

### Text

A text slot is either a literal value or a binding:

```json
{
  "region_name": "内蒙古中西部七盟市研究区",
  "report_year": {
    "source": "inputs.time_slices.0.year",
    "format": "{value}年"
  }
}
```

`source` is a dot-separated path in `report_inputs.json`; numeric path
components index arrays.

### Narrative

The initial narrative kind is `stat_summary`. It filters statistics by optional
variable and operator values, then reports the period, mean, maximum, minimum,
and start-to-end direction using deterministic rules.

```json
{
  "analysis_summary": {
    "kind": "stat_summary",
    "variable": "GMv",
    "operator": "mean",
    "variable_label": "垂直云水资源",
    "operator_label": "区域平均值",
    "unit": "亿吨",
    "value_scale": 1e-11,
    "precision": 2
  }
}
```

### Table

The initial table source is `stats`. Columns define source fields and displayed
headers. Optional filters use exact matches. Tables use a fixed full-width
geometry of 8310 DXA for the A4 standard template. Optional `column_widths`
values must be positive DXA integers totaling 8310.
Numeric columns may declare `scale` and `precision` to convert engine values
into report-facing units.

```json
{
  "stats_table": {
    "source": "stats",
    "filters": {"variable": "GMv"},
    "columns": [
      {"field": "label", "title": "时段"},
      {"field": "operator", "title": "算子"},
      {"field": "value", "title": "结果（亿吨）", "scale": 1e-11, "precision": 2}
    ],
    "column_widths": [4155, 4155]
  }
}
```

### Image

An image slot selects exactly one artifact by matching metadata fields.
Selectors should include the output request `name` when a task may emit more
than one figure of the same kind.

```json
{
  "overview_figure": {
    "selector": {
      "kind": "figure_distribution",
      "name": "gmv_spatial",
      "variable": "GMv",
      "operator": "mean",
      "label": "2025"
    },
    "width_inches": 5.5,
    "alt_text": "2025年GMv区域平均值空间分布图"
  }
}
```

## Failure Rules

The report is not saved when the engine task is unsuccessful, an input path is
missing, a source binding cannot be resolved, a figure selector matches zero or
multiple artifacts, a table has no rows, or any `<<...>>` marker remains
unresolved. Parent directories are created only immediately before a validated
document is saved, and the final DOCX is replaced atomically.
