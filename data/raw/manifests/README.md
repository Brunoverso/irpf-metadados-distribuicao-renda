# Raw Source Manifests

This folder stores manifests for raw source files used by the project.

## Files

- `irpf_raw_pdf_manifest.csv`: one row per local raw PDF file in the research workspace, with relative paths, SHA-256 checksums, file sizes, known public URLs, metadata links, and redistribution notes.
- `irpf_raw_pdf_manifest_summary.md`: generated summary of the PDF manifest.

The manifest documents the local corpus and the raw PDFs versioned in this repository through Git LFS. Rows classified as `public_url_identified` can be fetched into the ignored local cache with:

```powershell
python scripts/fetch_public_pdfs.py
```

Rows classified as `public_origin_no_public_url_identified` identify files received by correspondence whose public origin was confirmed by the project owner, but for which no direct public URL has been identified yet.
