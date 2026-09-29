# Raw Source Manifests

This folder stores manifests for raw source files that are kept outside the Git repository.

## Files

- `irpf_raw_pdf_manifest.csv`: one row per local raw PDF file in the research workspace, with relative paths, SHA-256 checksums, file sizes, known public URLs, metadata links, and redistribution notes.
- `irpf_raw_pdf_manifest_summary.md`: generated summary of the PDF manifest.

The manifest documents the local corpus without committing the raw PDFs themselves. Rows classified as `public_url_identified` can be fetched into the ignored local cache with:

```powershell
python scripts/fetch_public_pdfs.py
```

Rows classified as `private_correspondence` identify files received directly from a researcher and should not be redistributed unless explicit permission is obtained.
