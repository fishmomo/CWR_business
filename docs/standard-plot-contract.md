# Standard Plot Contract

All formal outputs also follow
`docs/figure-visual-acceptance-rules.md`. That document is authoritative for
font sizes, panel labels, title usage, colorbar alignment, and displayed
variable abbreviations. Product-specific contracts may add requirements but
may not silently weaken that baseline.

## Output requests

The plot step recognizes:

| Kind | Multiplicity | Filename |
| --- | --- | --- |
| `figure_timeseries` | variable | `<name>_<variable>.png` |
| `figure_distribution` | time slice, variable, operator | `<name>_<label>_<variable>_<operator>.png` |
| `figure_bar_compare` | variable, operator | `<name>_<variable>_<operator>.png` |

## Parameters

Every output request may contain a `params` object.

Common parameters:

- `title`: format string using fields valid for that plot type.
- `figsize`: `[width, height]` in inches.
- `dpi`: positive integer.

Time-series parameters:

- `ylabel`
- `line_color`

Distribution parameters:

- `cmap`
- `vmin`
- `vmax`
- `colorbar_label`

Bar-comparison parameters:

- `ylabel`
- `bar_color`

Title fields are:

- Time series: `{variable}`
- Distribution: `{label}`, `{variable}`, `{operator}`
- Bar comparison: `{variable}`, `{operator}`

Unknown parameters, invalid colors, invalid color maps, non-positive sizes, and
unsupported title fields fail before the output directory is created.

## Data semantics

- Time series use the masked regional spatial mean at every source time.
- Distribution figures apply the requested operator along the time dimension
  of each time slice and retain `lat/lon`.
- Bar figures use the regional scalar results produced by the stat step.

This contract does not define map projections, administrative boundaries, or
product-specific layouts. Visual acceptance is defined separately so it can be
updated without changing calculation or output-request semantics.
