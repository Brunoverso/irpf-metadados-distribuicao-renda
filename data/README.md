# Data Directory

This directory separates project data into three research layers:

- `raw/`: source-level documentation, source manifests, and future checksums for original materials.
- `refined/`: intermediate extraction products and validation checks derived from raw sources.
- `trusted/`: curated data that can be used directly by scripts and cited as the current research source of truth.

The separation is meant to make the workflow auditable. Raw evidence, intermediate transformations, and curated research outputs should not be mixed in the same folder.

Large PDFs, OCR images, and restricted or privately received source files are not stored in this repository unless their redistribution status is clear.
