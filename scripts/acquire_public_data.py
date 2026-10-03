"""Optional, explicit acquisition of allowlisted public disclosures.

The installed CalSTRS observations were obtained through official PDF text in
the research browser. This downloader was not used to obtain that snapshot.
PDF bytes are retained for manual extraction; they are never guessed into rows.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pmcapital.public_data import SOURCES, make_snapshot, parse_fund_summary_html, save_snapshot

MAX_SOURCE_BYTES = 4 * 1024 * 1024


class _SourceRedirectPolicy(HTTPRedirectHandler):
    def __init__(self, hostname: str):
        super().__init__()
        self.hostname = hostname

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        parsed = urlparse(newurl)
        if parsed.scheme != "https" or parsed.hostname != self.hostname:
            raise ValueError("Redirect outside the allowlisted HTTPS source host")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def acquire(source_id: str, root: Path, raw_dir: Path, *, amount_scale: int | None = None) -> dict:
    if source_id not in SOURCES:
        raise ValueError("Source is not allowlisted")
    source = SOURCES[source_id]
    if source["format"] == "html" and amount_scale is None:
        raise ValueError("HTML acquisition requires --amount-scale from the source's stated units")
    request = Request(source["url"], headers={"User-Agent": "PrivateMarketsCapitalLab/0.1 public academic-style research", "Accept": "text/html,application/pdf"})
    # One request, no authentication, no retries, and no access-control bypass.
    opener = build_opener(_SourceRedirectPolicy(urlparse(source["url"]).hostname))
    with opener.open(request, timeout=30) as response:
        final_url = response.geturl()
        if urlparse(final_url).hostname != urlparse(source["url"]).hostname:
            raise ValueError("Unexpected cross-host source redirect")
        content_type = response.headers.get_content_type()
        data = response.read(MAX_SOURCE_BYTES + 1)
    if len(data) > MAX_SOURCE_BYTES:
        raise ValueError("Source exceeds the bounded download size")
    if source["format"] == "pdf" and not data.startswith(b"%PDF"):
        raise ValueError("Source did not provide a PDF")
    if source["format"] == "html" and content_type not in {"text/html", "application/xhtml+xml"}:
        raise ValueError("Source did not provide HTML")
    retrieved_at = datetime.now(timezone.utc).isoformat()
    digest = hashlib.sha256(data).hexdigest()
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{source_id}_{digest}.{source['format']}"
    if raw_path.exists():
        if raw_path.read_bytes() != data:
            raise ValueError("Immutable raw-source path has different bytes")
    else:
        with raw_path.open("xb") as stream:
            stream.write(data)
    manifest = {"source_id": source_id, "source_url": source["url"], "final_url": final_url,
                "retrieved_at": retrieved_at, "raw_file": str(raw_path),
                "raw_source_sha256": digest, "byte_count": len(data), "content_type": content_type,
                "status": "RETRIEVED_RAW_ONLY"}
    if source["format"] == "html":
        parsed = parse_fund_summary_html(data.decode("utf-8-sig"), amount_scale=amount_scale)
        snapshot = make_snapshot(source_id=source_id, asof_date=parsed["asof_date"],
                                 retrieved_at=retrieved_at, capture_method="PARSED_DOWNLOADED_OFFICIAL_HTML",
                                 records=parsed["records"], raw_source_sha256=digest,
                                 coverage="Recognized source HTML table; parser does not infer missing rows")
        manifest["snapshot_file"] = str(save_snapshot(root, snapshot))
        manifest["status"] = "NORMALIZED_SNAPSHOT_SAVED"
    else:
        manifest["limitations"] = ["The standard-library utility does not extract PDF tables. Review the PDF and capture typed observations with exact row/page evidence; no cash flows are reconstructed."]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    manifest_path = raw_dir / f"{source_id}_{stamp}_{digest[:12]}.json"
    with manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Explicitly acquire one allowlisted official public disclosure. Raw sources are local research artifacts, not part of the shared normalized dataset.")
    parser.add_argument("--source", required=True, choices=sorted(SOURCES))
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--raw-dir", type=Path, help="Default: <project>/output/public_sources")
    parser.add_argument("--amount-scale", type=int, choices=(1, 1000, 1000000), help="Explicit dollars per displayed unit for HTML sources; never inferred")
    args = parser.parse_args()
    root = args.project_root.resolve()
    raw_dir = args.raw_dir.resolve() if args.raw_dir else root / "output" / "public_sources"
    try:
        result = acquire(args.source, root, raw_dir, amount_scale=args.amount_scale)
    except (OSError, ValueError) as exc:
        print(json.dumps({"status": "ACQUISITION_FAILED", "source_id": args.source, "error": str(exc)}), file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
