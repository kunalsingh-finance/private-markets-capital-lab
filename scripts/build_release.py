"""Package a verified saved report with its exact code and source inputs."""
import json
from pathlib import Path
import sys
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_release import member_name, verify_archive, verify_current_evidence


def main():
    status, pack, sources = verify_current_evidence(ROOT)
    destination = ROOT / "output" / "private_markets_capital_lab.zip"
    temporary = destination.with_name(destination.name + "." + uuid.uuid4().hex + ".tmp")
    # Public data enters through the exact normalized files identified in report
    # provenance. Other captures and all raw-source directories remain excluded.
    roots = [ROOT / name for name in ("pmcapital", "scripts", "tests", "docs", "sql")]
    candidates = {ROOT / "README.md", ROOT / ".gitignore"}
    for directory in roots:
        if directory.exists():
            for path in directory.rglob("*"):
                if path.is_file() and path.suffix in {".py", ".md", ".sql"} and "__pycache__" not in path.parts:
                    candidates.add(path)
    candidates.update(ROOT / Path(name) for name in sources)
    try:
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(candidates):
                if not path.exists():
                    continue
                resolved = path.resolve()
                if not resolved.is_relative_to(ROOT.resolve()):
                    raise ValueError("A release input resolves outside the project workspace")
                name = member_name(str(path.relative_to(ROOT)).replace("\\", "/"))
                archive.write(path, name)
            archive.write(ROOT / "output" / "report.html", "report.html")
            for name in sorted(status["artifacts"]):
                archive.write(pack / name, "evidence/" + name)
            portable_status = {
                **status, "pack": ".", "original_pack": status["pack"],
                "package_kind": "portable_evidence", "packaged_sources": sources,
            }
            archive.writestr("evidence/run_status.json", json.dumps(portable_status, indent=2))
            archive.writestr("START_HERE.html", '<!doctype html><meta charset="utf-8"><title>Private Markets Capital Lab</title><h1>Private Markets Performance & Capital Lab</h1><p>Independent synthetic partnership model and separately governed public research.</p><p><a href="report.html">Open the saved investor report</a></p><p>See README.md for usage and source rebuild instructions, and docs/PROJECT_BRIEF.md for the analytical workflow.</p>')
        verified = verify_archive(temporary)
        latest, _, latest_sources = verify_current_evidence(ROOT)
        if latest != status or latest_sources != sources:
            raise ValueError("Current reporting evidence changed during packaging")
        temporary.replace(destination)
    finally:
        # Only this invocation's checked, workspace-local temporary file is
        # removed. A previous verified release survives an unsuccessful build.
        if temporary.exists():
            if not temporary.resolve().is_relative_to((ROOT / "output").resolve()):
                raise ValueError("Refusing cleanup outside the intended output directory")
            temporary.unlink()
    print(f"Verified release: {destination} ({verified['artifacts']} artifacts, {verified['sources']} source inputs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
