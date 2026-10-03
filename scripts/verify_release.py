"""Verify exact evidence, calculation code and packaged source identities."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_FILES = {"funds.csv", "cashflows.csv", "valuations.csv", "benchmark.csv"}
ACCEPTED_STATUS = {"READY", "REVIEW_REQUIRED"}
ALLOWED_ROOT_FILES = {"README.md", ".gitignore", "START_HERE.html", "report.html"}
ALLOWED_PREFIXES = (
    "pmcapital/", "scripts/", "tests/", "docs/", "sql/",
    "data/sample/", "data/advanced/", "data/public_research/", "evidence/",
)


def member_name(value: str) -> str:
    """Portable file path, excluding Windows drive/ADS and traversal syntax."""
    if not isinstance(value, str) or not value or "\\" in value or ":" in value:
        raise ValueError(f"Unsafe release path: {value!r}")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts) or PurePosixPath(value).is_absolute():
        raise ValueError(f"Unsafe release path: {value!r}")
    if any(part.lower() in {"raw", "raw_sources", "__pycache__", ".git", ".aws"} for part in parts):
        raise ValueError(f"Excluded raw or private release path: {value!r}")
    return value


def _hash(value: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Manifest requires lowercase SHA-256 byte identities")
    return value


def _bytes_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _local_file(root: Path, name: str) -> Path:
    name = member_name(name)
    root = root.resolve()
    path = (root / Path(name)).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError(f"Required file is absent or outside the workspace: {name}")
    return path


def _source_hashes(manifest: dict, payload: dict) -> dict[str, str]:
    """Identities of authored synthetic inputs and derived public observations."""
    sample = manifest.get("source_hashes")
    if not isinstance(sample, dict) or set(sample) != SAMPLE_FILES:
        raise ValueError("Source manifest must identify all four synthetic input files")
    sources = {"data/sample/" + name: _hash(digest) for name, digest in sample.items()}
    payload_sample = {row["file"]: row["sha256"] for row in payload.get("provenance", [])}
    if payload_sample != sample:
        raise ValueError("Report source identities do not match the run manifest")
    advanced = payload.get("advanced")
    if not isinstance(advanced, dict) or not isinstance(advanced.get("provenance"), list):
        raise ValueError("Rebuild the full project before packaging: advanced provenance is missing")
    public = advanced.get("public_research")
    if not isinstance(public, dict):
        raise ValueError("Public research result must preserve its source availability")
    public_rows = public.get("provenance", [])
    if not isinstance(public_rows, list):
        raise ValueError("Public provenance must be a list")
    if public.get("records") and not public_rows:
        raise ValueError("Public observations require packaged normalized-source provenance")
    for rows, prefix in ((advanced["provenance"], "data/advanced/"), (public_rows, "data/public_research/")):
        for row in rows:
            name = member_name(row["file"])
            if not name.startswith(prefix):
                raise ValueError(f"Source provenance falls outside its supported population: {name}")
            digest = _hash(row["sha256"])
            if name in sources and sources[name] != digest:
                raise ValueError(f"Conflicting source identities: {name}")
            sources[name] = digest
    return sources


def verify_current_evidence(root: Path) -> tuple[dict, Path, dict[str, str]]:
    """Fail before publishing a ZIP if current files differ from saved evidence."""
    root = root.resolve()
    manifest = json.loads(_local_file(root, "output/run_status.json").read_text(encoding="utf-8"))
    if manifest.get("status") not in ACCEPTED_STATUS:
        raise ValueError("A READY or REVIEW_REQUIRED completed attempt is required")
    pack_name = member_name(manifest.get("pack"))
    if not pack_name.startswith("runs/"):
        raise ValueError("Current evidence must name a runs/ pack")
    pack = (root / "output" / Path(pack_name)).resolve()
    if not pack.is_relative_to((root / "output").resolve()) or not pack.is_dir():
        raise ValueError("Current evidence pack is unavailable")
    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, dict) or not {"report.html", "analytics.json", "warehouse.sqlite"} <= set(artifacts):
        raise ValueError("Current pack lacks required evidence identities")
    if set(artifacts) != {path.name for path in pack.iterdir() if path.is_file()}:
        raise ValueError("Current pack contents differ from its artifact manifest")
    for name, digest in artifacts.items():
        if "/" in member_name(name):
            raise ValueError("Evidence artifacts must use flat filenames")
        path = (pack / name).resolve()
        if not path.is_relative_to(pack) or _bytes_hash(path.read_bytes()) != _hash(digest):
            raise ValueError(f"Evidence artifact does not match its saved hash: {name}")
    if _local_file(root, "output/report.html").read_bytes() != (pack / "report.html").read_bytes():
        raise ValueError("Current report differs from the selected evidence report")
    payload = json.loads((pack / "analytics.json").read_text(encoding="utf-8"))
    for key in ("status", "run_id", "asof", "known_at"):
        if payload.get(key) != manifest.get(key):
            raise ValueError(f"Report and manifest context differ: {key}")
    code = manifest.get("code_hashes")
    actual_code = {str(path.relative_to(root)).replace("\\", "/") for path in (root / "pmcapital").glob("*.py")}
    if not isinstance(code, dict) or not code or set(code) != actual_code:
        raise ValueError("Calculation module inventory changed; rebuild the report")
    for name, digest in code.items():
        if _bytes_hash(_local_file(root, name).read_bytes()) != _hash(digest):
            raise ValueError(f"Calculation code changed after this report: {name}")
    sources = _source_hashes(manifest, payload)
    for name, digest in sources.items():
        if _bytes_hash(_local_file(root, name).read_bytes()) != digest:
            raise ValueError(f"Packaged source changed or custom source pack is unavailable: {name}; rebuild from the packaged inputs")
    return manifest, pack, sources


def verify_archive(path: Path) -> dict:
    """Verify all claimed byte identities and source/report context in a ZIP."""
    with zipfile.ZipFile(path) as archive:
        members = archive.namelist()
        names = set(members)
        if len(members) != len(names):
            raise ValueError("Release contains duplicate member paths")
        for name in names:
            member_name(name)
            if name not in ALLOWED_ROOT_FILES and not name.startswith(ALLOWED_PREFIXES):
                raise ValueError(f"Release member is outside the allowed content: {name}")
        required = {
            "START_HERE.html", "report.html", "README.md", "evidence/run_status.json",
            "pmcapital/analytics.py", "pmcapital/capital.py", "pmcapital/waterfall.py",
            "scripts/run_demo.py", "scripts/build_release.py", "scripts/verify_release.py",
            "scripts/verify_reporting.py", "scripts/verify_portability.py", "sql/reporting_queries.sql",
        }
        if not required <= names:
            raise ValueError("Release is missing required authored or evidence files")
        manifest = json.loads(archive.read("evidence/run_status.json"))
        if manifest.get("status") not in ACCEPTED_STATUS or manifest.get("pack") != ".":
            raise ValueError("Invalid portable manifest")
        artifacts = manifest.get("artifacts")
        if not isinstance(artifacts, dict) or not {"report.html", "analytics.json", "warehouse.sqlite"} <= set(artifacts):
            raise ValueError("Release lacks required evidence identities")
        expected_evidence = {"evidence/" + member_name(name) for name in artifacts} | {"evidence/run_status.json"}
        if expected_evidence != {name for name in names if name.startswith("evidence/")}:
            raise ValueError("Packaged evidence inventory differs from its manifest")
        for name, digest in artifacts.items():
            if _bytes_hash(archive.read("evidence/" + name)) != _hash(digest):
                raise ValueError(f"Artifact hash does not match: {name}")
        payload = json.loads(archive.read("evidence/analytics.json"))
        for key in ("status", "run_id", "asof", "known_at"):
            if payload.get(key) != manifest.get(key):
                raise ValueError(f"Packaged report context differs: {key}")
        code = manifest.get("code_hashes")
        if not isinstance(code, dict) or not code:
            raise ValueError("Release lacks calculation-code identities")
        if set(code) != {name for name in names if name.startswith("pmcapital/") and name.endswith(".py")}:
            raise ValueError("Packaged calculation inventory differs from its manifest")
        for name, digest in code.items():
            if _bytes_hash(archive.read(member_name(name))) != _hash(digest):
                raise ValueError(f"Authored code does not match report evidence: {name}")
        sources = _source_hashes(manifest, payload)
        if manifest.get("packaged_sources") != sources:
            raise ValueError("Packaged source manifest does not match report provenance")
        for name, digest in sources.items():
            if _bytes_hash(archive.read(name)) != digest:
                raise ValueError(f"Packaged source does not match report evidence: {name}")
        if archive.read("report.html") != archive.read("evidence/report.html"):
            raise ValueError("Saved report and evidence report differ")
        return {"members": len(names), "artifacts": len(artifacts), "sources": len(sources)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, default=ROOT / "output" / "private_markets_capital_lab.zip")
    args = parser.parse_args()
    result = verify_archive(args.archive)
    print(f"Verified {result['members']} release members, {result['artifacts']} evidence artifacts and {result['sources']} source inputs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
