# Figure Review Log

## Figure 1: evaluation region and grid mask

- Review date: 2026-08-07.
- Rule version: Figure Visual Acceptance Rules version 1; no exception.
- Business use: show the source region boundary, selected grid centers, and the
  grid-mask boundary used by every subsequent calculation.
- Typography and labels: use the direct English analysis name `Cloud-Water
  Evaluation Region`, English legend labels, and longitude/latitude
  tick labels at 22 pt. Region names remain report data and are not rendered
  inside the figure.
- Layout: retain the established 12% longitude and 16% latitude padding so the
  region is not pressed against the axes. The canvas is 6.4 by 3.2 inches and
  22-pt source text remains above 12 pt at the report's 4-inch image width.
  The three compact legend entries use a two-column layout below the
  axes so they neither cover the map nor widen the saved image enough to make
  the report text undersized.
- Affected profiles: the single-year and multi-year cloud-water reports share
  this implementation.
- Artifact paths: `profile_image/target_image1.png` below each profile output
  root, and the corresponding image embedded in each final DOCX report.
- Scope: this change applies only to Figure 1. It does not change the default
  typography of the map panels in later figures.
- Acceptance result: passed. The single-year report and an isolated multi-year
  QA run were rendered through LibreOffice and inspected at full-page size.
  Text remains readable, the legend does not obscure map content, and captions
  and following sections remain correctly placed. The standard multi-year
  output directory was externally locked during regeneration, so the verified
  multi-year artifact used the equivalent `-figure1-qa` output root.

## Figure 2: monthly sequence

- Review date: 2026-08-07.
- Rule version: Figure Visual Acceptance Rules version 1; no exception.
- Business use: compare the monthly evolution of four bar metrics with four
  corresponding line metrics for a single year or a multi-year climatology.
- Typography and labels: use 24-pt y-axis labels, y-axis tick labels, x-axis
  text, and panel labels. Month tick labels use 21 pt to prevent two-digit
  months from colliding and are rotated 45 degrees. Display only the approved
  abbreviations `GMv`, `CEv`, `GMh`, `Cvh`, `CWR`, `Ps`, `RTh`, and `PEh` on
  the y axes.
- Layout: retain four vertically stacked dual-axis panels, use only `(a)` to
  `(d)` panel labels, and use no panel title or overall title. The canvas is
  6.4 by 8.5 inches for placement at the report's 4-inch image width.
- Affected profiles: single-year Figure 2 and multi-year Figure 2 share this
  implementation; the multi-year interannual Figure 3 is outside this review.
- Scope: this change applies only to the shared monthly sequence figure.
- Acceptance result: passed. The single-year report and an isolated multi-year
  QA run were rendered through LibreOffice and inspected at full-page size.
  All labels remain readable, month ticks do not collide, and the figure,
  caption, and following explanatory text remain correctly placed. The
  multi-year artifact used the equivalent `-figure2-qa` output root because the
  standard multi-year output directory has an existing external lock.

## Remaining report figures: interannual sequence and spatial maps

- Review date: 2026-08-07.
- Rule version: Figure Visual Acceptance Rules version 1. The review procedure
  was updated from one-figure-at-a-time acceptance to one grouped review for
  all figures in the same report stage.
- Review scope: multi-year Figure 3, single-year Figure 3, multi-year Figure 4,
  single-year Figures 4-5, and multi-year Figures 5-6. Figures 1-2 were also
  rechecked during the final report render.
- Typography and labels: the interannual sequence uses the approved `GMv`,
  `CEv`, `GMh`, `Cvh`, `CWR`, `Ps`, `RTh`, and `PEh` abbreviations. Map axes,
  panel labels, colorbar ticks, and colorbar abbreviations use 23-pt source
  text. Maps use only `(a)`-style panel labels and no panel or overall titles.
- Layout: annual maps use six independently scaled, vertically aligned
  colorbars; seasonal maps use one colorbar aligned to the complete four-panel
  region. Repeated longitude labels are limited to the bottom row and repeated
  latitude labels to the left column. Map images are placed at 6.2 inches in
  the final report while other figures retain the 4-inch default.
- Spatial rendering: when a region geometry is available, contours retain the
  source grid values and are clipped to the geometry after rendering. A
  mask-to-NaN fallback is used only when no geometry is available.
- Affected profiles: both single-year and multi-year cloud-water reports use
  the same map renderer and per-image width override contract.
- Acceptance result: passed. Both reports were regenerated, rendered through
  LibreOffice, and inspected as complete documents and at full-size figure
  pages. All figures fit the page, labels remain readable, colorbars align with
  their panel regions, and no image, caption, or body text overlaps. The
  multi-year QA artifact used the isolated `-remaining-figures-qa` output root
  because the formal output directory remains externally locked.

## X-axis typography override

- Change date: 2026-08-07.
- Scope: all single-year and multi-year cloud-water figures.
- New setting: sequence `xlabel` text is 16 pt; sequence `xticklabel` text is
  15 pt; map and region coordinate tick labels are 15 pt.
- Unchanged elements: y-axis labels and ticks, colorbars, legends, titles, and
  panel labels retain their previously accepted settings.
- Review result: automated tests only. Visual PNG and DOCX review was
  explicitly skipped for this adjustment.

## Unit-label correction

- Change date: 2026-08-07.
- Scope: monthly Figure 2, multi-year interannual Figure 3, and all annual and
  seasonal spatial maps.
- Sequence figures: y-axis labels now combine the approved abbreviation with
  `mm`, `%`, or `hour`. Figure 2 month tick labels use zero rotation and its
  source canvas width is 7.2 inches.
- Spatial figures: colorbar titles show only `mm` or `%`, not the physical
  variable name, and use 12-pt title padding from the colorbar axis.
- Review result: automated tests only; visual review remains explicitly
  skipped. Formal reports are regenerated after this change.

## Sequence-axis typography alignment

- Change date: 2026-08-07.
- Scope: monthly Figure 2 and multi-year interannual Figure 3.
- New setting: both x- and y-axis titles use 16-pt source text; both x- and
  y-axis tick labels use 15-pt source text.
- Reason: the retained 24-pt y-axis typography was visibly disproportionate
  after the x-axis was reduced, causing crowded units and tick labels.
