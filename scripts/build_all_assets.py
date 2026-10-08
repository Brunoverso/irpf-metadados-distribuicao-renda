from __future__ import annotations

from build_adjusted_usd_tables import build_adjusted_usd_tables
from build_data_package import build_data_package
from filter_income_concept_compatibility import (
    DEFAULT_COMPATIBLE,
    DEFAULT_EXCLUDED,
    DEFAULT_METADATA,
    build_filters,
)
from build_irpf_histograms import build_histograms
from build_metadata_reference_table import build_pdf as build_metadata_reference_table


def main() -> None:
    build_data_package()
    build_filters(DEFAULT_METADATA, DEFAULT_COMPATIBLE, DEFAULT_EXCLUDED)
    build_adjusted_usd_tables()
    build_histograms()
    build_metadata_reference_table()


if __name__ == "__main__":
    main()
