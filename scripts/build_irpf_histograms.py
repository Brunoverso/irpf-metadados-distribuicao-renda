from __future__ import annotations

import argparse
import csv
import math
import re
import textwrap
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A3, landscape
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "trusted" / "irpf_distribution_brackets_all_sources.csv"
DEFAULT_OUTPUT_DIR = ROOT / "outputs" / "metadata" / "figures" / "histograms"
DEFAULT_MANIFEST = DEFAULT_OUTPUT_DIR / "irpf_histogram_manifest.csv"
DEFAULT_PDF = DEFAULT_OUTPUT_DIR / "irpf_distribution_histograms.pdf"

SVG_WIDTH = 1280
SVG_HEIGHT = 900
PLOT_LEFT = 100
PLOT_RIGHT = 42
PLOT_TOP = 126
PLOT_BOTTOM = 310

FREQUENCY_FIELDS = [
    ("pessoas_fisicas_notificadas", "Pessoas fisicas notificadas"),
    ("contribuintes_total", "Contribuintes"),
    ("declarantes", "Declarantes"),
    ("declarantes_total", "Declarantes"),
    ("numero_declarantes", "Declarantes"),
    ("numero_declaracoes", "Declaracoes"),
    ("quantidade_declarantes", "Declarantes"),
]

BRACKET_LABEL_FIELDS = [
    "faixa_rendimento_total_sm_mensal_normalizada",
    "faixa_rendimento_total_sm_mensal_publicada",
    "faixa_renda_mensal_publicada",
    "faixa_rendimento_tributavel_anual_rs",
    "faixa_renda_tributavel_anual_rs_mil",
    "faixa_renda_bruta_anual_publicada",
    "faixa_rendimento_bruto_total_ncz",
    "faixa_rendimento_bruto_total_cz",
    "faixa_rendimento_bruto_total_cr",
    "faixa_rendimento_bruto_cr",
    "faixa_renda_liquida_ncr_mil",
    "faixa_renda_liquida_ncr",
    "faixa_renda_liquida_cr_mil",
    "faixa_renda_liquida_cr",
    "faixa_renda_liquida",
]

LIMIT_PAIRS = [
    ("limite_inferior_sm_mensal", "limite_superior_sm_mensal"),
    ("limite_inferior_mensal_rs", "limite_superior_mensal_rs"),
    ("limite_inferior_anual_rs", "limite_superior_anual_rs"),
    ("limite_inferior_anual_rs_publicado", "limite_superior_anual_rs_publicado"),
    ("limite_inferior_rs", "limite_superior_rs"),
    ("limite_inferior_ncz", "limite_superior_ncz"),
    ("limite_inferior_cz", "limite_superior_cz"),
    ("limite_inferior_ncr_mil", "limite_superior_ncr_mil"),
    ("limite_inferior_ncr", "limite_superior_ncr"),
    ("limite_inferior_cr_mil", "limite_superior_cr_mil"),
    ("limite_inferior_cr", "limite_superior_cr"),
    ("limite_inferior", "limite_superior"),
]

MANIFEST_FIELDS = [
    "histogram_id",
    "status",
    "calendar_year",
    "tax_return_year",
    "source_table_id",
    "table_kind",
    "geographic_scope",
    "source_block",
    "row_count",
    "frequency_field",
    "frequency_label",
    "bracket_label_field",
    "x_axis_label",
    "y_axis_label",
    "figure_svg",
    "figure_pdf",
    "fonte",
    "pagina_pdf",
    "pagina_impressa",
    "quadro",
    "note",
]


@dataclass
class HistogramPoint:
    label: str
    full_label: str
    value: float
    order: float


@dataclass
class HistogramSpec:
    histogram_id: str
    calendar_year: str
    tax_return_year: str
    source_table_id: str
    table_kind: str
    geographic_scope: str
    source_block: str
    frequency_field: str
    frequency_label: str
    bracket_label_field: str
    x_axis_label: str
    y_axis_label: str
    title: str
    subtitle: str
    note: str
    fonte: str
    pagina_pdf: str
    pagina_impressa: str
    quadro: str
    points: list[HistogramPoint]
    svg_path: Path


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return str(value).replace("\n", " ").strip()


def ascii_text(value: str) -> str:
    value = clean(value).replace("�", "")
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", value).strip()


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


def number_or_none(value: str | None) -> float | None:
    value = clean(value)
    if not value:
        return None
    value = value.replace(" ", "").replace(",", ".")
    try:
        return float(value)
    except ValueError:
        return None


def first_present(rows: list[dict[str, str]], field: str) -> str:
    for row in rows:
        value = clean(row.get(field))
        if value:
            return value
    return ""


def slugify(value: str, max_length: int = 120) -> str:
    value = ascii_text(value).lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    value = re.sub(r"-+", "-", value)
    return value[:max_length].strip("-") or "histogram"


def group_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("calendar_year")),
        clean(row.get("source_table_id")),
        clean(row.get("source_block")),
        clean(row.get("geographic_scope")),
    )


def sort_key(row: dict[str, str]) -> tuple[float, float]:
    order = number_or_none(row.get("ordem_faixa"))
    if order is None:
        order = number_or_none(row.get("ordem_corte"))
    if order is None:
        order = number_or_none(row.get("source_row_number")) or 0
    row_number = number_or_none(row.get("source_row_number")) or 0
    return (order, row_number)


def choose_frequency_field(rows: list[dict[str, str]]) -> tuple[str, str] | None:
    for field, label in FREQUENCY_FIELDS:
        values = [number_or_none(row.get(field)) for row in rows]
        usable = [value for value in values if value is not None]
        if len(usable) >= max(3, math.ceil(len(rows) * 0.75)):
            return field, label
    return None


def choose_bracket_label_field(rows: list[dict[str, str]]) -> str:
    for field in BRACKET_LABEL_FIELDS:
        non_empty = sum(1 for row in rows if clean(row.get(field)))
        if non_empty >= max(3, math.ceil(len(rows) * 0.75)):
            return field
    return ""


def fallback_bracket_label(row: dict[str, str]) -> str:
    for lower_field, upper_field in LIMIT_PAIRS:
        lower = clean(row.get(lower_field))
        upper = clean(row.get(upper_field))
        top_open = clean(row.get("faixa_topo_aberta")) == "1"
        if lower and upper:
            return f"{lower}-{upper}"
        if lower and top_open:
            return f">{lower}"
        if lower:
            return lower
        if upper:
            return f"<= {upper}"
    return clean(row.get("codigo_faixa")) or clean(row.get("source_row_number"))


def format_count(value: float) -> str:
    if abs(value) >= 1_000_000:
        return f"{value / 1_000_000:.1f}M".replace(".0M", "M")
    if abs(value) >= 1_000:
        return f"{value / 1_000:.0f}k"
    if value == int(value):
        return str(int(value))
    return f"{value:.1f}"


def format_full_count(value: float) -> str:
    if value == int(value):
        return f"{int(value):,}".replace(",", ".")
    return f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def truncate_label(value: str, limit: int = 28) -> str:
    value = ascii_text(value)
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def infer_unit(rows: list[dict[str, str]], label_field: str) -> str:
    if "sm" in label_field:
        return "salarios minimos mensais"
    for field in ("unidade_limites_faixa", "unidade_monetaria_fonte", "unidade_monetaria_agregados", "moeda"):
        value = ascii_text(first_present(rows, field))
        if value:
            return value
    return "unidade publicada pela fonte"


def wrap_svg_text(text: str, max_chars: int) -> list[str]:
    return textwrap.wrap(ascii_text(text), width=max_chars, break_long_words=False) or [""]


def nice_ticks(max_value: float, count: int = 5) -> list[float]:
    if max_value <= 0:
        return [0]
    raw_step = max_value / count
    magnitude = 10 ** math.floor(math.log10(raw_step))
    residual = raw_step / magnitude
    if residual <= 1:
        step = magnitude
    elif residual <= 2:
        step = 2 * magnitude
    elif residual <= 5:
        step = 5 * magnitude
    else:
        step = 10 * magnitude
    top = math.ceil(max_value / step) * step
    ticks = []
    current = 0.0
    while current <= top + step / 2:
        ticks.append(current)
        current += step
    return ticks


def make_histogram_spec(rows: list[dict[str, str]], output_dir: Path) -> tuple[HistogramSpec | None, str, str]:
    table_kind = clean(rows[0].get("table_kind"))
    if table_kind != "bracket_distribution":
        return None, "skipped_not_bracket_distribution", "Only bracket-distribution tables are rendered as histograms."

    frequency = choose_frequency_field(rows)
    if frequency is None:
        return None, "skipped_no_direct_frequency", "No single direct frequency column was identified for this table."

    frequency_field, frequency_label = frequency
    label_field = choose_bracket_label_field(rows)
    sorted_rows = sorted(rows, key=sort_key)
    points: list[HistogramPoint] = []
    for row in sorted_rows:
        value = number_or_none(row.get(frequency_field))
        if value is None:
            continue
        full_label = clean(row.get(label_field)) if label_field else fallback_bracket_label(row)
        points.append(
            HistogramPoint(
                label=truncate_label(full_label),
                full_label=ascii_text(full_label),
                value=value,
                order=sort_key(row)[0],
            )
        )

    if len(points) < 3:
        return None, "skipped_too_few_bins", "Fewer than three usable bins were identified."

    year = clean(rows[0].get("calendar_year"))
    source_table_id = clean(rows[0].get("source_table_id"))
    scope = ascii_text(first_present(rows, "geographic_scope") or first_present(rows, "unidade_geografica"))
    tax_return_year = clean(first_present(rows, "tax_return_year") or first_present(rows, "ano_exercicio"))
    source_block = clean(first_present(rows, "source_block") or first_present(rows, "fonte_bloco"))
    tipo_rendimento = ascii_text(first_present(rows, "tipo_rendimento") or first_present(rows, "tipo_rendimento_faixa"))
    unit = infer_unit(rows, label_field)
    histogram_id = f"irpf_histogram_{year}_{slugify(source_table_id, 86)}"
    svg_path = output_dir / f"{histogram_id}.svg"

    title_parts = [f"IRPF {year}"]
    if scope:
        title_parts.append(scope)
    if tipo_rendimento:
        title_parts.append(tipo_rendimento)
    title = " - ".join(title_parts)
    source = ascii_text(first_present(rows, "fonte"))
    subtitle = source
    if len(subtitle) > 170:
        subtitle = subtitle[:167].rstrip() + "..."

    base_note = f"Eixo X: faixas de renda publicadas pela fonte ({unit}). Eixo Y: {frequency_label.lower()}."
    if scope and scope.lower() != "brasil":
        base_note += f" Serie regional: {scope}."
    observation = ascii_text(first_present(rows, "observacao") or first_present(rows, "observacao_linha"))
    if observation:
        base_note += " " + observation
    if len(base_note) > 360:
        base_note = base_note[:357].rstrip() + "..."

    return (
        HistogramSpec(
            histogram_id=histogram_id,
            calendar_year=year,
            tax_return_year=tax_return_year,
            source_table_id=source_table_id,
            table_kind=table_kind,
            geographic_scope=scope,
            source_block=source_block,
            frequency_field=frequency_field,
            frequency_label=frequency_label,
            bracket_label_field=label_field,
            x_axis_label=f"Faixas de renda publicadas ({unit})",
            y_axis_label=frequency_label,
            title=title,
            subtitle=subtitle,
            note=base_note,
            fonte=source,
            pagina_pdf=clean(first_present(rows, "pagina_pdf") or first_present(rows, "pagina_pdf_tabela")),
            pagina_impressa=clean(first_present(rows, "pagina_impressa") or first_present(rows, "pagina_impressa_tabela")),
            quadro=clean(first_present(rows, "quadro") or first_present(rows, "tabela")),
            points=points,
            svg_path=svg_path,
        ),
        "generated",
        "",
    )


def svg_text(x: float, y: float, text: str, **attrs: str) -> str:
    clean_attrs = {}
    for key, value in attrs.items():
        attr_name = key[:-1] if key.endswith("_") else key
        clean_attrs[attr_name.replace("_", "-")] = value
    attr_text = " ".join(f'{key}="{escape(str(value))}"' for key, value in clean_attrs.items())
    return f'<text x="{x:.1f}" y="{y:.1f}" {attr_text}>{escape(ascii_text(text))}</text>'


def write_svg(spec: HistogramSpec) -> None:
    plot_width = SVG_WIDTH - PLOT_LEFT - PLOT_RIGHT
    plot_height = SVG_HEIGHT - PLOT_TOP - PLOT_BOTTOM
    max_value = max(point.value for point in spec.points)
    ticks = nice_ticks(max_value)
    y_top = ticks[-1] if ticks else max_value
    bar_gap = 5 if len(spec.points) <= 20 else 3
    band = plot_width / len(spec.points)
    bar_width = max(3, band - bar_gap)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">',
        "<style>",
        "text{font-family:Arial,Helvetica,sans-serif;fill:#202124}",
        ".title{font-size:28px;font-weight:700}",
        ".subtitle{font-size:16px;fill:#4a4f55}",
        ".axis{font-size:15px;fill:#30343a}",
        ".tick{font-size:13px;fill:#4a4f55}",
        ".note{font-size:13px;fill:#4a4f55}",
        ".bar{fill:#2f6f9f}",
        ".bar:hover{fill:#c85a28}",
        ".grid{stroke:#d8dde3;stroke-width:1}",
        ".frame{stroke:#7f8790;stroke-width:1;fill:none}",
        "</style>",
        f'<rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="#ffffff"/>',
        svg_text(34, 44, spec.title, class_="title"),
    ]

    for i, line in enumerate(wrap_svg_text(spec.subtitle, 134)[:2]):
        parts.append(svg_text(34, 72 + i * 20, line, class_="subtitle"))

    for tick in ticks:
        y = PLOT_TOP + plot_height - (tick / y_top) * plot_height if y_top else PLOT_TOP + plot_height
        parts.append(f'<line x1="{PLOT_LEFT}" y1="{y:.1f}" x2="{SVG_WIDTH - PLOT_RIGHT}" y2="{y:.1f}" class="grid"/>')
        parts.append(svg_text(PLOT_LEFT - 12, y + 4, format_count(tick), class_="tick", text_anchor="end"))

    parts.append(f'<rect x="{PLOT_LEFT}" y="{PLOT_TOP}" width="{plot_width}" height="{plot_height}" class="frame"/>')

    for index, point in enumerate(spec.points):
        x = PLOT_LEFT + index * band + bar_gap / 2
        height = (point.value / y_top) * plot_height if y_top else 0
        y = PLOT_TOP + plot_height - height
        parts.append(
            f'<rect class="bar" x="{x:.1f}" y="{y:.1f}" width="{bar_width:.1f}" height="{height:.1f}">'
            f"<title>{escape(point.full_label)}: {format_full_count(point.value)}</title></rect>"
        )
        label_x = x + bar_width / 2
        label_y = PLOT_TOP + plot_height + 20
        parts.append(
            f'<text class="tick" transform="translate({label_x:.1f},{label_y:.1f}) rotate(58)" '
            f'text-anchor="start">{escape(point.label)}</text>'
        )

    parts.append(svg_text(SVG_WIDTH / 2, SVG_HEIGHT - 112, spec.x_axis_label, class_="axis", text_anchor="middle"))
    parts.append(
        f'<text class="axis" transform="translate(28,{PLOT_TOP + plot_height / 2:.1f}) rotate(-90)" '
        f'text-anchor="middle">{escape(ascii_text(spec.y_axis_label))}</text>'
    )
    for i, line in enumerate(wrap_svg_text(spec.note, 150)[:3]):
        parts.append(svg_text(34, SVG_HEIGHT - 72 + i * 17, line, class_="note"))
    parts.append("</svg>")

    spec.svg_path.parent.mkdir(parents=True, exist_ok=True)
    spec.svg_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def draw_wrapped_pdf_text(pdf: canvas.Canvas, x: float, y: float, text: str, max_chars: int, leading: float) -> float:
    for line in textwrap.wrap(ascii_text(text), width=max_chars, break_long_words=False):
        pdf.drawString(x, y, line)
        y -= leading
    return y


def draw_pdf_page(pdf: canvas.Canvas, spec: HistogramSpec, page_width: float, page_height: float) -> None:
    left = 72
    right = 42
    top = 116
    bottom = 210
    plot_width = page_width - left - right
    plot_height = page_height - top - bottom
    max_value = max(point.value for point in spec.points)
    ticks = nice_ticks(max_value)
    y_top = ticks[-1] if ticks else max_value
    band = plot_width / len(spec.points)
    bar_gap = 3 if len(spec.points) > 22 else 5
    bar_width = max(2, band - bar_gap)

    pdf.setFillColorRGB(0.12, 0.13, 0.15)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(34, page_height - 44, ascii_text(spec.title)[:150])
    pdf.setFont("Helvetica", 10)
    y = page_height - 67
    y = draw_wrapped_pdf_text(pdf, 34, y, spec.subtitle, 160, 12)

    frame_bottom = bottom
    frame_top = bottom + plot_height
    pdf.setStrokeColorRGB(0.84, 0.86, 0.89)
    pdf.setLineWidth(0.5)
    pdf.setFont("Helvetica", 8)
    for tick in ticks:
        tick_y = frame_bottom + (tick / y_top) * plot_height if y_top else frame_bottom
        pdf.line(left, tick_y, page_width - right, tick_y)
        pdf.setFillColorRGB(0.29, 0.31, 0.34)
        pdf.drawRightString(left - 7, tick_y - 3, format_count(tick))

    pdf.setStrokeColorRGB(0.48, 0.52, 0.56)
    pdf.rect(left, frame_bottom, plot_width, plot_height, stroke=1, fill=0)
    pdf.setFillColorRGB(0.18, 0.44, 0.62)
    for index, point in enumerate(spec.points):
        x = left + index * band + bar_gap / 2
        height = (point.value / y_top) * plot_height if y_top else 0
        pdf.rect(x, frame_bottom, bar_width, height, stroke=0, fill=1)

    pdf.setFillColorRGB(0.18, 0.19, 0.21)
    pdf.setFont("Helvetica", 7.2 if len(spec.points) > 24 else 8.2)
    for index, point in enumerate(spec.points):
        x = left + index * band + bar_width / 2 + bar_gap / 2
        pdf.saveState()
        pdf.translate(x, frame_bottom - 8)
        pdf.rotate(55)
        pdf.drawString(0, 0, truncate_label(point.full_label, 24))
        pdf.restoreState()

    pdf.setFont("Helvetica", 10)
    pdf.drawCentredString(page_width / 2, 34, ascii_text(spec.x_axis_label))
    pdf.saveState()
    pdf.translate(24, frame_bottom + plot_height / 2)
    pdf.rotate(90)
    pdf.drawCentredString(0, 0, ascii_text(spec.y_axis_label))
    pdf.restoreState()

    pdf.setFillColorRGB(0.29, 0.31, 0.34)
    pdf.setFont("Helvetica", 8)
    draw_wrapped_pdf_text(pdf, 34, 82, spec.note, 180, 10)


def write_pdf(pdf_path: Path, specs: list[HistogramSpec]) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    page_size = landscape(A3)
    pdf = canvas.Canvas(str(pdf_path), pagesize=page_size)
    page_width, page_height = page_size
    for spec in specs:
        draw_pdf_page(pdf, spec, page_width, page_height)
        pdf.showPage()
    pdf.save()


def build_histograms(
    input_csv: Path = DEFAULT_INPUT,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    manifest_csv: Path = DEFAULT_MANIFEST,
    output_pdf: Path = DEFAULT_PDF,
) -> dict[str, int]:
    rows = read_csv(input_csv)
    grouped: dict[tuple[str, str, str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(group_key(row), []).append(row)

    output_dir.mkdir(parents=True, exist_ok=True)
    for old_svg in output_dir.glob("irpf_histogram_*.svg"):
        old_svg.unlink()

    manifest_rows: list[dict[str, str]] = []
    generated_specs: list[HistogramSpec] = []

    for key, group_rows in sorted(grouped.items(), key=lambda item: (int(item[0][0]) if item[0][0].isdigit() else 9999, item[0][1])):
        spec, status, skip_note = make_histogram_spec(group_rows, output_dir)
        first = group_rows[0]
        if spec is not None:
            write_svg(spec)
            generated_specs.append(spec)
            manifest_rows.append(
                {
                    "histogram_id": spec.histogram_id,
                    "status": status,
                    "calendar_year": spec.calendar_year,
                    "tax_return_year": spec.tax_return_year,
                    "source_table_id": spec.source_table_id,
                    "table_kind": spec.table_kind,
                    "geographic_scope": spec.geographic_scope,
                    "source_block": spec.source_block,
                    "row_count": str(len(spec.points)),
                    "frequency_field": spec.frequency_field,
                    "frequency_label": spec.frequency_label,
                    "bracket_label_field": spec.bracket_label_field,
                    "x_axis_label": spec.x_axis_label,
                    "y_axis_label": spec.y_axis_label,
                    "figure_svg": spec.svg_path.relative_to(ROOT).as_posix(),
                    "figure_pdf": output_pdf.relative_to(ROOT).as_posix(),
                    "fonte": spec.fonte,
                    "pagina_pdf": spec.pagina_pdf,
                    "pagina_impressa": spec.pagina_impressa,
                    "quadro": spec.quadro,
                    "note": spec.note,
                }
            )
        else:
            source = ascii_text(first_present(group_rows, "fonte"))
            manifest_rows.append(
                {
                    "histogram_id": "",
                    "status": status,
                    "calendar_year": clean(first.get("calendar_year")),
                    "tax_return_year": clean(first.get("tax_return_year")),
                    "source_table_id": clean(first.get("source_table_id")),
                    "table_kind": clean(first.get("table_kind")),
                    "geographic_scope": ascii_text(clean(first.get("geographic_scope"))),
                    "source_block": clean(first.get("source_block")),
                    "row_count": str(len(group_rows)),
                    "frequency_field": "",
                    "frequency_label": "",
                    "bracket_label_field": "",
                    "x_axis_label": "",
                    "y_axis_label": "",
                    "figure_svg": "",
                    "figure_pdf": "",
                    "fonte": source,
                    "pagina_pdf": clean(first_present(group_rows, "pagina_pdf")),
                    "pagina_impressa": clean(first_present(group_rows, "pagina_impressa")),
                    "quadro": clean(first_present(group_rows, "quadro")),
                    "note": skip_note,
                }
            )

    write_csv(manifest_csv, MANIFEST_FIELDS, manifest_rows)
    write_pdf(output_pdf, generated_specs)
    return {
        "source_groups": len(grouped),
        "histograms_generated": len(generated_specs),
        "manifest_rows": len(manifest_rows),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build IRPF distribution histograms from trusted bracket data.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--pdf", type=Path, default=DEFAULT_PDF)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    stats = build_histograms(
        input_csv=args.input,
        output_dir=args.output_dir,
        manifest_csv=args.manifest,
        output_pdf=args.pdf,
    )
    for key, value in stats.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
