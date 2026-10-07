from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlparse


ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = ROOT.parent
DEFAULT_SOURCE_ROOT = PROJECT_ROOT / "outputs" / "fontes-pedro-souza-irpf"
DEFAULT_TRUSTED_METADATA = ROOT / "data" / "trusted" / "irpf_distribution_source_metadata_yearly.csv"
DEFAULT_OUTPUT_CSV = ROOT / "data" / "raw" / "manifests" / "irpf_raw_pdf_manifest.csv"
DEFAULT_OUTPUT_SUMMARY = ROOT / "data" / "raw" / "manifests" / "irpf_raw_pdf_manifest_summary.md"

URL_RE = re.compile(r"https?://[^\s<>)\"'`;|]+")
PDF_REF_RE = re.compile(
    r"(?:outputs[\\/]+fontes-pedro-souza-irpf[\\/]+)?[^\s;\"'<>,|]*?\.pdf",
    re.IGNORECASE,
)


OUTPUT_FIELDS = [
    "manifest_id",
    "file_name",
    "document_role",
    "workspace_relative_path",
    "source_root_relative_path",
    "size_bytes",
    "size_mb",
    "sha256",
    "public_urls",
    "url_count",
    "metadata_calendar_years",
    "trusted_metadata_sources",
    "source_blocks",
    "access_category",
    "redistribution_status",
    "manifest_evidence_files",
    "notes",
]


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split()).strip()


def normalize_path_text(value: str) -> str:
    return unquote(clean(value).strip("`'\"")).replace("\\", "/")


def workspace_relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def source_relative(path: Path, source_root: Path) -> str:
    return path.resolve().relative_to(source_root.resolve()).as_posix()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_urls(text: str) -> list[str]:
    urls = []
    for match in URL_RE.findall(text):
        urls.append(match.rstrip(".,;)]}`"))
    return urls


def extract_pdf_references(text: str) -> list[str]:
    refs = []
    for match in PDF_REF_RE.findall(text):
        refs.append(normalize_path_text(match))
    return refs


def infer_pdf_reference_from_url(url: str) -> str:
    parsed = urlparse(url)
    name = Path(unquote(parsed.path)).name
    return name if name.lower().endswith(".pdf") else ""


def build_pdf_index(source_root: Path) -> tuple[list[Path], dict[str, str], dict[str, str]]:
    pdfs = sorted(source_root.rglob("*.pdf"), key=lambda p: source_relative(p, source_root).lower())
    rel_index = {source_relative(path, source_root): source_relative(path, source_root) for path in pdfs}

    basename_to_rels: dict[str, list[str]] = defaultdict(list)
    for path in pdfs:
        basename_to_rels[path.name.lower()].append(source_relative(path, source_root))

    unique_basename_index = {
        name: rels[0] for name, rels in basename_to_rels.items() if len(rels) == 1
    }
    return pdfs, rel_index, unique_basename_index


def resolve_pdf_reference(
    ref: str,
    rel_index: dict[str, str],
    unique_basename_index: dict[str, str],
) -> str:
    ref = normalize_path_text(ref)
    marker = "outputs/fontes-pedro-souza-irpf/"
    if marker in ref:
        ref = ref.split(marker, 1)[1]
    ref = ref.lstrip("./")

    if ref in rel_index:
        return ref

    basename = Path(ref).name.lower()
    return unique_basename_index.get(basename, "")


def add_links_from_text(
    text: str,
    evidence_file: str,
    link_index: dict[str, dict[str, set[str]]],
    rel_index: dict[str, str],
    unique_basename_index: dict[str, str],
) -> None:
    urls = extract_urls(text)
    refs = extract_pdf_references(text)
    refs.extend(filter(None, (infer_pdf_reference_from_url(url) for url in urls)))

    for ref in refs:
        rel = resolve_pdf_reference(ref, rel_index, unique_basename_index)
        if not rel:
            continue
        link_index[rel]["evidence_files"].add(evidence_file)
        for url in urls:
            link_index[rel]["urls"].add(url)


def index_trusted_metadata(
    metadata_csv: Path,
    link_index: dict[str, dict[str, set[str]]],
    rel_index: dict[str, str],
    unique_basename_index: dict[str, str],
) -> None:
    if not metadata_csv.exists():
        return

    with metadata_csv.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f, delimiter=";"))

    for row in rows:
        candidates = [
            row.get("local_file", ""),
            row.get("primary_source_url", ""),
            row.get("pdf_download_url", ""),
            row.get("alternative_url", ""),
        ]
        urls = [
            clean(row.get("primary_source_url")),
            clean(row.get("pdf_download_url")),
            clean(row.get("alternative_url")),
        ]
        urls = [url for url in urls if url.startswith(("http://", "https://"))]

        refs = []
        for candidate in candidates:
            refs.extend(extract_pdf_references(clean(candidate)))
            if clean(candidate).startswith(("http://", "https://")):
                inferred = infer_pdf_reference_from_url(clean(candidate))
                if inferred:
                    refs.append(inferred)

        for ref in refs:
            rel = resolve_pdf_reference(ref, rel_index, unique_basename_index)
            if not rel:
                continue
            link_index[rel]["evidence_files"].add("data/trusted/irpf_distribution_source_metadata_yearly.csv")
            for url in urls:
                link_index[rel]["urls"].add(url)
            if clean(row.get("calendar_year")):
                link_index[rel]["calendar_years"].add(clean(row.get("calendar_year")))
            if clean(row.get("primary_source")):
                link_index[rel]["trusted_sources"].add(clean(row.get("primary_source")))
            if clean(row.get("source_block")):
                link_index[rel]["source_blocks"].add(clean(row.get("source_block")))


def index_auxiliary_files(
    source_root: Path,
    link_index: dict[str, dict[str, set[str]]],
    rel_index: dict[str, str],
    unique_basename_index: dict[str, str],
) -> None:
    for pattern in ("*.csv", "*.md", "*.json"):
        for path in source_root.rglob(pattern):
            try:
                lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
            except OSError:
                continue
            evidence_file = workspace_relative(path)
            for line in lines:
                add_links_from_text(line, evidence_file, link_index, rel_index, unique_basename_index)


def classify_access(rel_path: str, urls: set[str]) -> tuple[str, str, str]:
    rel_lower = rel_path.lower()
    if "pedro_herculano_anexos/" in rel_lower:
        return (
            "public_origin_no_public_url_identified",
            "public_origin_confirmed_by_project_owner",
            "File received through correspondence from Pedro Herculano G. F. de Souza; the project owner reports public origin, but no direct public URL has been identified in the metadata.",
        )
    if urls:
        return (
            "public_url_identified",
            "review_source_terms_before_redistribution",
            "At least one public URL was identified in the project metadata or auxiliary files.",
        )
    return (
        "local_copy_no_public_url_identified",
        "review_before_redistribution",
        "No public URL was identified automatically; check the source manually before redistribution.",
    )


def classify_document_role(rel_path: str) -> str:
    name = Path(rel_path).name.lower()
    project_prefixes = (
        "inventario_",
        "pedido_",
        "tabela_metadados_",
    )
    if name.startswith(project_prefixes):
        return "project_document"
    return "source_pdf"


def join_values(values: set[str]) -> str:
    return " | ".join(sorted(v for v in values if v))


def build_manifest(
    source_root: Path,
    trusted_metadata: Path,
) -> list[dict[str, str]]:
    pdfs, rel_index, unique_basename_index = build_pdf_index(source_root)
    link_index: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))

    index_trusted_metadata(trusted_metadata, link_index, rel_index, unique_basename_index)
    index_auxiliary_files(source_root, link_index, rel_index, unique_basename_index)

    rows: list[dict[str, str]] = []
    for idx, path in enumerate(pdfs, start=1):
        rel = source_relative(path, source_root)
        info = link_index[rel]
        urls = info["urls"]
        access_category, redistribution_status, notes = classify_access(rel, urls)
        size_bytes = path.stat().st_size
        rows.append(
            {
                "manifest_id": f"PDF-{idx:04d}",
                "file_name": path.name,
                "document_role": classify_document_role(rel),
                "workspace_relative_path": workspace_relative(path),
                "source_root_relative_path": rel,
                "size_bytes": str(size_bytes),
                "size_mb": f"{size_bytes / (1024 * 1024):.2f}",
                "sha256": sha256_file(path),
                "public_urls": join_values(urls),
                "url_count": str(len(urls)),
                "metadata_calendar_years": join_values(info["calendar_years"]),
                "trusted_metadata_sources": join_values(info["trusted_sources"]),
                "source_blocks": join_values(info["source_blocks"]),
                "access_category": access_category,
                "redistribution_status": redistribution_status,
                "manifest_evidence_files": join_values(info["evidence_files"]),
                "notes": notes,
            }
        )
    return rows


def write_manifest(rows: list[dict[str, str]], output_csv: Path) -> None:
    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with output_csv.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_FIELDS, delimiter=";", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(rows: list[dict[str, str]], output_summary: Path) -> None:
    output_summary.parent.mkdir(parents=True, exist_ok=True)
    total_size = sum(int(row["size_bytes"]) for row in rows)
    by_category: dict[str, int] = defaultdict(int)
    by_role: dict[str, int] = defaultdict(int)
    for row in rows:
        by_category[row["access_category"]] += 1
        by_role[row["document_role"]] += 1

    lines = [
        "# Raw PDF Manifest Summary",
        "",
        "This summary describes the generated raw PDF manifest and the raw PDF files versioned in this repository through Git LFS.",
        "",
        f"- PDF files listed: {len(rows)}",
        f"- Total listed size: {total_size / (1024 * 1024):.2f} MB",
        "",
        "## Access Categories",
        "",
    ]
    for category, count in sorted(by_category.items()):
        lines.append(f"- `{category}`: {count}")
    lines.extend(["", "## Document Roles", ""])
    for role, count in sorted(by_role.items()):
        lines.append(f"- `{role}`: {count}")
    lines.extend(
        [
            "",
            "## Files",
            "",
            "- `irpf_raw_pdf_manifest.csv`: one row per local raw PDF file, including relative path, SHA-256 checksum, size, identified public URLs, and redistribution notes.",
            "",
            "The manifest can be regenerated locally with:",
            "",
            "```powershell",
            "python scripts/build_raw_pdf_manifest.py",
            "```",
        ]
    )
    output_summary.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a manifest of local raw PDF source files and known public links."
    )
    parser.add_argument(
        "--source-root",
        type=Path,
        default=DEFAULT_SOURCE_ROOT,
        help="Local source corpus root containing raw PDFs.",
    )
    parser.add_argument(
        "--trusted-metadata",
        type=Path,
        default=DEFAULT_TRUSTED_METADATA,
        help="Trusted yearly metadata CSV used to enrich the manifest.",
    )
    parser.add_argument(
        "--output-csv",
        type=Path,
        default=DEFAULT_OUTPUT_CSV,
        help="Output CSV manifest path.",
    )
    parser.add_argument(
        "--output-summary",
        type=Path,
        default=DEFAULT_OUTPUT_SUMMARY,
        help="Output Markdown summary path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.source_root.exists():
        raise FileNotFoundError(f"source root not found: {args.source_root}")
    rows = build_manifest(args.source_root, args.trusted_metadata)
    write_manifest(rows, args.output_csv)
    write_summary(rows, args.output_summary)
    print(args.output_csv)
    print(args.output_summary)
    print(f"PDF files listed: {len(rows)}")


if __name__ == "__main__":
    main()
