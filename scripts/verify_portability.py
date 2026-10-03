"""Extract the verified release, run tests and rebuild its financial evidence."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.verify_release import verify_archive


def main():
    archive_path = ROOT / "output" / "private_markets_capital_lab.zip"
    verify_archive(archive_path)
    with zipfile.ZipFile(archive_path) as archive:
        expected = json.loads(archive.read("evidence/analytics.json"))
        with tempfile.TemporaryDirectory(prefix="private_markets_release_") as temporary:
            extracted = Path(temporary)
            archive.extractall(extracted)
            commands = [
                [sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-q"],
                [sys.executable, "-B", "scripts/run_demo.py", "--asof", expected["asof"], "--known-at", expected["known_at"]],
                [sys.executable, "-B", "scripts/verify_reporting.py"],
            ]
            for command in commands:
                result = subprocess.run(command, cwd=extracted, capture_output=True, text=True, timeout=120)
                if result.returncode:
                    raise RuntimeError("Portable check failed:\n" + result.stdout + result.stderr)
                print((result.stdout + result.stderr).strip())
            status = json.loads((extracted / "output" / "run_status.json").read_text(encoding="utf-8"))
            rebuilt = json.loads((extracted / "output" / status["pack"] / "analytics.json").read_text(encoding="utf-8"))
            for payload in (expected, rebuilt):
                payload.pop("run_id", None)
                payload.pop("built_at", None)
            if rebuilt != expected:
                raise ValueError("Extracted-source financial evidence differs from the saved report")
    print("Portable source rebuild matches all saved financial evidence; only run identity/time differ.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
