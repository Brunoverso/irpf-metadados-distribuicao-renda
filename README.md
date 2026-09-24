# Historical IRPF Distribution Source Metadata for Brazil

This repository documents the source metadata and reproducible table assets for a research project on the historical distribution of income declared in the Brazilian Personal Income Tax, locally known as Imposto de Renda da Pessoa Fisica (IRPF).

The project reconstructs and extends the documentary basis used by Pedro Herculano G. F. de Souza in Table 4 of his doctoral dissertation, with special attention to calendar-year coverage, income concept, geographic scope, source location, and comparability across publications.

## Research Scope

The current metadata file covers calendar years 1927-2024. It distinguishes:

- years with data already incorporated into this project;
- years covered in Pedro Herculano G. F. de Souza's Table 4;
- years available only as regional or parallel series;
- years that remain undocumented in the target historical range.

The repository currently stores metadata and generated research assets. It does not store the full raw PDF corpus, because some files are large, some are local archive copies, and some were received through private correspondence.

## Repository Structure

```text
data/
  raw/        Source-layer notes and future raw manifests.
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
- `outputs/metadata/tables/irpf_distribution_metadata_reference_table.csv`: compact table generated from the trusted metadata.
- `outputs/metadata/tables/irpf_distribution_metadata_reference_table.pdf`: PDF version of the compact reference table.
- `scripts/build_metadata_reference_table.py`: command-line script used to regenerate the table assets.

## Reproducibility

Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Regenerate the metadata table assets:

```powershell
python scripts/build_all_assets.py
```

The same command is also run by the GitHub Actions workflow. The workflow checks whether the committed generated assets match the current trusted metadata and scripts.

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
Graduate student, Graduate Program in Applied Physics  
Federal University of Rio de Janeiro (UFRJ), Brazil

Professional contact: TODO - add institutional e-mail  
ORCID: TODO  
Lattes: TODO

Academic supervision: Prof. Marcelo Byrro Ribeiro, UFRJ.

## Citation

This repository is under active development. For now, please cite the repository URL and contact the maintainer before using the metadata in published work. A DOI-based citation will be added after the Zenodo release.
