# Historical IRPF Distribution Source Metadata for Brazil

This repository documents the source metadata and reproducible table assets for a research project on the historical distribution of income declared in the Brazilian Personal Income Tax, locally known as Imposto de Renda da Pessoa Fisica (IRPF).

The project reconstructs and extends the documentary basis used by Pedro Herculano G. F. de Souza in Table 4 of his doctoral dissertation, with special attention to calendar-year coverage, income concept, geographic scope, source location, and comparability across publications.

## Research Scope

The current metadata file covers calendar years 1927-2024. It distinguishes:

- years with data already incorporated into this project;
- years covered in Pedro Herculano G. F. de Souza's Table 4;
- years available only as regional or parallel series;
- years that remain undocumented in the target historical range.

The repository stores metadata, extracted data, generated research assets, and raw PDF sources tracked with Git LFS. Files received by correspondence are included only when the project owner has confirmed public origin or redistribution permission.

## Repository Structure

```text
data/
  raw/        Source-layer notes, raw manifests, and ignored local PDF cache.
  refined/    Intermediate extraction outputs and harmonization checks.
  trusted/    Curated metadata used as the research source of truth.
outputs/
  metadata/
    tables/   Generated CSV and PDF table assets for the metadata module.
    figures/  Generated figures for the metadata module, when available.
scripts/      Reproducible scripts callable locally or by GitHub Actions.
.github/
  workflows/  Continuous-integration workflows for rebuilding assets.
```

## Main Files

- `data/trusted/irpf_distribution_source_metadata_yearly.csv`: curated yearly metadata, one row per calendar year.
- `data/trusted/irpf_distribution_brackets_all_sources.csv`: combined bracket-level extracted data from all usable source tables.
- `data/trusted/irpf_distribution_totals_all_sources.csv`: combined table-level totals from all usable source tables.
- `data/trusted/irpf_distribution_bracket_values_usd_2026.csv`: monetary values from the bracket table converted to nominal USD and 2026 USD when macro inputs are available.
- `data/trusted/irpf_distribution_total_values_usd_2026.csv`: monetary values from the totals table converted to nominal USD and 2026 USD when macro inputs are available.
- `data/refined/macro/usd_2026_conversion_factors.csv`: yearly exchange-rate and U.S. CPI factors used in the conversion.
- `data/refined/extractions/`: sanitized copies of the source extraction CSVs used to build the combined data package.
- `data/refined/irpf_extracted_tables_manifest.csv`: manifest of extraction tables included in the data package.
- `data/raw/macro/`: raw BCB/FRED macro series used to build the conversion factors.
- `data/raw/manifests/irpf_raw_pdf_manifest.csv`: manifest of local raw PDF sources, with checksums, sizes, relative paths, public links when identified, and redistribution notes.
- `data/raw/pdfs/public/`: public raw source PDFs tracked with Git LFS.
- `data/raw/pdfs/local/`: local raw PDFs and project PDFs without an identified public URL, tracked with Git LFS.
- `outputs/metadata/tables/irpf_distribution_metadata_reference_table.csv`: compact table generated from the trusted metadata.
- `outputs/metadata/tables/irpf_distribution_metadata_reference_table.pdf`: PDF version of the compact reference table.
- `scripts/build_metadata_reference_table.py`: command-line script used to regenerate the table assets.
- `scripts/build_data_package.py`: command-line script used to rebuild the refined and trusted data package from extracted CSV tables.
- `scripts/fetch_public_pdfs.py`: command-line script used to fetch public source PDFs listed in the raw manifest and verify their checksums.

## Reproducibility

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Regenerate the metadata table assets:

```powershell
python scripts/build_all_assets.py
```

The same command is also run by the GitHub Actions workflow. The workflow checks whether the committed generated assets match the current trusted metadata, data package, and scripts.

Inspect the public source PDFs that can be reconstructed from the manifest:

```powershell
python scripts/fetch_public_pdfs.py --dry-run
```

Download those public PDFs into the ignored local cache:

```powershell
python scripts/fetch_public_pdfs.py
```

Files received by correspondence are redistributed only when public origin or permission has been confirmed; otherwise they should stay outside the repository.

## Future Archival Plan

The research dataset will eventually be prepared for deposition in Zenodo to obtain a DOI. The intended long-term output is a citable research dataset and, if appropriate, a data descriptor article in a journal such as Scientific Data.

Before public archival, the repository should define:

- a stable release version;
- a data license;
- the final list of authors and contributors;
- ORCID identifiers;
- a complete citation file;
- a description of which raw source files can be redistributed.

## Maintainer

Bruno Freitas Lima  
Program in Applied Physics  
Federal University of Rio de Janeiro (UFRJ), Brazil

Professional contact: TODO - add institutional e-mail  
ORCID: TODO  
Lattes: TODO

Academic supervision: Prof. Marcelo Byrro Ribeiro, UFRJ.

## Citation

This repository is under active development. For now, please cite the repository URL and contact the maintainer before using the metadata in published work. A DOI-based citation will be added after the Zenodo release.
