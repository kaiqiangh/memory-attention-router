from __future__ import annotations

import argparse
from datetime import datetime, UTC
from pathlib import Path

from .runner import discover_cases, run_case, summarize, write_report


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description="Run memory-attention-router benchmarks")
    parser.add_argument("--split", default="all", choices=["all", "dev", "holdout", "adversarial"])
    parser.add_argument("--case", help="Run one specific case id")
    parser.add_argument(
        "--router-path",
        default=str(root / "vendor-memory-attention-router" / "skills" / "scripts" / "memory_router.py"),
    )
    parser.add_argument(
        "--benchmarks-root",
        default=str(root / "benchmarks"),
    )
    args = parser.parse_args()

    cases = discover_cases(Path(args.benchmarks_root), split=args.split, case_id=args.case)
    if not cases:
        raise SystemExit("No benchmark cases found")

    results = [run_case(case, args.router_path) for case in cases]
    summary = summarize(results)

    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    out_dir = root / "runs" / run_id
    write_report(out_dir, summary, results)

    print(out_dir)
    print(f"cases: {summary['passed_cases']}/{summary['case_count']} passed")
    print(f"checks: {summary['passed_checks']}/{summary['check_count']} passed")
