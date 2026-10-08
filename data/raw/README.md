# Raw Data Layer

This folder is reserved for raw-source manifests, documentation, versioned raw PDFs, and an ignored local cache of reconstructible source PDFs.

Raw PDFs whose redistribution status allows publication are tracked with Git LFS under `pdfs/`. Any additional local materials should only be published after their redistribution status is reviewed.

The `pdfs/cache/` folder is an ignored local cache. Publicly downloadable PDFs can be reconstructed there from the manifest with `scripts/fetch_public_pdfs.py`.

Future files in this folder may include:

- source manifests with bibliographic references;
- file checksums;
- download URLs;
- archive call numbers;
- access notes for physical or digital repositories.

Current manifests are stored in `manifests/`.

Macroeconomic source series used for currency conversion are stored in `macro/`.
