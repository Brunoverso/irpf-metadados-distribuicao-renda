# Raw PDF Sources

This folder stores raw PDF source files when their redistribution status allows versioning in this repository.

## Versioned Files

Public source PDFs with identified public URLs are stored in `public/` and tracked with Git LFS.

Local source PDFs and project PDFs without an identified public URL are stored in `local/` and tracked with Git LFS. This includes files received by correspondence when their public origin has been confirmed by the project owner.

## Files Not Versioned Here

The following folders are intentionally ignored:

- `private/`: files received through private correspondence or requiring explicit redistribution permission.
- `cache/`: temporary local downloads reconstructed from the public URLs listed in `../manifests/irpf_raw_pdf_manifest.csv`.
- `tmp/`: temporary working files.

Use `../manifests/irpf_raw_pdf_manifest.csv` for checksums, source URLs, and redistribution notes.
