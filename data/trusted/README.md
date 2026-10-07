# Trusted Data Layer

This folder contains curated data used directly by the repository scripts.

## Files

- `irpf_distribution_source_metadata_yearly.csv`: one row per calendar year in the target range. It records whether the project currently has data, whether Pedro Herculano G. F. de Souza's Table 4 reports coverage, the recommended series classification, the income concept, source references, links or local file notes, page locations, related extraction tables, and methodological observations.
- `irpf_distribution_brackets_all_sources.csv`: bracket-level distribution rows combined from the extracted source tables. The file preserves original source-specific columns and adds repository-level provenance columns.
- `irpf_distribution_totals_all_sources.csv`: table-level totals combined from the extracted source tables.
- `irpf_distribution_data_dictionary.csv`: machine-generated inventory of fields present in the combined bracket and total files.

These files are the current source of truth for the generated metadata table assets in `../../outputs/metadata/tables/` and for downstream analysis.
