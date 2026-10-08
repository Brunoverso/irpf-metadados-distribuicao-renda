from __future__ import annotations

import argparse
import csv
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_METADATA = ROOT / "data" / "trusted" / "irpf_distribution_source_metadata_yearly.csv"
DEFAULT_COMPATIBLE = ROOT / "data" / "trusted" / "irpf_distribution_renda_liquida_compatible_years.csv"
DEFAULT_EXCLUDED = ROOT / "data" / "trusted" / "irpf_distribution_renda_liquida_excluded_years.csv"
DEFAULT_BRACKETS = ROOT / "data" / "trusted" / "irpf_distribution_brackets_all_sources.csv"
DEFAULT_TOTALS = ROOT / "data" / "trusted" / "irpf_distribution_totals_all_sources.csv"
DEFAULT_BRACKET_VALUES = ROOT / "data" / "trusted" / "irpf_distribution_bracket_values_usd_2026.csv"
DEFAULT_TOTAL_VALUES = ROOT / "data" / "trusted" / "irpf_distribution_total_values_usd_2026.csv"
DEFAULT_COMPATIBLE_BRACKETS = (
    ROOT / "data" / "trusted" / "irpf_distribution_brackets_renda_liquida_compatible.csv"
)
DEFAULT_COMPATIBLE_TOTALS = (
    ROOT / "data" / "trusted" / "irpf_distribution_totals_renda_liquida_compatible.csv"
)
DEFAULT_COMPATIBLE_BRACKET_VALUES = (
    ROOT / "data" / "trusted" / "irpf_distribution_bracket_values_usd_2026_renda_liquida_compatible.csv"
)
DEFAULT_COMPATIBLE_TOTAL_VALUES = (
    ROOT / "data" / "trusted" / "irpf_distribution_total_values_usd_2026_renda_liquida_compatible.csv"
)

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
    "extracted_bracket_rows",
    "extracted_total_rows",
    "data_ready_status",
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


def read_csv_with_fieldnames(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        return list(reader.fieldnames or []), list(reader)


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


def year_scope_key(row: dict[str, str]) -> tuple[str, str]:
    return (clean(row.get("calendar_year")), ascii_lower(row.get("geographic_scope")))


def compact_identifier(value: str | None) -> str:
    return "".join(ch for ch in ascii_lower(value) if ch.isalnum())


def primary_source_match(row: dict[str, str], compatible: dict[str, str]) -> bool:
    wanted = compact_identifier(compatible.get("source_block"))
    if not wanted:
        return False
    source_table_id = compact_identifier(row.get("source_table_id"))
    source_block = compact_identifier(row.get("source_block"))
    return wanted in source_table_id or wanted in source_block


def related_source_match(row: dict[str, str], compatible: dict[str, str]) -> bool:
    source_table_id = compact_identifier(row.get("source_table_id"))
    source_block = compact_identifier(row.get("source_block"))
    related = [
        compact_identifier(value)
        for value in clean(compatible.get("related_sqlite_tables")).split(";")
        if clean(value)
    ]
    return any(
        related_id
        and (source_table_id == related_id or source_block == related_id)
        for related_id in related
    )


def compatible_for_data_row(
    row: dict[str, str],
    compatible_by_year_scope: dict[tuple[str, str], list[dict[str, str]]],
    source_tables_by_year_scope: dict[tuple[str, str], set[str]],
) -> dict[str, str] | None:
    key = year_scope_key(row)
    candidates = compatible_by_year_scope.get(key, [])
    if not candidates:
        return None

    primary_matches = [candidate for candidate in candidates if primary_source_match(row, candidate)]
    if primary_matches:
        return primary_matches[0]

    source_table_count = len(source_tables_by_year_scope.get(key, set()))
    if source_table_count > 1:
        return None

    related_matches = [candidate for candidate in candidates if related_source_match(row, candidate)]
    if related_matches:
        return related_matches[0]

    if len(candidates) == 1:
        return candidates[0]
    return None


def filter_compatible_table(
    input_path: Path,
    output_path: Path,
    compatible_rows: list[dict[str, str]],
) -> tuple[dict[str, int], dict[str, int]]:
    fieldnames, rows = read_csv_with_fieldnames(input_path)
    compatible_by_year_scope: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in compatible_rows:
        compatible_by_year_scope.setdefault(year_scope_key(row), []).append(row)
    source_tables_by_year_scope: dict[tuple[str, str], set[str]] = {}
    for row in rows:
        source_tables_by_year_scope.setdefault(year_scope_key(row), set()).add(
            clean(row.get("source_table_id"))
        )
    extra_fields = ["income_concept_subset", "compatibility_scope", "compatibility_note"]
    output_rows: list[dict[str, str]] = []

    for row in rows:
        compatible = compatible_for_data_row(
            row, compatible_by_year_scope, source_tables_by_year_scope
        )
        if compatible is None:
            continue
        output_rows.append(
            {
                **row,
                "income_concept_subset": "strict_renda_liquida",
                "compatibility_scope": compatible["compatibility_scope"],
                "compatibility_note": compatible["compatibility_note"],
            }
        )

    write_csv(output_path, fieldnames + extra_fields, output_rows)
    year_counts: dict[str, int] = {}
    for row in output_rows:
        year = clean(row.get("calendar_year"))
        year_counts[year] = year_counts.get(year, 0) + 1
    stats = {
        "rows": len(output_rows),
        "source_tables": len({clean(row.get("source_table_id")) for row in output_rows}),
        "years": len(year_counts),
    }
    return stats, year_counts


def build_filters(
    metadata: Path,
    compatible_output: Path,
    excluded_output: Path,
    brackets_input: Path = DEFAULT_BRACKETS,
    totals_input: Path = DEFAULT_TOTALS,
    bracket_values_input: Path = DEFAULT_BRACKET_VALUES,
    total_values_input: Path = DEFAULT_TOTAL_VALUES,
    compatible_brackets_output: Path = DEFAULT_COMPATIBLE_BRACKETS,
    compatible_totals_output: Path = DEFAULT_COMPATIBLE_TOTALS,
    compatible_bracket_values_output: Path = DEFAULT_COMPATIBLE_BRACKET_VALUES,
    compatible_total_values_output: Path = DEFAULT_COMPATIBLE_TOTAL_VALUES,
) -> dict[str, int]:
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

    bracket_stats, bracket_year_counts = filter_compatible_table(
        brackets_input, compatible_brackets_output, compatible_rows
    )
    total_stats, total_year_counts = filter_compatible_table(
        totals_input, compatible_totals_output, compatible_rows
    )
    bracket_value_stats, _ = filter_compatible_table(
        bracket_values_input, compatible_bracket_values_output, compatible_rows
    )
    total_value_stats, _ = filter_compatible_table(
        total_values_input, compatible_total_values_output, compatible_rows
    )

    for row in compatible_rows:
        year = clean(row.get("calendar_year"))
        bracket_count = bracket_year_counts.get(year, 0)
        total_count = total_year_counts.get(year, 0)
        row["extracted_bracket_rows"] = str(bracket_count)
        row["extracted_total_rows"] = str(total_count)
        if bracket_count and total_count:
            row["data_ready_status"] = "ready_in_trusted_tables"
        elif bracket_count or total_count:
            row["data_ready_status"] = "partial_extracted_rows"
        else:
            row["data_ready_status"] = "compatible_in_metadata_without_extracted_table_rows"

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
        "compatible_bracket_rows": bracket_stats["rows"],
        "compatible_bracket_source_tables": bracket_stats["source_tables"],
        "compatible_total_rows": total_stats["rows"],
        "compatible_total_source_tables": total_stats["source_tables"],
        "compatible_bracket_value_rows": bracket_value_stats["rows"],
        "compatible_total_value_rows": total_value_stats["rows"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Filter yearly IRPF metadata to the income concept compatible with liquid income."
    )
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument("--compatible-output", type=Path, default=DEFAULT_COMPATIBLE)
    parser.add_argument("--excluded-output", type=Path, default=DEFAULT_EXCLUDED)
    parser.add_argument("--brackets-input", type=Path, default=DEFAULT_BRACKETS)
    parser.add_argument("--totals-input", type=Path, default=DEFAULT_TOTALS)
    parser.add_argument("--bracket-values-input", type=Path, default=DEFAULT_BRACKET_VALUES)
    parser.add_argument("--total-values-input", type=Path, default=DEFAULT_TOTAL_VALUES)
    parser.add_argument("--compatible-brackets-output", type=Path, default=DEFAULT_COMPATIBLE_BRACKETS)
    parser.add_argument("--compatible-totals-output", type=Path, default=DEFAULT_COMPATIBLE_TOTALS)
    parser.add_argument(
        "--compatible-bracket-values-output",
        type=Path,
        default=DEFAULT_COMPATIBLE_BRACKET_VALUES,
    )
    parser.add_argument(
        "--compatible-total-values-output",
        type=Path,
        default=DEFAULT_COMPATIBLE_TOTAL_VALUES,
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_filters(
        args.metadata,
        args.compatible_output,
        args.excluded_output,
        brackets_input=args.brackets_input,
        totals_input=args.totals_input,
        bracket_values_input=args.bracket_values_input,
        total_values_input=args.total_values_input,
        compatible_brackets_output=args.compatible_brackets_output,
        compatible_totals_output=args.compatible_totals_output,
        compatible_bracket_values_output=args.compatible_bracket_values_output,
        compatible_total_values_output=args.compatible_total_values_output,
    )
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
