# Trusted Data Layer

This folder contains curated data used directly by the repository scripts.

## Files

- `irpf_distribution_source_metadata_yearly.csv`: one row per calendar year in the target range. It records whether the project currently has data, whether Pedro Herculano G. F. de Souza's Table 4 reports coverage, the recommended series classification, the income concept, source references, links or local file notes, page locations, related extraction tables, and methodological observations.
- `irpf_distribution_brackets_all_sources.csv`: bracket-level distribution rows combined from the extracted source tables. The file preserves original source-specific columns and adds repository-level provenance columns.
- `irpf_distribution_totals_all_sources.csv`: table-level totals combined from the extracted source tables.
- `irpf_distribution_bracket_values_usd_2026.csv`: long-form monetary values extracted from the bracket table, converted to nominal USD and to 2026 USD when the required exchange-rate and CPI inputs exist. Each row records the exchange-rate source, CPI series, conversion method, and conversion status.
- `irpf_distribution_total_values_usd_2026.csv`: long-form monetary values extracted from the totals table, converted to nominal USD and to 2026 USD when the required exchange-rate and CPI inputs exist. Each row records the exchange-rate source, CPI series, conversion method, and conversion status.
- `irpf_distribution_data_dictionary.csv`: machine-generated inventory of fields present in the combined bracket and total files.
- `irpf_distribution_renda_liquida_compatible_years.csv`: filtered list of years whose available table is ordered by liquid income and reports liquid income, so the year can be considered for the strict liquid-income concept subset. The `compatibility_scope` column separates national and regional/local series, and the extracted-row columns show whether the year is already present in the trusted bracket and total tables.
- `irpf_distribution_renda_liquida_excluded_years.csv`: years with data that are excluded from the strict liquid-income concept subset, with the reason for exclusion.
- `irpf_distribution_brackets_renda_liquida_compatible.csv`: bracket-level distribution rows filtered to the strict liquid-income concept subset.
- `irpf_distribution_totals_renda_liquida_compatible.csv`: table-level totals filtered to the strict liquid-income concept subset.
- `irpf_distribution_bracket_values_usd_2026_renda_liquida_compatible.csv`: USD-adjusted bracket monetary values filtered to the strict liquid-income concept subset.
- `irpf_distribution_total_values_usd_2026_renda_liquida_compatible.csv`: USD-adjusted total monetary values filtered to the strict liquid-income concept subset.

These files are the current source of truth for the generated metadata table assets in `../../outputs/metadata/tables/` and for downstream analysis.

The USD-adjusted files use BCB SGS 3694 plus FRED `CPIAUCSL` for the modern segment, BCB SGS 3694 plus FRED `CPIAUCNS` for 1943-1946, and BCB SGS 3690 plus FRED `CPIAUCNS` for 1927-1941. The remaining 1942 monetary rows are kept in the long files but marked as missing exchange-rate input.
