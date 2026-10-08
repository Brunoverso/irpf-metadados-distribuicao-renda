from __future__ import annotations

import argparse
import csv
import json
import subprocess
import time
from collections import Counter, defaultdict
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, getcontext
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


getcontext().prec = 40

ROOT = Path(__file__).resolve().parents[1]

DEFAULT_TARGET_YEAR = 2026
DEFAULT_EXCHANGE_SERIES_ID = 3694
DEFAULT_EXCHANGE_START_YEAR = 1943
DEFAULT_EXCHANGE_END_YEAR = 2025

BCB_SERIES_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados"
FRED_CPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=CPIAUCSL"

DEFAULT_RAW_MACRO_DIR = ROOT / "data" / "raw" / "macro"
DEFAULT_REFINED_MACRO_DIR = ROOT / "data" / "refined" / "macro"
DEFAULT_TRUSTED_DIR = ROOT / "data" / "trusted"

DEFAULT_EXCHANGE_CSV = DEFAULT_RAW_MACRO_DIR / "bcb_sgs_3694_usd_exchange_annual.csv"
DEFAULT_CPI_CSV = DEFAULT_RAW_MACRO_DIR / "fred_cpiaucsl_monthly.csv"
DEFAULT_FACTORS_CSV = DEFAULT_REFINED_MACRO_DIR / "usd_2026_conversion_factors.csv"
DEFAULT_BRACKETS_INPUT = DEFAULT_TRUSTED_DIR / "irpf_distribution_brackets_all_sources.csv"
DEFAULT_TOTALS_INPUT = DEFAULT_TRUSTED_DIR / "irpf_distribution_totals_all_sources.csv"
DEFAULT_BRACKETS_OUTPUT = DEFAULT_TRUSTED_DIR / "irpf_distribution_bracket_values_usd_2026.csv"
DEFAULT_TOTALS_OUTPUT = DEFAULT_TRUSTED_DIR / "irpf_distribution_total_values_usd_2026.csv"

META_FIELDS = [
    "source_table_id",
    "source_file",
    "table_kind",
    "source_row_number",
    "calendar_year",
    "tax_return_year",
    "geographic_scope",
    "source_block",
    "moeda",
    "unidade_monetaria_agregados",
    "unidade_limites_faixa",
    "tipo_rendimento",
    "tipo_rendimento_faixa",
    "fonte",
    "url_fonte",
    "arquivo_fonte",
    "pagina_pdf",
    "pagina_impressa",
    "quadro",
    "observacao",
]

OUTPUT_FIELDS = [
    "dataset_kind",
    *META_FIELDS,
    "field_name",
    "field_value_original",
    "field_unit_multiplier_to_domestic_currency",
    "field_value_domestic_currency_units",
    "exchange_rate_domestic_currency_per_usd",
    "exchange_rate_series_id",
    "exchange_rate_source",
    "cpi_source_year_avg",
    "cpi_source_month_count",
    "cpi_target_year",
    "cpi_target_year_avg",
    "cpi_target_month_count",
    "cpi_target_status",
    "usd_inflation_factor_to_target_year",
    "field_value_usd_nominal",
    "field_value_usd_2026",
    "conversion_status",
    "conversion_note",
]

TEXT_OR_ID_TOKENS = (
    "arquivo",
    "url",
    "fonte",
    "pagina",
    "quadro",
    "tabela",
    "validacao",
    "observacao",
    "metodo",
    "codigo",
    "ordem",
    "linha",
    "linhas_",
    "folha",
    "aba_",
    "source_",
    "calendar_",
    "tax_return",
)

COUNT_TOKENS = (
    "pessoas",
    "declarantes",
    "declaracoes",
    "contribuintes",
    "dependentes",
    "numero_",
    "quantidade",
    "row_count",
    "column_count",
    "ufs_",
    "tipos_formulario",
)

PERCENT_OR_INDEX_TOKENS = (
    "percentual",
    "aliquota",
    "gini",
)

MONEY_TOKENS = (
    "renda",
    "rendimento",
    "imposto",
    "abatimento",
    "abatimentos",
    "deducao",
    "deducoes",
    "base_calculo",
    "bens",
    "dividas",
    "doacoes",
    "valor",
    "valores",
    "limite_inferior",
    "limite_superior",
    "desconto",
    "retencao",
    "incentivo",
    "incentivos",
)


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def decimal_or_none(value: str | None) -> Decimal | None:
    value = clean(value)
    if not value:
        return None
    if ":" in value or "$" in value:
        return None
    value = value.replace(" ", "")
    value = value.replace(",", ".") if value.count(",") == 1 and "." not in value else value
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def decimal_to_csv(value: Decimal | None, places: str = "0.000001") -> str:
    if value is None:
        return ""
    quantum = Decimal(places)
    return format(value.quantize(quantum), "f")


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


def get_url(url: str, timeout: int = 120, attempts: int = 3) -> bytes:
    request = Request(
        url,
        headers={
            "User-Agent": "irpf-metadados-distribuicao-renda/1.0",
            "Accept": "text/csv, application/json, */*",
        },
    )
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return response.read()
        except Exception as exc:
            last_error = exc
            if attempt < attempts:
                time.sleep(attempt * 2)
    assert last_error is not None
    try:
        completed = subprocess.run(
            ["curl", "-L", "-sS", "--max-time", str(timeout), url],
            check=True,
            capture_output=True,
        )
        return completed.stdout
    except Exception:
        raise last_error


def get_json_url(url: str, attempts: int = 3) -> object:
    last_text = ""
    for attempt in range(1, attempts + 1):
        payload = get_url(url)
        text = payload.decode("utf-8", errors="replace").strip()
        last_text = text[:500]
        if text.startswith("[") or text.startswith("{"):
            return json.loads(text)
        if attempt < attempts:
            time.sleep(attempt * 2)
    raise ValueError(f"expected JSON response from {url}, got: {last_text}")


def bcb_url(series_id: int, start_year: int, end_year: int) -> str:
    params = {
        "formato": "json",
        "dataInicial": f"01/01/{start_year}",
        "dataFinal": f"31/12/{end_year}",
    }
    return f"{BCB_SERIES_URL.format(series_id=series_id)}?{urlencode(params)}"


def refresh_exchange_csv(
    output_path: Path,
    series_id: int,
    start_year: int,
    end_year: int,
) -> int:
    url = bcb_url(series_id, start_year, end_year)
    data = get_json_url(url)
    rows = []
    for item in data:
        observation_date = datetime.strptime(item["data"], "%d/%m/%Y").date()
        rows.append(
            {
                "date": observation_date.isoformat(),
                "year": str(observation_date.year),
                "exchange_rate_domestic_currency_per_usd": clean(item["valor"]),
                "series_id": str(series_id),
                "series_name": "Taxa de cambio - Livre - Dolar americano (venda) - Media de periodo - anual",
                "unit": "unidade monetaria corrente por US$",
                "source_url": url,
                "downloaded_at": date.today().isoformat(),
            }
        )
    write_csv(
        output_path,
        [
            "date",
            "year",
            "exchange_rate_domestic_currency_per_usd",
            "series_id",
            "series_name",
            "unit",
            "source_url",
            "downloaded_at",
        ],
        rows,
    )
    return len(rows)


def refresh_cpi_csv(output_path: Path) -> int:
    payload = get_url(FRED_CPI_URL)
    text = payload.decode("utf-8-sig")
    lines = text.splitlines()
    reader = csv.DictReader(lines)
    rows = []
    for item in reader:
        value = clean(item.get("CPIAUCSL"))
        if not value or value == ".":
            continue
        observation_date = datetime.strptime(item["observation_date"], "%Y-%m-%d").date()
        rows.append(
            {
                "date": observation_date.isoformat(),
                "year": str(observation_date.year),
                "month": str(observation_date.month),
                "cpiaucsl_index_1982_1984_100": value,
                "series_id": "CPIAUCSL",
                "series_name": "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
                "unit": "Index 1982-1984=100",
                "source_url": FRED_CPI_URL,
                "downloaded_at": date.today().isoformat(),
            }
        )
    write_csv(
        output_path,
        [
            "date",
            "year",
            "month",
            "cpiaucsl_index_1982_1984_100",
            "series_id",
            "series_name",
            "unit",
            "source_url",
            "downloaded_at",
        ],
        rows,
    )
    return len(rows)


def annual_average(values: list[Decimal]) -> Decimal | None:
    if not values:
        return None
    return sum(values) / Decimal(len(values))


def build_conversion_factors(
    exchange_csv: Path,
    cpi_csv: Path,
    output_csv: Path,
    target_year: int,
    required_years: set[int],
    exchange_series_id: int,
) -> dict[int, dict[str, str]]:
    exchange_rows = read_csv(exchange_csv)
    cpi_rows = read_csv(cpi_csv)

    exchange_by_year: dict[int, Decimal] = {}
    exchange_source_by_year: dict[int, str] = {}
    for row in exchange_rows:
        year = int(row["year"])
        value = decimal_or_none(row["exchange_rate_domestic_currency_per_usd"])
        if value is not None:
            exchange_by_year[year] = value
            exchange_source_by_year[year] = clean(row.get("source_url"))

    cpi_values_by_year: dict[int, list[Decimal]] = defaultdict(list)
    for row in cpi_rows:
        value = decimal_or_none(row.get("cpiaucsl_index_1982_1984_100"))
        if value is not None:
            cpi_values_by_year[int(row["year"])].append(value)

    cpi_avg_by_year = {
        year: annual_average(values)
        for year, values in cpi_values_by_year.items()
    }
    target_cpi = cpi_avg_by_year.get(target_year)
    target_month_count = len(cpi_values_by_year.get(target_year, []))
    target_status = "complete" if target_month_count == 12 else "partial"

    all_years = sorted(required_years | set(exchange_by_year) | set(cpi_avg_by_year) | {target_year})
    factor_rows: list[dict[str, str]] = []
    factors: dict[int, dict[str, str]] = {}
    for year in all_years:
        exchange = exchange_by_year.get(year)
        cpi = cpi_avg_by_year.get(year)
        source_month_count = len(cpi_values_by_year.get(year, []))
        inflation_factor = None
        if cpi is not None and target_cpi is not None:
            inflation_factor = target_cpi / cpi

        status_parts = []
        if exchange is None:
            status_parts.append("missing_exchange_rate")
        if cpi is None:
            status_parts.append("missing_cpi_source_year")
        if target_cpi is None:
            status_parts.append("missing_cpi_target_year")
        if target_status == "partial":
            status_parts.append("partial_cpi_target_year")
        if not status_parts:
            status_parts.append("ok")

        row = {
            "year": str(year),
            "exchange_rate_domestic_currency_per_usd": decimal_to_csv(exchange),
            "exchange_rate_series_id": str(exchange_series_id),
            "exchange_rate_source": exchange_source_by_year.get(year, ""),
            "cpi_annual_avg": decimal_to_csv(cpi),
            "cpi_month_count": str(source_month_count),
            "cpi_target_year": str(target_year),
            "cpi_target_annual_avg": decimal_to_csv(target_cpi),
            "cpi_target_month_count": str(target_month_count),
            "cpi_target_status": target_status,
            "usd_inflation_factor_to_target_year": decimal_to_csv(inflation_factor),
            "conversion_status": " | ".join(status_parts),
        }
        factor_rows.append(row)
        factors[year] = row

    write_csv(
        output_csv,
        [
            "year",
            "exchange_rate_domestic_currency_per_usd",
            "exchange_rate_series_id",
            "exchange_rate_source",
            "cpi_annual_avg",
            "cpi_month_count",
            "cpi_target_year",
            "cpi_target_annual_avg",
            "cpi_target_month_count",
            "cpi_target_status",
            "usd_inflation_factor_to_target_year",
            "conversion_status",
        ],
        factor_rows,
    )
    return factors


def has_any_token(field: str, tokens: tuple[str, ...]) -> bool:
    return any(token in field for token in tokens)


def is_candidate_monetary_field(field: str) -> bool:
    field = field.lower()
    if has_any_token(field, TEXT_OR_ID_TOKENS):
        return False
    if has_any_token(field, COUNT_TOKENS):
        return False
    if has_any_token(field, PERCENT_OR_INDEX_TOKENS):
        return False
    if "_sm_" in field or field.endswith("_sm") or "salario_minimo" in field:
        return False
    return has_any_token(field, MONEY_TOKENS)


def unit_multiplier_from_unit_text(unit_text: str) -> Decimal | None:
    unit_text = unit_text.lower()
    if "salario" in unit_text:
        return None
    if "milhoes" in unit_text or "1.000.000" in unit_text:
        return Decimal("1000000")
    if "mil-reis" in unit_text or "1.000" in unit_text:
        return Decimal("1000")
    if "1,00" in unit_text or "1.00" in unit_text:
        return Decimal("1")
    return None


def infer_multiplier(field: str, row: dict[str, str]) -> Decimal | None:
    field = field.lower()
    if not is_candidate_monetary_field(field):
        return None

    if "_rs_milhoes" in field:
        return Decimal("1000000")
    if "_rs_mil" in field:
        return Decimal("1000")
    if "_rs" in field:
        return Decimal("1")

    for currency_token in ("_ncr", "_cr", "_ncz", "_cz"):
        if f"{currency_token}_mil" in field:
            return Decimal("1000")
        if currency_token in field:
            return Decimal("1")

    if field.endswith("_mil") or "_mil_" in field:
        unit = clean(row.get("unidade_monetaria_agregados"))
        if "mil-reis" in unit.lower() or clean(row.get("moeda")).lower() == "reis":
            return Decimal("1000")

    if field in {"limite_inferior", "limite_superior"}:
        return unit_multiplier_from_unit_text(clean(row.get("unidade_limites_faixa")))

    if field in {"renda_liquida_media", "renda_media_tributavel_rs_torres_calculada"}:
        return Decimal("1")

    return None


def conversion_note(status_parts: list[str]) -> str:
    if status_parts == ["ok"]:
        return "Converted from nominal domestic currency to nominal USD with BCB exchange rate, then to target-year USD with CPIAUCSL."
    notes = []
    if "missing_exchange_rate" in status_parts:
        notes.append("No annual BCB exchange rate for the source year.")
    if "missing_cpi_source_year" in status_parts:
        notes.append("No CPIAUCSL annual average for the source year.")
    if "missing_cpi_target_year" in status_parts:
        notes.append("No CPIAUCSL annual average for the target year.")
    if "partial_cpi_target_year" in status_parts:
        notes.append("Target-year CPI uses the months available so far.")
    return " ".join(notes)


def convert_table_to_long(
    input_csv: Path,
    output_csv: Path,
    dataset_kind: str,
    factors: dict[int, dict[str, str]],
) -> Counter[str]:
    input_rows = read_csv(input_csv)
    output_rows: list[dict[str, str]] = []
    stats: Counter[str] = Counter()

    for row in input_rows:
        year_text = clean(row.get("calendar_year"))
        if not year_text.isdigit():
            continue
        year = int(year_text)
        factor = factors.get(year, {})
        exchange = decimal_or_none(factor.get("exchange_rate_domestic_currency_per_usd"))
        source_cpi = decimal_or_none(factor.get("cpi_annual_avg"))
        target_cpi = decimal_or_none(factor.get("cpi_target_annual_avg"))
        inflation_factor = decimal_or_none(factor.get("usd_inflation_factor_to_target_year"))

        for field, original_value in row.items():
            multiplier = infer_multiplier(field, row)
            if multiplier is None:
                continue
            numeric_value = decimal_or_none(original_value)
            if numeric_value is None:
                continue

            domestic_value = numeric_value * multiplier
            usd_nominal = domestic_value / exchange if exchange else None
            usd_2026 = usd_nominal * inflation_factor if usd_nominal is not None and inflation_factor else None

            status_parts = []
            if exchange is None:
                status_parts.append("missing_exchange_rate")
            if source_cpi is None:
                status_parts.append("missing_cpi_source_year")
            if target_cpi is None:
                status_parts.append("missing_cpi_target_year")
            if clean(factor.get("cpi_target_status")) == "partial":
                status_parts.append("partial_cpi_target_year")
            if not status_parts:
                status_parts.append("ok")
            if usd_nominal is not None:
                stats["nominal_usd_values"] += 1
            if usd_2026 is not None:
                stats["target_year_usd_values"] += 1
            stats["monetary_values"] += 1
            stats["status:" + " | ".join(status_parts)] += 1

            out = {"dataset_kind": dataset_kind}
            for meta_field in META_FIELDS:
                out[meta_field] = clean(row.get(meta_field))
            out.update(
                {
                    "field_name": field,
                    "field_value_original": clean(original_value),
                    "field_unit_multiplier_to_domestic_currency": decimal_to_csv(multiplier),
                    "field_value_domestic_currency_units": decimal_to_csv(domestic_value),
                    "exchange_rate_domestic_currency_per_usd": clean(
                        factor.get("exchange_rate_domestic_currency_per_usd")
                    ),
                    "exchange_rate_series_id": clean(factor.get("exchange_rate_series_id")),
                    "exchange_rate_source": clean(factor.get("exchange_rate_source")),
                    "cpi_source_year_avg": clean(factor.get("cpi_annual_avg")),
                    "cpi_source_month_count": clean(factor.get("cpi_month_count")),
                    "cpi_target_year": clean(factor.get("cpi_target_year")),
                    "cpi_target_year_avg": clean(factor.get("cpi_target_annual_avg")),
                    "cpi_target_month_count": clean(factor.get("cpi_target_month_count")),
                    "cpi_target_status": clean(factor.get("cpi_target_status")),
                    "usd_inflation_factor_to_target_year": clean(
                        factor.get("usd_inflation_factor_to_target_year")
                    ),
                    "field_value_usd_nominal": decimal_to_csv(usd_nominal),
                    "field_value_usd_2026": decimal_to_csv(usd_2026),
                    "conversion_status": " | ".join(status_parts),
                    "conversion_note": conversion_note(status_parts),
                }
            )
            output_rows.append(out)

    write_csv(output_csv, OUTPUT_FIELDS, output_rows)
    stats["rows_written"] = len(output_rows)
    return stats


def required_years_from_tables(paths: list[Path]) -> set[int]:
    years: set[int] = set()
    for path in paths:
        for row in read_csv(path):
            year = clean(row.get("calendar_year"))
            if year.isdigit():
                years.add(int(year))
    return years


def build_adjusted_usd_tables(
    refresh_macro: bool = False,
    target_year: int = DEFAULT_TARGET_YEAR,
    exchange_series_id: int = DEFAULT_EXCHANGE_SERIES_ID,
    exchange_start_year: int = DEFAULT_EXCHANGE_START_YEAR,
    exchange_end_year: int = DEFAULT_EXCHANGE_END_YEAR,
    exchange_csv: Path = DEFAULT_EXCHANGE_CSV,
    cpi_csv: Path = DEFAULT_CPI_CSV,
    factors_csv: Path = DEFAULT_FACTORS_CSV,
    brackets_input: Path = DEFAULT_BRACKETS_INPUT,
    totals_input: Path = DEFAULT_TOTALS_INPUT,
    brackets_output: Path = DEFAULT_BRACKETS_OUTPUT,
    totals_output: Path = DEFAULT_TOTALS_OUTPUT,
) -> dict[str, int]:
    stats: dict[str, int] = {}
    if refresh_macro:
        stats["exchange_rows"] = refresh_exchange_csv(
            exchange_csv,
            exchange_series_id,
            exchange_start_year,
            exchange_end_year,
        )
        stats["cpi_rows"] = refresh_cpi_csv(cpi_csv)

    missing_inputs = [path for path in (exchange_csv, cpi_csv) if not path.exists()]
    if missing_inputs:
        missing = ", ".join(path.as_posix() for path in missing_inputs)
        raise FileNotFoundError(f"missing macro input(s): {missing}. Run with --refresh-macro first.")

    years = required_years_from_tables([brackets_input, totals_input])
    factors = build_conversion_factors(
        exchange_csv,
        cpi_csv,
        factors_csv,
        target_year,
        years,
        exchange_series_id,
    )
    stats["factor_rows"] = len(factors)

    bracket_stats = convert_table_to_long(brackets_input, brackets_output, "bracket", factors)
    total_stats = convert_table_to_long(totals_input, totals_output, "total", factors)
    for key, value in bracket_stats.items():
        stats[f"bracket_{key}"] = value
    for key, value in total_stats.items():
        stats[f"total_{key}"] = value
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build IRPF monetary-value tables converted to nominal USD and target-year USD."
    )
    parser.add_argument(
        "--refresh-macro",
        action="store_true",
        help="Download fresh BCB/FRED macro series before building the adjusted tables.",
    )
    parser.add_argument(
        "--target-year",
        type=int,
        default=DEFAULT_TARGET_YEAR,
        help="Dollar purchasing-power year used for CPI adjustment.",
    )
    parser.add_argument(
        "--exchange-end-year",
        type=int,
        default=DEFAULT_EXCHANGE_END_YEAR,
        help="Final year requested from the BCB annual exchange-rate series when refreshing macro data.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_adjusted_usd_tables(
        refresh_macro=args.refresh_macro,
        target_year=args.target_year,
        exchange_end_year=args.exchange_end_year,
    )
    for key, value in sorted(stats.items()):
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
