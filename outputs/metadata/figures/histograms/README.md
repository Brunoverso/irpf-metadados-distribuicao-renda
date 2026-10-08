# IRPF Histogram Figures

This folder contains generated histogram assets for direct-frequency IRPF bracket series.

## Files

- `irpf_distribution_histograms.pdf`: combined A3 landscape PDF, one histogram per page.
- `irpf_histogram_manifest.csv`: generation manifest with source metadata, chart paths, page references, frequency field, axis labels, and skipped-source notes.
- `irpf_histogram_*.svg`: individual SVG histograms.

The charts preserve the income brackets published by each source on the X axis. Currency, unit, and bracket definitions therefore vary across years and publications. The Y axis is the direct frequency field identified for each table, such as people notified, taxpayers, filers, declarations, or declarants.

Regenerate these assets with:

```powershell
python scripts/build_irpf_histograms.py
```
