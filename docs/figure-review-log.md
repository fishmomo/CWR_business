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
