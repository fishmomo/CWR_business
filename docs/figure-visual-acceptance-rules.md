# Figure Visual Acceptance Rules

## Authority and precedence

Version: 1

Effective date: 2026-08-07.

These rules are the default baseline for every subsequent figure review and
revision. A newer explicit user instruction overrides the corresponding rule.
Every override must record the changed rule, effective date, affected figures,
and whether previously accepted figures need to be regenerated.

The rules govern display and visual acceptance. They do not rename source
NetCDF variables, metric JSON fields, registry keys, or calculation formulas.

## Typography

- Visible text should not be smaller than 12 pt.
- Axis labels, axis tick labels, colorbar labels, and colorbar tick labels must
  remain legible after the figure is placed in its final report. Use 16 pt or
  larger by default and increase it when scaled output is still too small.
- Heatmap cell values must use at least 14 pt. Their final size must also be
  reviewed against canvas size and grid density.
- Panel labels use a consistent top-left position. They must be at least 12 pt
  and should normally use 14-16 pt.

## Labels and titles

- Y-axis variable labels use the approved abbreviation only, not an expanded
  English variable name.
- Axis descriptions and colorbar descriptions may use Chinese.
- A multi-panel figure has no title above individual panels. Panels use only
  `(a)`, `(b)`, `(c)`, `(d)`, and subsequent labels as needed.
- A single-panel figure has no `(a)`-style panel label. Its name uses the case
  name or analysis name directly.
- A figure has no overall title unless a later explicit requirement creates an
  exception.

## Colorbars

- A colorbar must be exactly aligned to the height of its corresponding panel
  region. It must not be visibly shorter or taller.
- Shared colorbars in multi-panel figures align with the complete panel region
  they describe.
- Label and tick typography follows the axis readability rule above.

## Display abbreviations

The following mapping is authoritative for figure labels:

| Internal or historical key | Display label |
| --- | --- |
| `GMv` | `GMv` |
| `GMh` | `GMh` |
| `Dv` | `Dv` |
| `Dh` | `Dh` |
| `CWR` | `CWR` |
| `CEv` | `CEv` |
| `PEv` | `PEv` |
| `PEh` | `PEh` |
| `INv` | `Qvi` |
| `OTv` | `Qvo` |
| `INh` | `Qhi` |
| `OTh` | `Qho` |
| `MC` | `Cvh` |
| `SP` | `Ps` |
| `RCv` | `RTv` |
| `RCh` | `RTh` |

## Current impact range

This version applies immediately to every newly generated or modified figure.
Existing artifacts are not silently treated as compliant. Figures in the same
report stage are reviewed as one group, followed by one combined report-level
render and acceptance pass.

The known review scope is:

- The five single-year cloud-water report figures.
- The six multi-year cloud-water report figures.
- Standard time-series, distribution, and bar-comparison renderers when their
  outputs are next modified or accepted for formal use.

Known existing mismatches include sub-12-pt legend or title text, default-small
Matplotlib axis ticks, historical labels such as `MC`, `SP`, and `RCh`, and
multi-panel map titles. These are remediation candidates, not permission for
unreviewed bulk visual changes.

## Per-figure change record

Each reviewed figure records:

1. Figure identifier and business use.
2. Applicable rule version and any explicit exception.
3. Changed typography, labels, layout, colorbar, and canvas dimensions.
4. Affected report profiles and artifact paths.
5. Visual acceptance result at final output size.
6. Whether the change applies only to this figure or updates the default rule.
