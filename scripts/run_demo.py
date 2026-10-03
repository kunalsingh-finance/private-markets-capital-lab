"""Run without installing packages: python scripts/run_demo.py."""
import argparse
from datetime import date
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pmcapital.pipeline import build


def main():
    parser = argparse.ArgumentParser(description="Build the synthetic private-markets capital lab")
    parser.add_argument("--asof", type=date.fromisoformat, default=date(2026, 6, 30))
    parser.add_argument("--known-at", type=date.fromisoformat, default=date(2026, 8, 15))
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "sample")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "output")
    args = parser.parse_args()
    try:
        result = build(args.data_dir, args.output_dir, args.asof, args.known_at)
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1
    print(f"{result['status']}: {len(result['funds'])} synthetic funds; {len(result['controls'])} controls")
    print(f"Report: {(args.output_dir / 'report.html').resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
