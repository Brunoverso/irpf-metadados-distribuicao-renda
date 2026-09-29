# Local Raw PDF Cache

This folder is reserved for a local cache of raw PDF source files reconstructed from the public URLs listed in `../manifests/irpf_raw_pdf_manifest.csv`.

The PDF files themselves are not committed to Git. They are intentionally ignored because the corpus is large and because redistribution rights vary by source. Publicly downloadable files can be fetched again from the manifest, while files received through private correspondence should remain documented only by metadata unless explicit redistribution permission is obtained.

To inspect what would be downloaded:

```powershell
python scripts/fetch_public_pdfs.py --dry-run
```

To download public source PDFs into this ignored cache:

```powershell
python scripts/fetch_public_pdfs.py
```

Each downloaded file is checked against the SHA-256 checksum stored in the manifest. If the checksum does not match, the file is not accepted.
