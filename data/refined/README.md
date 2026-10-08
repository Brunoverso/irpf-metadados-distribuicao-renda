# Refined Data Layer

This folder stores intermediate extraction outputs.

Examples of refined data include OCR-assisted transcriptions, page-level extraction checks, harmonization tables, and quality-control summaries that are not yet the final curated dataset.

## Files

- `extractions/`: sanitized copies of the extracted `irpf_*.csv` tables produced during the research workflow. These preserve the source-specific schemas used during transcription and validation.
- `macro/`: annual exchange-rate and CPI conversion factors derived from the raw macro series.
- `irpf_extracted_tables_manifest.csv`: one row per extracted table, with row counts, column counts, year coverage, and SHA-256 checksums.
- `irpf_extracted_values_long.csv`: long-form cell-level representation of all extracted tables. This is useful for auditing heterogeneous source tables without forcing every publication into one schema.

The main curated yearly metadata and combined analysis tables are stored in `../trusted/`.
