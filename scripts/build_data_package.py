from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DEFAULT_EXTERNAL_SOURCE_ROOT = PROJECT_ROOT / "outputs" / "fontes-pedro-souza-irpf"
DEFAULT_REFINED_EXTRACTIONS_DIR = ROOT / "data" / "refined" / "extractions"
DEFAULT_REFINED_MANIFEST = ROOT / "data" / "refined" / "irpf_extracted_tables_manifest.csv"
DEFAULT_REFINED_LONG = ROOT / "data" / "refined" / "irpf_extracted_values_long.csv"
DEFAULT_TRUSTED_BRACKETS = ROOT / "data" / "trusted" / "irpf_distribution_brackets_all_sources.csv"
DEFAULT_TRUSTED_TOTALS = ROOT / "data" / "trusted" / "irpf_distribution_totals_all_sources.csv"
DEFAULT_TRUSTED_DICTIONARY = ROOT / "data" / "trusted" / "irpf_distribution_data_dictionary.csv"

USER_DESKTOP_RE = re.compile(r"C:/Users/[^/]+/Desktop/", flags=re.IGNORECASE)
USER_HOME_RE = re.compile(r"C:/Users/[^/]+/", flags=re.IGNORECASE)

META_COLUMNS = [
    "source_table_id",
    "source_file",
    "table_kind",
    "source_row_number",
    "calendar_year",
    "tax_return_year",
    "geographic_scope",
    "source_block",
]


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def normalize_path_text(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    if ":\\\\" in value or ":\\" in value or "outputs\\" in value:
        value = value.replace("\\", "/")

    project_prefix = PROJECT_ROOT.resolve().as_posix().rstrip("/") + "/"
    repo_prefix = ROOT.resolve().as_posix().rstrip("/") + "/"
    value = value.replace(project_prefix, "")
    value = value.replace(repo_prefix, "")
    value = USER_DESKTOP_RE.sub("local-desktop:/", value)
    value = USER_HOME_RE.sub("local-user:/", value)
    return value


def sanitize_row(row: dict[str, str]) -> dict[str, str]:
    return {field: normalize_path_text(value) for field, value in row.items()}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f, delimiter=";")
        fieldnames = list(reader.fieldnames or [])
        rows = [sanitize_row(row) for row in reader]
    return fieldnames, rows


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


def classify_table(path: Path) -> str:
    name = path.name
    if "consolidado" in name:
        return "historical_consolidated"
    if name.endswith("_faixas_origem.csv"):
        return "bracket_source_detail"
    if name.endswith("_totais.csv"):
        return "total"
    if name.endswith("_acima.csv"):
        return "above_threshold_distribution"
    if name.endswith("_intervalos.csv"):
        return "bracket_distribution"
    if name.endswith("_renda_liquida_por_rendimento_bruto.csv"):
        return "bracket_distribution"
    if name.endswith("_faixas.csv"):
        return "bracket_distribution"
    return "other"


def source_table_id(path: Path) -> str:
    return path.stem


def first_present(row: dict[str, str], fields: tuple[str, ...]) -> str:
    for field in fields:
        value = clean(row.get(field))
        if value:
            return value
    return ""


def calendar_year(row: dict[str, str]) -> str:
    return first_present(row, ("ano_calendario", "ano_calendario_inferido", "calendar_year"))


def tax_return_year(row: dict[str, str]) -> str:
    return first_present(row, ("ano_exercicio", "ano_lancamento", "tax_return_year"))


def geographic_scope(row: dict[str, str]) -> str:
    return first_present(row, ("unidade_geografica", "geographic_scope"))


def source_block(row: dict[str, str], fallback: str) -> str:
    return first_present(row, ("fonte_bloco", "source_block")) or fallback


def bracket_code(row: dict[str, str]) -> str:
    return first_present(row, ("codigo_faixa", "codigo_faixa_origem", "bracket_code"))


def bracket_order(row: dict[str, str]) -> str:
    return first_present(row, ("ordem_faixa", "ordem_faixa_origem", "bracket_order"))


def iter_source_csvs(source_root: Path) -> list[Path]:
    return sorted(source_root.glob("irpf_*.csv"), key=lambda path: path.name.lower())


def same_path(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except FileNotFoundError:
        return left.absolute() == right.absolute()


def load_or_copy_extractions(source_root: Path, refined_dir: Path) -> list[dict[str, object]]:
    source_paths = iter_source_csvs(source_root)
    if not source_paths:
        raise FileNotFoundError(f"no irpf_*.csv files found in {source_root}")

    refined_dir.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    copying_from_external = not same_path(source_root, refined_dir)

    for source_path in source_paths:
        fields, rows = read_csv(source_path)
        output_path = refined_dir / source_path.name
        if copying_from_external:
            write_csv(output_path, fields, rows)
        elif not output_path.exists():
            raise FileNotFoundError(f"refined extraction not found: {output_path}")

        records.append(
            {
                "source_path": source_path,
                "refined_path": output_path,
                "fields": fields,
                "rows": rows,
                "table_kind": classify_table(source_path),
                "source_table_id": source_table_id(source_path),
            }
        )

    return records


def source_root_for_build(args_source_root: Path | None, refined_dir: Path) -> Path:
    if args_source_root is not None:
        return args_source_root
    if DEFAULT_EXTERNAL_SOURCE_ROOT.exists():
        return DEFAULT_EXTERNAL_SOURCE_ROOT
    return refined_dir


def year_summary(rows: list[dict[str, str]]) -> tuple[str, str, str]:
    years = sorted({int(year) for row in rows if (year := calendar_year(row)).isdigit()})
    if not years:
        return "", "", "0"
    return str(years[0]), str(years[-1]), str(len(years))


def write_manifest(records: list[dict[str, object]], output_path: Path) -> list[dict[str, str]]:
    manifest_rows: list[dict[str, str]] = []
    for record in records:
        rows = record["rows"]
        assert isinstance(rows, list)
        first_year, last_year, year_count = year_summary(rows)
        fields = record["fields"]
        assert isinstance(fields, list)
        refined_path = record["refined_path"]
        assert isinstance(refined_path, Path)
        manifest_rows.append(
            {
                "source_table_id": str(record["source_table_id"]),
                "source_file": refined_path.name,
                "table_kind": str(record["table_kind"]),
                "row_count": str(len(rows)),
                "column_count": str(len(fields)),
                "first_calendar_year": first_year,
                "last_calendar_year": last_year,
                "calendar_year_count": year_count,
                "sha256": sha256_file(refined_path),
                "refined_path": refined_path.relative_to(ROOT).as_posix(),
            }
        )

    write_csv(
        output_path,
        [
            "source_table_id",
            "source_file",
            "table_kind",
            "row_count",
            "column_count",
            "first_calendar_year",
            "last_calendar_year",
            "calendar_year_count",
            "sha256",
            "refined_path",
        ],
        manifest_rows,
    )
    return manifest_rows


def build_combined_rows(
    records: list[dict[str, object]],
    included_kinds: set[str],
) -> tuple[list[str], list[dict[str, str]]]:
    original_fields: list[str] = []
    seen_fields = set(META_COLUMNS)
    combined_rows: list[dict[str, str]] = []

    for record in records:
        if str(record["table_kind"]) not in included_kinds:
            continue
        rows = record["rows"]
        fields = record["fields"]
        assert isinstance(rows, list)
        assert isinstance(fields, list)
        table_id = str(record["source_table_id"])
        refined_path = record["refined_path"]
        assert isinstance(refined_path, Path)

        for field in fields:
            if field not in seen_fields:
                original_fields.append(field)
                seen_fields.add(field)

        for row_number, row in enumerate(rows, start=1):
            assert isinstance(row, dict)
            combined = {
                "source_table_id": table_id,
                "source_file": refined_path.name,
                "table_kind": str(record["table_kind"]),
                "source_row_number": str(row_number),
                "calendar_year": calendar_year(row),
                "tax_return_year": tax_return_year(row),
                "geographic_scope": geographic_scope(row),
                "source_block": source_block(row, table_id),
            }
            combined.update(row)
            combined_rows.append(combined)

    sort_fields = ("calendar_year", "tax_return_year", "source_table_id", "source_row_number")
    combined_rows.sort(key=lambda row: tuple(clean(row.get(field)) for field in sort_fields))
    return META_COLUMNS + original_fields, combined_rows


def write_long_values(records: list[dict[str, object]], output_path: Path) -> int:
    rows_out: list[dict[str, str]] = []
    for record in records:
        rows = record["rows"]
        fields = record["fields"]
        assert isinstance(rows, list)
        assert isinstance(fields, list)
        table_id = str(record["source_table_id"])
        refined_path = record["refined_path"]
        assert isinstance(refined_path, Path)

        for row_number, row in enumerate(rows, start=1):
            assert isinstance(row, dict)
            base = {
                "source_table_id": table_id,
                "source_file": refined_path.name,
                "table_kind": str(record["table_kind"]),
                "source_row_number": str(row_number),
                "calendar_year": calendar_year(row),
                "tax_return_year": tax_return_year(row),
                "geographic_scope": geographic_scope(row),
                "source_block": source_block(row, table_id),
                "bracket_code": bracket_code(row),
                "bracket_order": bracket_order(row),
            }
            for field in fields:
                value = clean(row.get(field))
                if value:
                    rows_out.append({**base, "field_name": field, "field_value": value})

    write_csv(
        output_path,
        [
            "source_table_id",
            "source_file",
            "table_kind",
            "source_row_number",
            "calendar_year",
            "tax_return_year",
            "geographic_scope",
            "source_block",
            "bracket_code",
            "bracket_order",
            "field_name",
            "field_value",
        ],
        rows_out,
    )
    return len(rows_out)


def write_data_dictionary(
    brackets: list[dict[str, str]],
    totals: list[dict[str, str]],
    output_path: Path,
) -> None:
    counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in brackets:
        for field, value in row.items():
            if clean(value):
                counts[field]["brackets_non_empty"] += 1
    for row in totals:
        for field, value in row.items():
            if clean(value):
                counts[field]["totals_non_empty"] += 1

    dictionary_rows = []
    for field in sorted(counts):
        present_in = []
        if counts[field]["brackets_non_empty"]:
            present_in.append("brackets")
        if counts[field]["totals_non_empty"]:
            present_in.append("totals")
        dictionary_rows.append(
            {
                "field_name": field,
                "present_in": " | ".join(present_in),
                "brackets_non_empty": str(counts[field]["brackets_non_empty"]),
                "totals_non_empty": str(counts[field]["totals_non_empty"]),
                "description": "",
            }
        )

    write_csv(
        output_path,
        [
            "field_name",
            "present_in",
            "brackets_non_empty",
            "totals_non_empty",
            "description",
        ],
        dictionary_rows,
    )


def build_data_package(
    source_root: Path | None = None,
    refined_dir: Path = DEFAULT_REFINED_EXTRACTIONS_DIR,
    refined_manifest: Path = DEFAULT_REFINED_MANIFEST,
    refined_long: Path = DEFAULT_REFINED_LONG,
    trusted_brackets: Path = DEFAULT_TRUSTED_BRACKETS,
    trusted_totals: Path = DEFAULT_TRUSTED_TOTALS,
    trusted_dictionary: Path = DEFAULT_TRUSTED_DICTIONARY,
) -> dict[str, int]:
    actual_source_root = source_root_for_build(source_root, refined_dir)
    records = load_or_copy_extractions(actual_source_root, refined_dir)
    manifest_rows = write_manifest(records, refined_manifest)

    bracket_fields, bracket_rows = build_combined_rows(
        records,
        {"bracket_distribution", "above_threshold_distribution"},
    )
    total_fields, total_rows = build_combined_rows(records, {"total"})
    write_csv(trusted_brackets, bracket_fields, bracket_rows)
    write_csv(trusted_totals, total_fields, total_rows)
    long_value_count = write_long_values(records, refined_long)
    write_data_dictionary(bracket_rows, total_rows, trusted_dictionary)

    return {
        "source_tables": len(records),
        "manifest_rows": len(manifest_rows),
        "bracket_rows": len(bracket_rows),
        "total_rows": len(total_rows),
        "long_values": long_value_count,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the repository data package from extracted IRPF CSV tables."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=None,
        help=(
            "Directory containing extracted irpf_*.csv files. Defaults to the local "
            "research workspace when present, otherwise data/refined/extractions."
        ),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_data_package(source_root=args.source_root)
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
