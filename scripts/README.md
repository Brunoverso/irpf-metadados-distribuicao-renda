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

Build the refined and trusted data package from extracted IRPF CSV tables:

```powershell
python scripts/build_data_package.py
```

Build monetary-value tables converted to nominal USD and 2026 USD:

```powershell
python scripts/build_adjusted_usd_tables.py
```

Refresh the BCB/FRED macro series before rebuilding the adjusted tables:

```powershell
python scripts/build_adjusted_usd_tables.py --refresh-macro
```

The adjusted USD builder records the method used for each year. It prefers BCB SGS 3694 with FRED `CPIAUCSL`, falls back to FRED `CPIAUCNS` for CPI before 1947, and uses BCB SGS 3690 for historical mil-reis exchange rates before 1942.

Build histogram figures for direct-frequency bracket series:

```powershell
python scripts/build_irpf_histograms.py
```

Build the raw PDF source manifest from the local research workspace:

```powershell
python scripts/build_raw_pdf_manifest.py
```

Download public source PDFs listed in the raw manifest into the ignored local cache:

```powershell
python scripts/fetch_public_pdfs.py
```

Inspect what would be downloaded without making network requests:

```powershell
python scripts/fetch_public_pdfs.py --dry-run
```

Optional explicit paths:

```powershell
python scripts/build_metadata_reference_table.py `
  --input data/trusted/irpf_distribution_source_metadata_yearly.csv `
  --output-csv outputs/metadata/tables/irpf_distribution_metadata_reference_table.csv `
  --output-pdf outputs/metadata/tables/irpf_distribution_metadata_reference_table.pdf
```
