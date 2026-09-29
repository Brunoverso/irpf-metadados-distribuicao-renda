# Raw PDF Manifest Summary

This summary describes the generated raw PDF manifest. The PDFs themselves are not versioned in this repository.

- PDF files listed: 103
- Total listed size: 1944.27 MB

## Access Categories

- `local_copy_no_public_url_identified`: 15
- `private_correspondence`: 3
- `public_url_identified`: 85

## Document Roles

- `project_document`: 4
- `source_pdf`: 99

## Files

- `irpf_raw_pdf_manifest.csv`: one row per local raw PDF file, including relative path, SHA-256 checksum, size, identified public URLs, and redistribution notes.

The manifest can be regenerated locally with:

```powershell
python scripts/build_raw_pdf_manifest.py
```
