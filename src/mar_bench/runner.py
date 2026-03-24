from __future__ import annotations

import json
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from .router_loader import load_router_module


@dataclass
class CheckResult:
    name: str
    passed: bool
    kind: str
    target: str
    expected: Any
    observed: Any


@dataclass
class CaseResult:
    case_id: str
    split: str
    description: str
    passed: bool
    checks_passed: int
    checks_total: int
    checks: list[CheckResult]
    step_outputs: dict[str, Any]
    db_path: str


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def lookup_ref(ref: str, context: dict[str, Any]) -> Any:
    if not ref.startswith("$"):
        return ref
    parts = ref[1:].split(".")
    cur: Any = context
    for part in parts:
        if isinstance(cur, list):
            cur = cur[int(part)]
        else:
            cur = cur[part]
    return cur


def resolve_refs(value: Any, context: dict[str, Any]) -> Any:
    if isinstance(value, str) and value.startswith("$"):
        return lookup_ref(value, context)
    if isinstance(value, list):
        return [resolve_refs(v, context) for v in value]
    if isinstance(value, dict):
        return {k: resolve_refs(v, context) for k, v in value.items()}
    return value


def get_target(target: str, context: dict[str, Any]) -> Any:
    return lookup_ref(target, context) if target.startswith("$") else target


def evaluate_check(check: dict[str, Any], context: dict[str, Any]) -> CheckResult:
    name = check.get("name", check["target"])
    kind = check["kind"]
    target = check["target"]
    observed = get_target(target, context)
    expected = resolve_refs(check.get("value"), context) if "value" in check else None

    if kind == "contains":
        if isinstance(observed, list):
            passed = any(
                (expected in item) if isinstance(item, str) and isinstance(expected, str) else item == expected
                for item in observed
            )
        elif isinstance(observed, str) and isinstance(expected, str):
            passed = expected in observed
        else:
            passed = False
    elif kind == "not_contains":
        if isinstance(observed, list):
            passed = all(
                not ((expected in item) if isinstance(item, str) and isinstance(expected, str) else item == expected)
                for item in observed
            )
        elif isinstance(observed, str) and isinstance(expected, str):
            passed = expected not in observed
        else:
            passed = True
    elif kind == "equals":
        passed = observed == expected
    elif kind == "len_min":
        passed = len(observed) >= int(expected)
    elif kind == "len_max":
        passed = len(observed) <= int(expected)
    elif kind == "exists":
        passed = observed not in (None, "", [], {})
    else:
        raise ValueError(f"Unsupported check kind: {kind}")

    return CheckResult(
        name=name,
        passed=bool(passed),
        kind=kind,
        target=target,
        expected=expected,
        observed=observed,
    )


def invoke_step(router: Any, conn: Any, step: dict[str, Any], context: dict[str, Any], db_path: str) -> Any:
    op = step["op"]
    if op == "init":
        return {"ok": True, **router.ensure_schema(conn), "db_path": db_path}
    if op == "add":
        payload = resolve_refs(step["payload"], context)
        return router.add_memory(conn, payload)
    if op == "bulk_add":
        items = resolve_refs(step["items"], context)
        return [router.add_memory(conn, item) for item in items]
    if op == "route":
        payload = resolve_refs(step["payload"], context)
        return router.route_memory(conn, payload)
    if op == "reflect":
        payload = resolve_refs(step["payload"], context)
        return router.reflect_memory(conn, payload)
    if op == "refresh":
        payload = resolve_refs(step["payload"], context)
        return router.refresh_memory(conn, payload)
    if op == "list":
        limit = int(resolve_refs(step.get("limit", 20), context))
        return router.list_memories(conn, limit)
    if op == "packets":
        limit = int(resolve_refs(step.get("limit", 10), context))
        return router.list_packets(conn, limit)
    if op == "inspect":
        memory_id = str(resolve_refs(step["memory_id"], context))
        return router.inspect_memory(conn, memory_id)
    raise ValueError(f"Unsupported op: {op}")


def run_case(case_path: Path, router_path: str) -> CaseResult:
    case = load_json(case_path)
    router = load_router_module(router_path)

    run_root = Path(tempfile.mkdtemp(prefix=f"{case['id']}-", dir="/tmp"))
    db_path = str(run_root / ".mar.sqlite3")
    conn = router.connect(db_path)
    router.ensure_schema(conn)

    context: dict[str, Any] = {"steps": {}}
    for step in case.get("steps", []):
        name = step["name"]
        context["steps"][name] = invoke_step(router, conn, step, context, db_path)

    checks = [evaluate_check(check, context) for check in case.get("checks", [])]
    checks_passed = sum(1 for c in checks if c.passed)
    passed = checks_passed == len(checks)

    return CaseResult(
        case_id=case["id"],
        split=case["split"],
        description=case.get("description", ""),
        passed=passed,
        checks_passed=checks_passed,
        checks_total=len(checks),
        checks=checks,
        step_outputs=context["steps"],
        db_path=db_path,
    )


def discover_cases(benchmarks_root: Path, split: str | None = None, case_id: str | None = None) -> list[Path]:
    if case_id:
        matches = sorted(benchmarks_root.glob(f"**/{case_id}.json"))
        return matches
    if split in {None, "all"}:
        return sorted(benchmarks_root.glob("**/*.json"))
    return sorted((benchmarks_root / split).glob("*.json"))


def summarize(results: list[CaseResult]) -> dict[str, Any]:
    by_split: dict[str, dict[str, Any]] = {}
    total_checks = 0
    passed_checks = 0
    for result in results:
        bucket = by_split.setdefault(result.split, {"cases": 0, "passed_cases": 0, "checks": 0, "passed_checks": 0})
        bucket["cases"] += 1
        bucket["passed_cases"] += int(result.passed)
        bucket["checks"] += result.checks_total
        bucket["passed_checks"] += result.checks_passed
        total_checks += result.checks_total
        passed_checks += result.checks_passed

    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "case_count": len(results),
        "passed_cases": sum(int(r.passed) for r in results),
        "check_count": total_checks,
        "passed_checks": passed_checks,
        "splits": by_split,
        "cases": [
            {
                "case_id": r.case_id,
                "split": r.split,
                "passed": r.passed,
                "checks_passed": r.checks_passed,
                "checks_total": r.checks_total,
                "description": r.description,
            }
            for r in results
        ],
    }


def write_report(out_dir: Path, summary: dict[str, Any], results: list[CaseResult]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    cases_dir = out_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    lines = [
        "# Benchmark Summary",
        "",
        f"- Cases: {summary['passed_cases']}/{summary['case_count']} passed",
        f"- Checks: {summary['passed_checks']}/{summary['check_count']} passed",
        "",
        "## Splits",
        "",
    ]
    for split, bucket in summary["splits"].items():
        lines.append(f"- **{split}**: cases {bucket['passed_cases']}/{bucket['cases']}, checks {bucket['passed_checks']}/{bucket['checks']}")
    lines.extend(["", "## Cases", ""])
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"- **{result.case_id}** [{result.split}] — {status} ({result.checks_passed}/{result.checks_total} checks)")
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n")

    for result in results:
        payload = {
            "case_id": result.case_id,
            "split": result.split,
            "description": result.description,
            "passed": result.passed,
            "checks_passed": result.checks_passed,
            "checks_total": result.checks_total,
            "db_path": result.db_path,
            "checks": [asdict(c) for c in result.checks],
            "step_outputs": result.step_outputs,
        }
        (cases_dir / f"{result.case_id}.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))
