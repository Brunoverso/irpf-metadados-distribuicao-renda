# Metadata Figure Assets

This folder is reserved for generated figures associated with the source-metadata module.

## Files

- `histograms/irpf_distribution_histograms.pdf`: one-page-per-series PDF collecting the generated direct-frequency bracket histograms.
- `histograms/irpf_histogram_manifest.csv`: manifest documenting every source group considered for histogram generation, including skipped groups and the reason they were skipped.
- `histograms/irpf_histogram_*.svg`: individual SVG histogram assets.

The histogram script renders only bracket tables with one direct frequency column, such as people, taxpayers, filers, declarations, or declarants. Auxiliary tables that split several measures across columns, and cumulative "above threshold" tables, are listed in the manifest but not rendered as ordinary histograms.
