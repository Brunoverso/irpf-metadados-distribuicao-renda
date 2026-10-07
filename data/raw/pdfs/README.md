# Raw PDF Sources

This folder stores raw PDF source files when their redistribution status allows versioning in this repository.

## Versioned Files

Public source PDFs with identified public URLs are stored in `public/` and tracked with Git LFS.

## Files Not Versioned Here

The following folders are intentionally ignored:

- `private/`: files received through private correspondence or requiring explicit redistribution permission.
- `cache/`: temporary local downloads reconstructed from the public URLs listed in `../manifests/irpf_raw_pdf_manifest.csv`.
- `tmp/`: temporary working files.

Files received through private correspondence remain documented in the manifest but should not be redistributed without explicit permission.

Use `../manifests/irpf_raw_pdf_manifest.csv` for checksums, source URLs, and redistribution notes.
