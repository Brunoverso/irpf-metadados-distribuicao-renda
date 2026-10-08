from __future__ import annotations

from build_adjusted_usd_tables import build_adjusted_usd_tables
from build_data_package import build_data_package
from build_metadata_reference_table import build_pdf as build_metadata_reference_table


def main() -> None:
    build_data_package()
    build_adjusted_usd_tables()
    build_metadata_reference_table()


if __name__ == "__main__":
    main()
