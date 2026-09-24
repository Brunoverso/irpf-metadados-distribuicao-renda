from __future__ import annotations

import csv
import html
import re
import unicodedata
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import LongTable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, TableStyle


ROOT = Path(__file__).resolve().parents[1]
IN_CSV = ROOT / "data" / "tabela_metadados_distribuicoes_irpf.csv"
OUT_DIR = ROOT / "output" / "pdf"
OUT_PDF = OUT_DIR / "tabela_metadados_irpf_estilo_referencia.pdf"
OUT_COMPACT_CSV = ROOT / "data" / "tabela_metadados_irpf_estilo_referencia.csv"


def register_fonts() -> tuple[str, str]:
    fonts_dir = Path(r"C:\Windows\Fonts")
    normal = fonts_dir / "times.ttf"
    bold = fonts_dir / "timesbd.ttf"
    if normal.exists() and bold.exists():
        pdfmetrics.registerFont(TTFont("TimesCustom", str(normal)))
        pdfmetrics.registerFont(TTFont("TimesCustom-Bold", str(bold)))
        return "TimesCustom", "TimesCustom-Bold"
    return "Times-Roman", "Times-Bold"


FONT, FONT_BOLD = register_fonts()


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split()).strip()


def strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value) if not unicodedata.combining(ch)
    )


def short_scope(value: str) -> str:
    value = clean(value)
    return {
        "Brasil": "BR",
        "Distrito Federal": "DF",
        "Guanabara": "GB",
    }.get(value, "-")


def short_series(row: dict[str, str]) -> str:
    series = clean(row.get("serie_uso_recomendado"))
    status = clean(row.get("status_cobertura"))
    mapping = {
        "serie historica nacional principal": "N-RLIQ",
        "serie historica regional/local": "R-LOC",
        "serie paralela por rendimento bruto": "P-RBT",
        "GNIRPF moderna": "GNIRPF",
        "bloco moderno especifico": "MOD",
        "serie paralela/candidata": "P-CAND",
    }
    if series in mapping:
        return mapping[series]
    if status.startswith("nao temos"):
        return "No data"
    return series or "-"


def short_concept(value: str) -> str:
    value = strip_accents(clean(value)).lower()
    mapping = {
        "renda liquida": "RLIQ",
        "rendimento bruto total": "RBT",
        "rendimento tributavel bruto": "RTribB",
        "renda bruta total": "RB",
        "rendimentos totais em faixas de salario minimo mensal": "RTOT/SM",
    }
    return mapping.get(value, "-" if not value else value[:12])


def short_reported(value: str) -> str:
    raw = clean(value)
    value = strip_accents(raw).lower()
    if not value:
        return "-"
    if value == "rliq; imposto; pessoas":
        return "RLIQ; imp.; pess."
    if value.startswith("rliq; renda bruta"):
        return "RLIQ; RB; imp.; pess."
    if value.startswith("rendimento bruto"):
        return "RBT; RLIQ blocks"
    if value.startswith("rbt; tributacao exclusiva"):
        return "RBT; RTOT; BC; bens"
    if value.startswith("rbt; numero de declarantes"):
        return "RBT; decl."
    if value.startswith("renda bruta total"):
        return "RB; decl.; Gini"
    if len(value) > 24:
        return value[:21] + "..."
    return value


def short_unit(row: dict[str, str]) -> str:
    unit = clean(row.get("unidade_agregados"))
    if not unit:
        return "-"
    unit = unit.replace("R$ 1.000.000", "R$ mi")
    unit = unit.replace("R$ 1,00", "R$ 1")
    unit = unit.replace("NCr$ 1.000", "NCr$ mil")
    unit = unit.replace("Cr$ 1.000", "Cr$ mil")
    unit = unit.replace("mil-reis", "mil-rs")
    return unit


def short_pages(row: dict[str, str]) -> str:
    pdf_page = clean(row.get("pagina_pdf"))
    printed = clean(row.get("pagina_impressa"))
    if not pdf_page and not printed:
        return "-"
    if pdf_page and printed:
        printed = printed.replace("tabela completa no XLSX", "XLSX")
        printed = printed.replace("metadados; ", "")
        return f"{pdf_page}/{printed}"
    return pdf_page or printed


def source_reference(row: dict[str, str]) -> str:
    source = clean(row.get("fonte_principal"))
    if not source:
        return ""
    link = clean(row.get("link_pdf_download")) or clean(row.get("link_fonte_principal"))
    local_file = clean(row.get("arquivo_local"))
    if link:
        return f"{source} URL: {link}"
    if local_file:
        return f"{source} Arquivo local: {local_file}"
    return source


def escape(text: str) -> str:
    return html.escape(text, quote=False)


def paragraph(text: str, style: ParagraphStyle) -> Paragraph:
    return Paragraph(escape(text), style)


def build_styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "caption": ParagraphStyle(
            "Caption",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=11.5,
            leading=14,
            alignment=TA_LEFT,
            spaceAfter=12,
        ),
        "table": ParagraphStyle(
            "Table",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=8.4,
            leading=9.6,
            wordWrap="CJK",
        ),
        "table_header": ParagraphStyle(
            "TableHeader",
            parent=base["BodyText"],
            fontName=FONT_BOLD,
            fontSize=8.7,
            leading=9.8,
            wordWrap="CJK",
        ),
        "refs_title": ParagraphStyle(
            "RefsTitle",
            parent=base["Heading1"],
            fontName=FONT,
            fontSize=13,
            leading=15,
            spaceAfter=10,
        ),
        "ref": ParagraphStyle(
            "Ref",
            parent=base["BodyText"],
            fontName=FONT,
            fontSize=9.2,
            leading=11.2,
            leftIndent=18,
            firstLineIndent=-18,
            spaceAfter=5,
            wordWrap="CJK",
        ),
    }


def load_rows() -> list[dict[str, str]]:
    with IN_CSV.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def make_short_source_label(ref: str) -> str:
    if not ref:
        return ""
    if "Souza Reis" in ref:
        return "Souza Reis 1930"
    if "Anuario Estatistico do Brasil 1941-1945" in ref:
        return "AEB 1941-1945"
    if "Anuario Estatistico do Brasil 1946" in ref:
        return "AEB 1946"
    match = re.search(r"Anuario Estatistico do Brasil (\d{4})", ref)
    if match:
        return f"AEB {match.group(1)}"
    match = re.search(r"Boletim Estatistico, n\. (\d+)", ref)
    if match:
        return f"Bol. Est. {match.group(1)}"
    match = re.search(r"Anuario Economico-Fiscal (\d{4})", ref)
    if match:
        return f"AEF {match.group(1)}"
    match = re.search(r"Imposto de Renda Pessoa Fisica (\d{4})", ref)
    if match:
        return f"IRPF {match.group(1)}"
    if "Tributacao da Renda no Brasil Pos-Real" in ref:
        return "Pos-Real 2001"
    match = re.search(r"Grandes Numeros (?:DIRPF|IRPF).*?ano-calendario (\d{4})", ref)
    if match:
        return f"GNIRPF {match.group(1)}"
    if "Analise Economica da DIRPF 1999" in ref:
        return "Analise DIRPF 1999"
    if "Torres" in ref:
        return "Torres 2003"
    if "O imposto de renda das pessoas fisicas no Brasil" in ref:
        return "SRF 2004"
    if "Castro" in ref:
        return "Castro 2014"
    if "Imposto sobre a renda e proventos de qualquer natureza, 1968" in ref:
        return "CIEF 1968"
    if "Relatorio do ano de 1961" in ref:
        return "Rel. DIR 1961"
    if "Relatorio das atividades do exercicio ano de 1964" in ref:
        return "Rel. DIR 1964"
    if "Relatorio das atividades do ano de 1965" in ref:
        return "Rel. DIR 1965"
    return ref[:22] + ("..." if len(ref) > 22 else "")


def compact_rows(rows: list[dict[str, str]]) -> tuple[list[list[str]], list[str]]:
    refs: list[str] = []
    ref_index: dict[str, int] = {}
    compact: list[list[str]] = []

    for row in rows:
        ref = source_reference(row)
        if ref:
            if ref not in ref_index:
                ref_index[ref] = len(refs) + 1
                refs.append(ref)
            data_ref = f"[{ref_index[ref]}]"
            source_label = make_short_source_label(ref)
        else:
            data_ref = "No data"
            source_label = "No data"

        compact.append(
            [
                clean(row.get("ano_calendario")),
                clean(row.get("temos_flag")) or "0",
                clean(row.get("pedro_tem_flag")) or "0",
                short_scope(row.get("escopo_geografico")),
                short_series(row),
                source_label,
                short_concept(row.get("conceito_ordenamento")),
                short_reported(row.get("rendas_reportadas")),
                clean(row.get("ano_exercicio")) or "-",
                clean(row.get("numero_faixas")) or "-",
                clean(row.get("moeda")) or "-",
                short_unit(row),
                short_pages(row),
                data_ref,
            ]
        )

    return compact, refs


def write_compact_csv(rows: list[list[str]]) -> None:
    OUT_COMPACT_CSV.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "Ano",
        "Temos",
        "Pedro",
        "Escopo",
        "Serie",
        "Fonte curta",
        "Orden.",
        "Rendas",
        "Exerc.",
        "Faixas",
        "Moeda",
        "Unidade",
        "Pag.",
        "Ref.",
    ]
    with OUT_COMPACT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(header)
        writer.writerows(rows)


class NumberedCanvas:
    def __init__(self, *args, **kwargs):
        from reportlab.pdfgen.canvas import Canvas

        self._canvas = Canvas(*args, **kwargs)
        self._saved_page_states = []

    def __getattr__(self, name):
        return getattr(self._canvas, name)

    def showPage(self):
        self._saved_page_states.append(dict(self._canvas.__dict__))
        self._canvas._startPage()

    def save(self):
        page_count = len(self._saved_page_states)
        for state in self._saved_page_states:
            self._canvas.__dict__.update(state)
            self._draw_page_number(page_count)
            self._canvas.showPage()
        self._canvas.save()

    def _draw_page_number(self, page_count: int) -> None:
        self._canvas.setFont(FONT, 9.5)
        width, _height = landscape(A4)
        self._canvas.drawCentredString(width / 2.0, 0.65 * cm, str(self._canvas._pageNumber))


def build_pdf() -> None:
    styles = build_styles()
    rows = load_rows()
    compact, refs = compact_rows(rows)
    write_compact_csv(compact)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT_PDF),
        pagesize=landscape(A4),
        leftMargin=1.15 * cm,
        rightMargin=1.15 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.15 * cm,
        title="Integrated annual IRPF distribution source and extraction metadata",
        author="Projeto Mestrado",
    )

    story: list = []
    caption = (
        "Table 1: Integrated annual source, extraction, and coverage metadata for the IRPF "
        "distribution series. 'Temos' and 'Pedro' are 1/0 indicators for data currently "
        "incorporated and for availability in Pedro Herculano G. F. de Souza's Table 4. "
        "'Escopo' identifies geographic coverage (BR, DF, GB), 'Serie' classifies the "
        "recommended use, 'Orden.' identifies the ordering/income concept, and 'Pag.' gives "
        "PDF/printed page locations when available. Missing years are marked as 'No data'."
    )
    story.append(paragraph(caption, styles["caption"]))

    header = [
        "Ano",
        "Temos",
        "Pedro",
        "Esc.",
        "Serie",
        "Fonte",
        "Orden.",
        "Rendas",
        "Exerc.",
        "Fx.",
        "Moeda",
        "Unid.",
        "Pag.",
        "Ref.",
    ]
    table_data = [[paragraph(cell, styles["table_header"]) for cell in header]]
    for row in compact:
        table_data.append([paragraph(cell, styles["table"]) for cell in row])

    available_width = landscape(A4)[0] - doc.leftMargin - doc.rightMargin
    weights = [0.045, 0.047, 0.047, 0.05, 0.075, 0.155, 0.075, 0.12, 0.058, 0.048, 0.058, 0.07, 0.095, 0.057]
    col_widths = [available_width * w for w in weights]
    table = LongTable(table_data, colWidths=col_widths, repeatRows=1, hAlign="CENTER")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
                ("FONTNAME", (0, 1), (-1, -1), FONT),
                ("FONTSIZE", (0, 0), (-1, 0), 8.7),
                ("FONTSIZE", (0, 1), (-1, -1), 8.4),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (4, -1), "CENTER"),
                ("ALIGN", (8, 0), (-1, -1), "CENTER"),
                ("LINEABOVE", (0, 0), (-1, 0), 1.0, colors.black),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.black),
                ("LINEBELOW", (0, -1), (-1, -1), 1.0, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("LEFTPADDING", (0, 0), (-1, -1), 2),
                ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    story.append(table)
    story.append(PageBreak())

    story.append(Paragraph("References", styles["refs_title"]))
    legend = (
        "Abbreviations: N-RLIQ = national historical series by net income; R-LOC = regional/local "
        "series; P-RBT = parallel series ordered by total gross income; MOD = specific modern block; "
        "GNIRPF = Grandes Numeros do Imposto de Renda da Pessoa Fisica; RLIQ = net income; RBT = "
        "gross taxable income or total gross income as indicated by source; RTOT/SM = total income "
        "classes in monthly minimum wages."
    )
    story.append(Paragraph(escape(legend), styles["ref"]))
    story.append(Spacer(1, 0.15 * cm))
    for idx, ref in enumerate(refs, start=1):
        story.append(Paragraph(f"[{idx}] {escape(ref)}", styles["ref"]))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(OUT_PDF)
    print(OUT_COMPACT_CSV)


if __name__ == "__main__":
    build_pdf()
