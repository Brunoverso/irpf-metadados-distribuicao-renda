# Extracted Source Tables

This folder stores sanitized copies of the extracted `irpf_*.csv` source tables used to build the combined data package.

The files preserve the source-specific columns produced during transcription, validation, and harmonization. They are not a single analytical schema. Use the combined files in `../../trusted/` for ordinary analysis, and return to these files when auditing a specific publication or extraction decision.

Regenerate this folder from the local research workspace with:

```powershell
python scripts/build_data_package.py
```
