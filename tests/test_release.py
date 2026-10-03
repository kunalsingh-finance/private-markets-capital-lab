"""A saved report must bind to the exact inputs and code in its review ZIP."""
from contextlib import redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from scripts import build_release
from scripts.verify_release import verify_archive, verify_current_evidence

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReleaseIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT, prefix="release_test_")
        self.root = Path(self.temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(ROOT.resolve()))
        for name in ("pmcapital", "scripts", "sql", "data/sample", "data/advanced"):
            shutil.copytree(ROOT / name, self.root / name)
        (self.root / "README.md").write_text("Integrity test fixture\n", encoding="utf-8")
        (self.root / ".gitignore").write_text("output/\n", encoding="utf-8")
        self.pack = self.root / "output" / "runs" / "fixture"
        self.pack.mkdir(parents=True)
        self.sample_hashes = {path.name: digest(path) for path in (self.root / "data" / "sample").glob("*.csv")}
        advanced = [{"file": str(path.relative_to(self.root)).replace("\\", "/"), "sha256": digest(path)} for path in sorted((self.root / "data" / "advanced").glob("*.json"))]
        public_path = self.root / "data" / "public_research" / "observations_fixture.json"
        public_path.parent.mkdir(parents=True)
        public_path.write_text('{"records":[{"name":"Derived observation"}]}\n', encoding="utf-8")
        public = [{"file": "data/public_research/observations_fixture.json", "sha256": digest(public_path), "kind": "DERIVED_OFFICIAL_OBSERVATIONS"}]
        self.payload = {
            "status": "REVIEW_REQUIRED", "run_id": "fixture", "asof": "2026-06-30", "known_at": "2026-08-15",
            "provenance": [{"file": name, "sha256": value} for name, value in self.sample_hashes.items()],
            "advanced": {"provenance": advanced, "public_research": {"records": [{"name": "Derived observation"}], "provenance": public}},
        }
        (self.pack / "analytics.json").write_text(json.dumps(self.payload), encoding="utf-8")
        # Artifact contents are arbitrary here: accounting is verified by the
        # finance suites. These tests establish byte identities and handoff.
        (self.pack / "warehouse.sqlite").write_bytes(b"warehouse test artifact")
        (self.pack / "report.html").write_text("<!doctype html><p>Saved report</p>", encoding="utf-8")
        shutil.copyfile(self.pack / "report.html", self.root / "output" / "report.html")
        self.manifest = {
            "status": "REVIEW_REQUIRED", "run_id": "fixture", "asof": "2026-06-30", "known_at": "2026-08-15",
            "pack": "runs/fixture", "source_hashes": self.sample_hashes,
            "code_hashes": {str(path.relative_to(self.root)).replace("\\", "/"): digest(path) for path in (self.root / "pmcapital").glob("*.py")},
            "artifacts": {path.name: digest(path) for path in self.pack.iterdir()},
        }
        (self.root / "output" / "run_status.json").write_text(json.dumps(self.manifest), encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def package(self):
        with patch.object(build_release, "ROOT", self.root), redirect_stdout(io.StringIO()):
            build_release.main()
        return self.root / "output" / "private_markets_capital_lab.zip"

    def test_complete_sources_verify_and_raw_captures_are_excluded(self):
        raw = self.root / "data" / "public_research" / "raw"
        raw.mkdir()
        (raw / "copied_source.json").write_text('{"original":"excluded"}', encoding="utf-8")
        (raw.parent / "unrelated_capture.json").write_text('{"unused":"excluded"}', encoding="utf-8")
        path = self.package()
        result = verify_archive(path)
        self.assertEqual(result["sources"], 9)  # Four CSVs, four cases, one derived snapshot.
        with zipfile.ZipFile(path) as archive:
            self.assertIn("data/public_research/observations_fixture.json", archive.namelist())
            self.assertFalse(any("raw/" in name or "unrelated_capture" in name for name in archive.namelist()))

    def test_changed_sample_source_is_rejected_before_package_success(self):
        path = self.root / "data" / "sample" / "cashflows.csv"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "source changed|custom source"):
            self.package()
        self.assertFalse((self.root / "output" / "private_markets_capital_lab.zip").exists())

    def test_changed_advanced_and_public_source_files_are_rejected(self):
        for name in ("data/advanced/northstar_base.json", "data/public_research/observations_fixture.json"):
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                with self.assertRaisesRegex(ValueError, "source changed|custom source"):
                    verify_current_evidence(self.root)
                path.write_bytes(original)

    def test_changed_calculation_code_is_rejected(self):
        path = self.root / "pmcapital" / "waterfall.py"
        path.write_bytes(path.read_bytes() + b"\n# changed after report\n")
        with self.assertRaisesRegex(ValueError, "Calculation code changed"):
            self.package()

    def test_changed_artifact_is_rejected_and_previous_release_survives(self):
        path = self.package()
        previous_zip = path.read_bytes()
        (self.pack / "analytics.json").write_bytes(b"{}")
        with self.assertRaisesRegex(ValueError, "Evidence artifact"):
            self.package()
        self.assertEqual(path.read_bytes(), previous_zip)

    def test_packaged_source_tampering_is_rejected(self):
        path = self.package()
        changed = self.root / "tampered.zip"
        with zipfile.ZipFile(path) as original, zipfile.ZipFile(changed, "w") as replacement:
            for name in original.namelist():
                data = original.read(name)
                if name == "data/sample/cashflows.csv":
                    data += b"\n"
                replacement.writestr(name, data)
        with self.assertRaisesRegex(ValueError, "Packaged source does not match"):
            verify_archive(changed)

    def test_unsafe_pack_path_is_rejected(self):
        self.manifest["pack"] = "../other_project"
        (self.root / "output" / "run_status.json").write_text(json.dumps(self.manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Unsafe release path"):
            verify_current_evidence(self.root)

    def test_missing_runnable_entrypoint_is_rejected(self):
        path = self.package()
        changed = self.root / "missing_entrypoint.zip"
        with zipfile.ZipFile(path) as original, zipfile.ZipFile(changed, "w") as replacement:
            for name in original.namelist():
                if name != "scripts/run_demo.py":
                    replacement.writestr(name, original.read(name))
        with self.assertRaisesRegex(ValueError, "missing required"):
            verify_archive(changed)


if __name__ == "__main__":
    unittest.main()
