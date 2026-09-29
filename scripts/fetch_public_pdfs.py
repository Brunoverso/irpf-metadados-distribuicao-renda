from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "data" / "raw" / "manifests" / "irpf_raw_pdf_manifest.csv"
DEFAULT_DESTINATION_ROOT = ROOT / "data" / "raw" / "pdfs"

PUBLIC_ACCESS_CATEGORY = "public_url_identified"
DEFAULT_USER_AGENT = (
    "irpf-metadados-distribuicao-renda/0.1 "
    "(research source verification; contact repository maintainer)"
)


@dataclass(frozen=True)
class FetchResult:
    status: str
    manifest_id: str
    target: Path
    detail: str = ""


def clean(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(str(value).replace("\n", " ").split()).strip()


def read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f, delimiter=";"))


def split_urls(value: str) -> list[str]:
    urls = [clean(url) for url in value.split("|")]
    return [url for url in urls if url.startswith(("http://", "https://"))]


def ordered_urls(row: dict[str, str]) -> list[str]:
    expected_stem = Path(clean(row.get("file_name"))).stem.lower()

    def sort_key(url: str) -> tuple[bool, bool, bool, bool, str]:
        lower = url.lower()
        has_expected_stem = bool(expected_stem and expected_stem in lower)
        has_pdf_marker = ".pdf" in lower
        looks_like_download = (
            "@@download/file" in lower or "/download/" in lower or lower.endswith(".pdf")
        )
        looks_like_view_page = lower.rstrip("/").endswith("/view")
        return (
            not has_expected_stem,
            not has_pdf_marker,
            not looks_like_download,
            looks_like_view_page,
            lower,
        )

    return sorted(split_urls(clean(row.get("public_urls"))), key=sort_key)


def split_years(value: str) -> set[str]:
    return {clean(year) for year in value.split("|") if clean(year)}


def row_matches_filters(row: dict[str, str], args: argparse.Namespace) -> bool:
    if clean(row.get("access_category")) != PUBLIC_ACCESS_CATEGORY:
        return False
    if not args.include_project_documents and clean(row.get("document_role")) != "source_pdf":
        return False
    if args.manifest_id and clean(row.get("manifest_id")) not in args.manifest_id:
        return False
    if args.calendar_year:
        row_years = split_years(clean(row.get("metadata_calendar_years")))
        if not row_years.intersection(args.calendar_year):
            return False
    return bool(ordered_urls(row))


def safe_relative_path(value: str) -> PurePosixPath:
    normalized = clean(value).replace("\\", "/").lstrip("/")
    rel_path = PurePosixPath(normalized)
    if not normalized or rel_path.is_absolute():
        raise ValueError(f"invalid relative path: {value!r}")
    if any(part in {"", ".", ".."} for part in rel_path.parts):
        raise ValueError(f"unsafe relative path: {value!r}")
    if rel_path.parts and ":" in rel_path.parts[0]:
        raise ValueError(f"absolute or drive-qualified path is not allowed: {value!r}")
    return rel_path


def target_path(row: dict[str, str], destination_root: Path, path_field: str) -> Path:
    rel_path = safe_relative_path(clean(row.get(path_field)))
    root = destination_root.resolve()
    target = (root / Path(*rel_path.parts)).resolve()
    if not target.is_relative_to(root):
        raise ValueError(f"target path escapes destination root: {target}")
    return target


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_to_temp(url: str, target: Path, timeout: float, user_agent: str) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": user_agent})
    with urlopen(request, timeout=timeout) as response:
        with tempfile.NamedTemporaryFile(
            "wb",
            delete=False,
            dir=target.parent,
            prefix=f".{target.name}.",
            suffix=".tmp",
        ) as tmp:
            shutil.copyfileobj(response, tmp)
            return Path(tmp.name)


def fetch_row(row: dict[str, str], args: argparse.Namespace) -> FetchResult:
    manifest_id = clean(row.get("manifest_id"))
    target = target_path(row, args.destination_root, args.path_field)
    expected_hash = clean(row.get("sha256")).lower()

    if target.exists() and not args.overwrite:
        actual_hash = sha256_file(target)
        if expected_hash and actual_hash == expected_hash:
            return FetchResult("matched_existing", manifest_id, target)
        return FetchResult(
            "existing_checksum_mismatch",
            manifest_id,
            target,
            f"expected {expected_hash}, found {actual_hash}",
        )

    urls = ordered_urls(row)
    if args.dry_run:
        return FetchResult("would_download", manifest_id, target, urls[0])

    errors: list[str] = []
    for url in urls:
        tmp_path: Path | None = None
        try:
            tmp_path = download_to_temp(url, target, args.timeout, args.user_agent)
            actual_hash = sha256_file(tmp_path)
            if expected_hash and actual_hash != expected_hash:
                errors.append(f"{url} -> checksum {actual_hash}")
                tmp_path.unlink(missing_ok=True)
                continue
            tmp_path.replace(target)
            return FetchResult("downloaded", manifest_id, target, url)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            errors.append(f"{url} -> {exc}")
            if tmp_path is not None:
                tmp_path.unlink(missing_ok=True)

    return FetchResult("failed", manifest_id, target, "; ".join(errors[-3:]))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download public raw PDF sources listed in the manifest and verify them "
            "against the recorded SHA-256 checksums."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=DEFAULT_MANIFEST,
        help="Input raw PDF manifest CSV.",
    )
    parser.add_argument(
        "--destination-root",
        type=Path,
        default=DEFAULT_DESTINATION_ROOT,
        help="Root folder where downloaded PDFs are written.",
    )
    parser.add_argument(
        "--path-field",
        choices=("source_root_relative_path", "workspace_relative_path"),
        default="source_root_relative_path",
        help="Manifest path column to recreate under the destination root.",
    )
    parser.add_argument(
        "--manifest-id",
        action="append",
        default=[],
        help="Download only a specific manifest ID. May be passed more than once.",
    )
    parser.add_argument(
        "--calendar-year",
        action="append",
        default=[],
        help="Download only rows associated with a calendar year. May be passed more than once.",
    )
    parser.add_argument(
        "--include-project-documents",
        action="store_true",
        help="Also include project-generated PDFs if they have public URLs.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of matching rows to process. Zero means no limit.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace existing files instead of only validating them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the planned actions without downloading files.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="Per-request timeout in seconds.",
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="HTTP User-Agent header used for downloads.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = read_manifest(args.manifest)
    selected = [row for row in rows if row_matches_filters(row, args)]
    if args.limit:
        selected = selected[: args.limit]

    counts: Counter[str] = Counter()
    failed_statuses = {"existing_checksum_mismatch", "failed"}

    print(f"Manifest rows: {len(rows)}")
    print(f"Selected public rows: {len(selected)}")
    print(f"Destination root: {args.destination_root.resolve()}")
    print(f"Path field: {args.path_field}")
    if args.dry_run:
        print("Mode: dry run")

    for row in selected:
        result = fetch_row(row, args)
        counts[result.status] += 1
        detail = f" ({result.detail})" if result.detail else ""
        print(f"{result.status}: {result.manifest_id} -> {result.target}{detail}")

    print("Summary:")
    for status, count in sorted(counts.items()):
        print(f"- {status}: {count}")

    if any(counts[status] for status in failed_statuses):
        sys.exit(1)


if __name__ == "__main__":
    main()
