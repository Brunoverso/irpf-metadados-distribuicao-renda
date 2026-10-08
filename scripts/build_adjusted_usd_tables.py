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
DEFAULT_EXCHANGE_AVERAGE_SERIES_ID = 3694
DEFAULT_EXCHANGE_END_PERIOD_SERIES_ID = 3692
DEFAULT_HISTORICAL_EXCHANGE_SERIES_ID = 3690
DEFAULT_EXCHANGE_START_YEAR = 1943
DEFAULT_EXCHANGE_END_YEAR = 2025
DEFAULT_HISTORICAL_EXCHANGE_START_YEAR = 1901
DEFAULT_HISTORICAL_EXCHANGE_END_YEAR = 1941

BCB_SERIES_URL = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{series_id}/dados"
FRED_CPI_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"

DEFAULT_RAW_MACRO_DIR = ROOT / "data" / "raw" / "macro"
DEFAULT_REFINED_MACRO_DIR = ROOT / "data" / "refined" / "macro"
DEFAULT_TRUSTED_DIR = ROOT / "data" / "trusted"

DEFAULT_EXCHANGE_AVERAGE_CSV = DEFAULT_RAW_MACRO_DIR / "bcb_sgs_3694_usd_exchange_annual.csv"
DEFAULT_EXCHANGE_END_PERIOD_CSV = DEFAULT_RAW_MACRO_DIR / "bcb_sgs_3692_usd_exchange_end_period_annual.csv"
DEFAULT_HISTORICAL_EXCHANGE_CSV = DEFAULT_RAW_MACRO_DIR / "bcb_sgs_3690_usd_exchange_mil_reis_end_period_annual.csv"
DEFAULT_CPIAUCSL_CSV = DEFAULT_RAW_MACRO_DIR / "fred_cpiaucsl_monthly.csv"
DEFAULT_CPIAUCNS_CSV = DEFAULT_RAW_MACRO_DIR / "fred_cpiaucns_monthly.csv"
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
    "exchange_rate_reported_value",
    "exchange_rate_reported_unit",
    "exchange_rate_unit_adjustment_multiplier",
    "exchange_rate_unit_adjustment_note",
    "exchange_rate_series_id",
    "exchange_rate_series_name",
    "exchange_rate_timing",
    "exchange_rate_source",
    "cpi_series_id",
    "cpi_series_name",
    "cpi_seasonal_adjustment",
    "cpi_source_year_avg",
    "cpi_source_month_count",
    "cpi_target_year",
    "cpi_target_year_avg",
    "cpi_target_month_count",
    "cpi_target_status",
    "usd_inflation_factor_to_target_year",
    "field_value_usd_nominal",
    "field_value_usd_2026",
    "conversion_method",
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
    try:
        completed = subprocess.run(
            [
                "curl",
                "-L",
                "-sS",
                "--connect-timeout",
                "20",
                "--max-time",
                str(timeout),
                "-A",
                "irpf-metadados-distribuicao-renda/1.0",
                url,
            ],
            check=True,
            capture_output=True,
        )
        if completed.stdout:
            return completed.stdout
    except Exception:
        pass

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
    series_name: str,
    unit: str,
    timing: str,
    value_scale: Decimal = Decimal("1"),
) -> int:
    url = bcb_url(series_id, start_year, end_year)
    data = get_json_url(url)
    rows = []
    for item in data:
        observation_date = datetime.strptime(item["data"], "%d/%m/%Y").date()
        api_value = decimal_or_none(item["valor"])
        if api_value is None:
            continue
        value = api_value * value_scale
        rows.append(
            {
                "date": observation_date.isoformat(),
                "year": str(observation_date.year),
                "exchange_rate_domestic_currency_per_usd": decimal_to_csv(value),
                "exchange_rate_api_value": clean(item["valor"]),
                "exchange_rate_api_value_scale": decimal_to_csv(value_scale),
                "series_id": str(series_id),
                "series_name": series_name,
                "unit": unit,
                "timing": timing,
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
            "exchange_rate_api_value",
            "exchange_rate_api_value_scale",
            "series_id",
            "series_name",
            "unit",
            "timing",
            "source_url",
            "downloaded_at",
        ],
        rows,
    )
    return len(rows)


def refresh_cpi_csv(
    output_path: Path,
    series_id: str,
    series_name: str,
    seasonal_adjustment: str,
) -> int:
    source_url = FRED_CPI_URL.format(series_id=series_id)
    payload = get_url(source_url)
    text = payload.decode("utf-8-sig")
    lines = text.splitlines()
    reader = csv.DictReader(lines)
    rows = []
    for item in reader:
        value = clean(item.get(series_id))
        if not value or value == ".":
            continue
        observation_date = datetime.strptime(item["observation_date"], "%Y-%m-%d").date()
        rows.append(
            {
                "date": observation_date.isoformat(),
                "year": str(observation_date.year),
                "month": str(observation_date.month),
                "cpi_index_1982_1984_100": value,
                "series_id": series_id,
                "series_name": series_name,
                "seasonal_adjustment": seasonal_adjustment,
                "unit": "Index 1982-1984=100",
                "source_url": source_url,
                "downloaded_at": date.today().isoformat(),
            }
        )
    write_csv(
        output_path,
        [
            "date",
            "year",
            "month",
            "cpi_index_1982_1984_100",
            "series_id",
            "series_name",
            "seasonal_adjustment",
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


def load_exchange_by_year(
    exchange_csv: Path,
    method_prefix: str,
) -> dict[int, dict[str, object]]:
    rows = read_csv(exchange_csv)
    by_year: dict[int, dict[str, object]] = {}
    for row in rows:
        year_text = clean(row.get("year"))
        if not year_text.isdigit():
            continue
        value = decimal_or_none(row.get("exchange_rate_domestic_currency_per_usd"))
        if value is None:
            continue
        by_year[int(year_text)] = {
            "value": value,
            "method_prefix": method_prefix,
            "exchange_rate_reported_value": decimal_to_csv(value),
            "exchange_rate_reported_unit": clean(row.get("unit")),
            "exchange_rate_series_id": clean(row.get("series_id")),
            "exchange_rate_series_name": clean(row.get("series_name")),
            "exchange_rate_timing": clean(row.get("timing")),
            "exchange_rate_source": clean(row.get("source_url")),
        }
    return by_year


def cpi_value_from_row(row: dict[str, str]) -> Decimal | None:
    for field in (
        "cpi_index_1982_1984_100",
        "cpiaucsl_index_1982_1984_100",
        "cpiaucns_index_1982_1984_100",
    ):
        value = decimal_or_none(row.get(field))
        if value is not None:
            return value
    return None


def load_cpi_by_year(cpi_csv: Path) -> dict[int, dict[str, object]]:
    rows = read_csv(cpi_csv)
    values_by_year: dict[int, list[Decimal]] = defaultdict(list)
    meta_by_year: dict[int, dict[str, str]] = {}
    for row in rows:
        year_text = clean(row.get("year"))
        if not year_text.isdigit():
            continue
        value = cpi_value_from_row(row)
        if value is None:
            continue
        year = int(year_text)
        values_by_year[year].append(value)
        meta_by_year[year] = {
            "cpi_series_id": clean(row.get("series_id")),
            "cpi_series_name": clean(row.get("series_name")),
            "cpi_seasonal_adjustment": clean(row.get("seasonal_adjustment")),
            "cpi_source": clean(row.get("source_url")),
        }

    by_year: dict[int, dict[str, object]] = {}
    for year, values in values_by_year.items():
        avg = annual_average(values)
        if avg is None:
            continue
        by_year[year] = {
            **meta_by_year.get(year, {}),
            "value": avg,
            "month_count": len(values),
        }
    return by_year


def choose_exchange(
    year: int,
    average_exchange: dict[int, dict[str, object]],
    historical_exchange: dict[int, dict[str, object]],
    end_period_exchange: dict[int, dict[str, object]],
) -> dict[str, object] | None:
    if year in average_exchange:
        return average_exchange[year]
    if year in historical_exchange:
        return historical_exchange[year]
    if year in end_period_exchange:
        return end_period_exchange[year]
    return None


def choose_cpi(
    year: int,
    cpiaucsl: dict[int, dict[str, object]],
    cpiaucns: dict[int, dict[str, object]],
) -> dict[str, object] | None:
    if year in cpiaucsl:
        return cpiaucsl[year]
    if year in cpiaucns:
        return cpiaucns[year]
    return None


def factor_conversion_note(row: dict[str, str]) -> str:
    method = clean(row.get("conversion_method"))
    status = clean(row.get("conversion_status"))
    cpi = clean(row.get("cpi_series_id"))
    timing = clean(row.get("exchange_rate_timing"))
    unit = clean(row.get("exchange_rate_reported_unit"))

    notes = []
    if "missing_exchange_rate" not in status and "missing_cpi" not in status:
        notes.append(
            "Converted from nominal domestic currency to nominal USD with the listed exchange rate, "
            f"then to target-year USD with {cpi}."
        )
    if timing == "annual_end_period":
        notes.append("Exchange rate is end-of-period rather than annual average.")
    if unit == "1 mil-reis/US$":
        notes.append(
            "BCB SGS 3690 is reported in mil-reis per US dollar; rows stored in reis are adjusted by 1000 during conversion."
        )
    if "missing_exchange_rate" in status:
        notes.append("No exchange-rate series is available for the source year under the current method.")
    if "missing_cpi_source_year" in status:
        notes.append("No U.S. CPI annual average is available for the source year.")
    if "missing_cpi_target_year" in status:
        notes.append("No U.S. CPI annual average is available for the target year.")
    if "partial_cpi_target_year" in status:
        notes.append("Target-year CPI uses the months available so far.")
    if method and "missing_exchange_rate" in status and not method.startswith("missing_exchange"):
        notes.append(f"Candidate method would be {method} if an exchange rate were available.")
    return " ".join(notes)


def build_conversion_factors(
    exchange_average_csv: Path,
    exchange_end_period_csv: Path,
    historical_exchange_csv: Path,
    cpiaucsl_csv: Path,
    cpiaucns_csv: Path,
    output_csv: Path,
    target_year: int,
    required_years: set[int],
) -> dict[int, dict[str, str]]:
    average_exchange = load_exchange_by_year(exchange_average_csv, "bcb_3694")
    end_period_exchange = load_exchange_by_year(exchange_end_period_csv, "bcb_3692_end_period")
    historical_exchange = load_exchange_by_year(historical_exchange_csv, "bcb_3690_end_period")
    cpiaucsl = load_cpi_by_year(cpiaucsl_csv)
    cpiaucns = load_cpi_by_year(cpiaucns_csv)

    exchange_years = set(average_exchange) | set(end_period_exchange) | set(historical_exchange)
    cpi_years = set(cpiaucsl) | set(cpiaucns)
    all_years = sorted(required_years | exchange_years | cpi_years | {target_year})
    factor_rows: list[dict[str, str]] = []
    factors: dict[int, dict[str, str]] = {}
    for year in all_years:
        exchange_row = choose_exchange(year, average_exchange, historical_exchange, end_period_exchange)
        cpi_row = choose_cpi(year, cpiaucsl, cpiaucns)

        exchange = exchange_row.get("value") if exchange_row else None
        cpi = cpi_row.get("value") if cpi_row else None
        cpi_series_id = clean(cpi_row.get("cpi_series_id")) if cpi_row else ""
        if not cpi_series_id:
            cpi_series_id = "CPIAUCNS" if year < 1947 else "CPIAUCSL"
        target_cpi_row = None
        if cpi_series_id == "CPIAUCSL":
            target_cpi_row = cpiaucsl.get(target_year)
        elif cpi_series_id == "CPIAUCNS":
            target_cpi_row = cpiaucns.get(target_year)
        cpi_meta_row = cpi_row or target_cpi_row

        target_cpi = target_cpi_row.get("value") if target_cpi_row else None
        source_month_count = int(cpi_row.get("month_count", 0)) if cpi_row else 0
        target_month_count = int(target_cpi_row.get("month_count", 0)) if target_cpi_row else 0
        target_status = "complete" if target_month_count == 12 else "partial"
        inflation_factor = None
        if cpi is not None and target_cpi is not None:
            assert isinstance(cpi, Decimal)
            assert isinstance(target_cpi, Decimal)
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

        exchange_prefix = clean(exchange_row.get("method_prefix")) if exchange_row else "missing_exchange"
        if cpi_series_id:
            conversion_method = f"{exchange_prefix}_{cpi_series_id.lower()}"
        else:
            conversion_method = f"{exchange_prefix}_missing_cpi"

        row = {
            "year": str(year),
            "conversion_method": conversion_method,
            "exchange_rate_domestic_currency_per_usd": decimal_to_csv(exchange if isinstance(exchange, Decimal) else None),
            "exchange_rate_reported_value": clean(exchange_row.get("exchange_rate_reported_value")) if exchange_row else "",
            "exchange_rate_reported_unit": clean(exchange_row.get("exchange_rate_reported_unit")) if exchange_row else "",
            "exchange_rate_series_id": clean(exchange_row.get("exchange_rate_series_id")) if exchange_row else "",
            "exchange_rate_series_name": clean(exchange_row.get("exchange_rate_series_name")) if exchange_row else "",
            "exchange_rate_timing": clean(exchange_row.get("exchange_rate_timing")) if exchange_row else "",
            "exchange_rate_source": clean(exchange_row.get("exchange_rate_source")) if exchange_row else "",
            "cpi_series_id": cpi_series_id,
            "cpi_series_name": clean(cpi_meta_row.get("cpi_series_name")) if cpi_meta_row else "",
            "cpi_seasonal_adjustment": clean(cpi_meta_row.get("cpi_seasonal_adjustment")) if cpi_meta_row else "",
            "cpi_annual_avg": decimal_to_csv(cpi if isinstance(cpi, Decimal) else None),
            "cpi_month_count": str(source_month_count),
            "cpi_target_year": str(target_year),
            "cpi_target_annual_avg": decimal_to_csv(target_cpi if isinstance(target_cpi, Decimal) else None),
            "cpi_target_month_count": str(target_month_count),
            "cpi_target_status": target_status,
            "usd_inflation_factor_to_target_year": decimal_to_csv(inflation_factor),
            "conversion_status": " | ".join(status_parts),
        }
        row["conversion_note"] = factor_conversion_note(row)
        factor_rows.append(row)
        factors[year] = row

    write_csv(
        output_csv,
        [
            "year",
            "conversion_method",
            "exchange_rate_domestic_currency_per_usd",
            "exchange_rate_reported_value",
            "exchange_rate_reported_unit",
            "exchange_rate_series_id",
            "exchange_rate_series_name",
            "exchange_rate_timing",
            "exchange_rate_source",
            "cpi_series_id",
            "cpi_series_name",
            "cpi_seasonal_adjustment",
            "cpi_annual_avg",
            "cpi_month_count",
            "cpi_target_year",
            "cpi_target_annual_avg",
            "cpi_target_month_count",
            "cpi_target_status",
            "usd_inflation_factor_to_target_year",
            "conversion_status",
            "conversion_note",
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


def effective_exchange_rate_for_row(
    factor: dict[str, str],
    source_row: dict[str, str],
) -> tuple[Decimal | None, Decimal, str]:
    exchange = decimal_or_none(factor.get("exchange_rate_domestic_currency_per_usd"))
    if exchange is None:
        return None, Decimal("1"), ""

    unit = clean(factor.get("exchange_rate_reported_unit")).lower()
    currency = clean(source_row.get("moeda")).lower()
    if unit == "1 mil-reis/us$" and currency == "reis":
        return (
            exchange * Decimal("1000"),
            Decimal("1000"),
            "BCB SGS 3690 reports mil-reis per US dollar; applied exchange rate was multiplied by 1000 because this row is stored in reis.",
        )
    return exchange, Decimal("1"), ""


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
        exchange, exchange_adjustment, exchange_adjustment_note = effective_exchange_rate_for_row(factor, row)
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
                    "exchange_rate_domestic_currency_per_usd": decimal_to_csv(exchange),
                    "exchange_rate_reported_value": clean(factor.get("exchange_rate_reported_value")),
                    "exchange_rate_reported_unit": clean(factor.get("exchange_rate_reported_unit")),
                    "exchange_rate_unit_adjustment_multiplier": decimal_to_csv(exchange_adjustment),
                    "exchange_rate_unit_adjustment_note": exchange_adjustment_note,
                    "exchange_rate_series_id": clean(factor.get("exchange_rate_series_id")),
                    "exchange_rate_series_name": clean(factor.get("exchange_rate_series_name")),
                    "exchange_rate_timing": clean(factor.get("exchange_rate_timing")),
                    "exchange_rate_source": clean(factor.get("exchange_rate_source")),
                    "cpi_series_id": clean(factor.get("cpi_series_id")),
                    "cpi_series_name": clean(factor.get("cpi_series_name")),
                    "cpi_seasonal_adjustment": clean(factor.get("cpi_seasonal_adjustment")),
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
                    "conversion_method": clean(factor.get("conversion_method")),
                    "conversion_status": " | ".join(status_parts),
                    "conversion_note": clean(factor.get("conversion_note")),
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
    exchange_average_series_id: int = DEFAULT_EXCHANGE_AVERAGE_SERIES_ID,
    exchange_end_period_series_id: int = DEFAULT_EXCHANGE_END_PERIOD_SERIES_ID,
    historical_exchange_series_id: int = DEFAULT_HISTORICAL_EXCHANGE_SERIES_ID,
    exchange_start_year: int = DEFAULT_EXCHANGE_START_YEAR,
    exchange_end_year: int = DEFAULT_EXCHANGE_END_YEAR,
    historical_exchange_start_year: int = DEFAULT_HISTORICAL_EXCHANGE_START_YEAR,
    historical_exchange_end_year: int = DEFAULT_HISTORICAL_EXCHANGE_END_YEAR,
    exchange_average_csv: Path = DEFAULT_EXCHANGE_AVERAGE_CSV,
    exchange_end_period_csv: Path = DEFAULT_EXCHANGE_END_PERIOD_CSV,
    historical_exchange_csv: Path = DEFAULT_HISTORICAL_EXCHANGE_CSV,
    cpiaucsl_csv: Path = DEFAULT_CPIAUCSL_CSV,
    cpiaucns_csv: Path = DEFAULT_CPIAUCNS_CSV,
    factors_csv: Path = DEFAULT_FACTORS_CSV,
    brackets_input: Path = DEFAULT_BRACKETS_INPUT,
    totals_input: Path = DEFAULT_TOTALS_INPUT,
    brackets_output: Path = DEFAULT_BRACKETS_OUTPUT,
    totals_output: Path = DEFAULT_TOTALS_OUTPUT,
) -> dict[str, int]:
    stats: dict[str, int] = {}
    if refresh_macro:
        stats["exchange_average_rows"] = refresh_exchange_csv(
            exchange_average_csv,
            exchange_average_series_id,
            exchange_start_year,
            exchange_end_year,
            "Taxa de cambio - Livre - Dolar americano (venda) - Media de periodo - anual",
            "unidade monetaria corrente por US$",
            "annual_period_average",
        )
        stats["exchange_end_period_rows"] = refresh_exchange_csv(
            exchange_end_period_csv,
            exchange_end_period_series_id,
            exchange_start_year,
            exchange_end_year,
            "Taxa de cambio - Livre - Dolar americano (venda) - Fim de periodo - anual",
            "unidade monetaria corrente por US$",
            "annual_end_period",
        )
        stats["historical_exchange_rows"] = refresh_exchange_csv(
            historical_exchange_csv,
            historical_exchange_series_id,
            historical_exchange_start_year,
            historical_exchange_end_year,
            "Taxa de cambio - Livre - Dolar americano - Fim de periodo",
            "1 mil-reis/US$",
            "annual_end_period",
            value_scale=Decimal("0.001"),
        )
        stats["cpiaucsl_rows"] = refresh_cpi_csv(
            cpiaucsl_csv,
            "CPIAUCSL",
            "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
            "seasonally_adjusted",
        )
        stats["cpiaucns_rows"] = refresh_cpi_csv(
            cpiaucns_csv,
            "CPIAUCNS",
            "Consumer Price Index for All Urban Consumers: All Items in U.S. City Average",
            "not_seasonally_adjusted",
        )

    macro_inputs = (
        exchange_average_csv,
        exchange_end_period_csv,
        historical_exchange_csv,
        cpiaucsl_csv,
        cpiaucns_csv,
    )
    missing_inputs = [path for path in macro_inputs if not path.exists()]
    if missing_inputs:
        missing = ", ".join(path.as_posix() for path in missing_inputs)
        raise FileNotFoundError(f"missing macro input(s): {missing}. Run with --refresh-macro first.")

    years = required_years_from_tables([brackets_input, totals_input])
    factors = build_conversion_factors(
        exchange_average_csv,
        exchange_end_period_csv,
        historical_exchange_csv,
        cpiaucsl_csv,
        cpiaucns_csv,
        factors_csv,
        target_year,
        years,
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
