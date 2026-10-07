from __future__ import annotations

from build_data_package import build_data_package
from build_metadata_reference_table import build_pdf as build_metadata_reference_table


def main() -> None:
    build_data_package()
    build_metadata_reference_table()


if __name__ == "__main__":
    main()
