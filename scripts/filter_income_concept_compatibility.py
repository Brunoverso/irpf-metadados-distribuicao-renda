from __future__ import annotations

import argparse
import csv
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA = ROOT / "data" / "trusted" / "irpf_distribution_source_metadata_yearly.csv"
DEFAULT_COMPATIBLE = ROOT / "data" / "trusted" / "irpf_distribution_renda_liquida_compatible_years.csv"
DEFAULT_EXCLUDED = ROOT / "data" / "trusted" / "irpf_distribution_renda_liquida_excluded_years.csv"

COMPATIBLE_FIELDS = [
    "calendar_year",
    "compatibility_scope",
    "geographic_scope",
    "recommended_series",
    "ordering_concept",
    "reported_incomes",
    "tax_return_year",
    "source_block",
    "primary_source",
    "table_or_panel",
    "compatibility_note",
]

EXCLUDED_FIELDS = [
    "calendar_year",
    "geographic_scope",
    "recommended_series",
    "ordering_concept",
    "reported_incomes",
    "source_block",
    "reason_not_compatible",
]


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def ascii_lower(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", clean(value))
    value = value.encode("ascii", "ignore").decode("ascii")
    return " ".join(value.lower().split())


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=fieldnames,
            delimiter=";",
            lineterminator="\n",
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(rows)


def is_renda_liquida_compatible(row: dict[str, str]) -> bool:
    ordering = ascii_lower(row.get("ordering_concept"))
    reported = ascii_lower(row.get("reported_incomes"))
    has_liquid_order = "renda liquida" in ordering or ordering == "rliq"
    has_liquid_measure = "rliq" in reported or "renda liquida" in reported
    return has_liquid_order and has_liquid_measure


def exclusion_reason(row: dict[str, str]) -> str:
    ordering = ascii_lower(row.get("ordering_concept"))
    reported = ascii_lower(row.get("reported_incomes"))
    if "rendimento bruto" in ordering or "renda bruta" in ordering:
        return "faixas ordenadas por renda/rendimento bruto; nao redistribuir como renda liquida sem microdados"
    if "rendimento tributavel" in ordering:
        return "faixas ordenadas por rendimento tributavel bruto; conceito distinto da renda liquida historica"
    if "rendimentos totais" in ordering or "salario minimo" in ordering:
        return "faixas de rendimentos totais em salarios minimos; conceito distinto da renda liquida historica"
    if "rliq" not in reported and "renda liquida" not in reported:
        return "renda liquida nao aparece como medida publicada no metadado anual"
    return "conceito de renda nao classificado como renda liquida compativel"


def compatible_scope(row: dict[str, str]) -> str:
    scope = ascii_lower(row.get("geographic_scope"))
    if scope == "brasil":
        return "national"
    return "regional"


def build_filters(metadata: Path, compatible_output: Path, excluded_output: Path) -> dict[str, int]:
    rows = [row for row in read_csv(metadata) if clean(row.get("project_has_data")) == "1"]
    compatible_rows: list[dict[str, str]] = []
    excluded_rows: list[dict[str, str]] = []

    for row in rows:
        if is_renda_liquida_compatible(row):
            scope = compatible_scope(row)
            note = "renda liquida publicada em faixas compativeis"
            if scope == "regional":
                note += "; serie regional/local, nao comparar diretamente com Brasil"
            compatible_rows.append(
                {
                    **row,
                    "compatibility_scope": scope,
                    "compatibility_note": note,
                }
            )
        else:
            excluded_rows.append({**row, "reason_not_compatible": exclusion_reason(row)})

    compatible_rows.sort(key=lambda row: int(row["calendar_year"]))
    excluded_rows.sort(key=lambda row: int(row["calendar_year"]))
    write_csv(compatible_output, COMPATIBLE_FIELDS, compatible_rows)
    write_csv(excluded_output, EXCLUDED_FIELDS, excluded_rows)
    return {
        "source_years_with_data": len(rows),
        "compatible_years": len(compatible_rows),
        "compatible_national_years": sum(
            1 for row in compatible_rows if row["compatibility_scope"] == "national"
        ),
        "compatible_regional_years": sum(
            1 for row in compatible_rows if row["compatibility_scope"] == "regional"
        ),
        "excluded_years": len(excluded_rows),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter yearly IRPF metadata to the income concept compatible with liquid income."
    )
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--compatible-output", type=Path, default=DEFAULT_COMPATIBLE)
    parser.add_argument("--excluded-output", type=Path, default=DEFAULT_EXCLUDED)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_filters(args.metadata, args.compatible_output, args.excluded_output)
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
