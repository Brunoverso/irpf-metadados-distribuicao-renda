# Scripts

Scripts in this directory are designed to be runnable both locally and through GitHub Actions.

## Available Commands

Build all committed assets:

```powershell
python scripts/build_all_assets.py
```

Build only the compact metadata reference table:

```powershell
python scripts/build_metadata_reference_table.py
```

Optional explicit paths:

```powershell
python scripts/build_metadata_reference_table.py `
  --input data/trusted/irpf_distribution_source_metadata_yearly.csv `
  --output-csv outputs/metadata/tables/irpf_distribution_metadata_reference_table.csv `
  --output-pdf outputs/metadata/tables/irpf_distribution_metadata_reference_table.pdf
```
