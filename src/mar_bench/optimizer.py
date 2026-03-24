from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from .runner import discover_cases, run_case, summarize


@dataclass
class CandidateSpec:
    candidate_id: str
    description: str
    patches: list[dict[str, str]]


@dataclass
class CandidateEvaluation:
    candidate_id: str
    description: str
    repo_path: str
    router_path: str
    summary: dict[str, Any]
    metrics: dict[str, float]
    ranking: list[float]


def patch_executor_reads_preferences() -> list[dict[str, str]]:
    return [
        {
            "path": "skills/scripts/memory_router.py",
            "old": '    "executor": ("procedure", "episode", "reflection"),\n',
            "new": '    "executor": ("preference", "procedure", "episode", "reflection"),\n',
        }
    ]


def patch_directional_contradiction() -> list[dict[str, str]]:
    return [
        {
            "path": "skills/scripts/memory_router.py",
            "old": '        SELECT edge_type, weight\n',
            "new": '        SELECT from_memory_id, to_memory_id, edge_type, weight\n',
        },
        {
            "path": "skills/scripts/memory_router.py",
            "old": '        elif row["edge_type"] == "contradicts":\n            contradiction += float(row["weight"])\n',
            "new": '        elif row["edge_type"] == "contradicts":\n            if row["to_memory_id"] == mem_id:\n                contradiction += float(row["weight"])\n',
        },
    ]

def patch_support_weight(weight: float) -> list[dict[str, str]]:
    return [
        {
            "path": "skills/scripts/memory_router.py",
            "old": '        + 0.05 * support\n',
            "new": f'        + {weight:.2f} * support\n',
        }
    ]


def patch_importance_weight(weight: float) -> list[dict[str, str]]:
    return [
        {
            "path": "skills/scripts/memory_router.py",
            "old": '        + 0.13 * importance\n',
            "new": f'        + {weight:.2f} * importance\n',
        }
    ]


def compact_patch_set(
    *,
    selected_limit: int,
    constraint_limit: int,
    facts_limit: int,
    procedures_limit: int,
    pitfalls_limit: int,
) -> list[dict[str, str]]:
    return [
        {
            "path": "skills/scripts/memory_router.py",
            "old": '    return dedupe_keep_order(items, limit=6)\n',
            "new": f'    return dedupe_keep_order(items, limit={constraint_limit})\n',
        },
        {
            "path": "skills/scripts/memory_router.py",
            "old": 'def extract_relevant_facts(selected: list[sqlite3.Row]) -> list[str]:\n    items: list[str] = []\n    for row in selected:\n        if row["memory_type"] in {"summary", "episode"}:\n            items.append(row["summary"])\n    return dedupe_keep_order(items, limit=5)\n',
            "new": f'def extract_relevant_facts(selected: list[sqlite3.Row]) -> list[str]:\n    items: list[str] = []\n    for row in selected:\n        if row["memory_type"] in {{"summary", "episode"}}:\n            items.append(row["summary"])\n    return dedupe_keep_order(items, limit={facts_limit})\n',
        },
        {
            "path": "skills/scripts/memory_router.py",
            "old": 'def extract_procedures(selected: list[sqlite3.Row]) -> list[str]:\n    items = [row["summary"] for row in selected if row["memory_type"] == "procedure"]\n    return dedupe_keep_order(items, limit=4)\n',
            "new": f'def extract_procedures(selected: list[sqlite3.Row]) -> list[str]:\n    items = [row["summary"] for row in selected if row["memory_type"] == "procedure"]\n    return dedupe_keep_order(items, limit={procedures_limit})\n',
        },
        {
            "path": "skills/scripts/memory_router.py",
            "old": 'def extract_pitfalls(\n    selected: list[sqlite3.Row], recent_failures: list[str]\n) -> list[str]:\n    items = list(recent_failures)\n    for row in selected:\n        if row["memory_type"] == "reflection":\n            items.append(row["summary"])\n        tags = loads_json_field(row["tags_json"], [])\n        if any(tag in {"failure", "pitfall", "warning"} for tag in tags):\n            items.append(row["summary"])\n    return dedupe_keep_order(items, limit=4)\n',
            "new": f'def extract_pitfalls(\n    selected: list[sqlite3.Row], recent_failures: list[str]\n) -> list[str]:\n    items = list(recent_failures)\n    for row in selected:\n        if row["memory_type"] == "reflection":\n            items.append(row["summary"])\n        tags = loads_json_field(row["tags_json"], [])\n        if any(tag in {{"failure", "pitfall", "warning"}} for tag in tags):\n            items.append(row["summary"])\n    return dedupe_keep_order(items, limit={pitfalls_limit})\n',
        },
        {
            "path": "skills/scripts/memory_router.py",
            "old": '    selected_rows = [cand.row for cand in scored[:8]]\n',
            "new": f'    selected_rows = [cand.row for cand in scored[:{selected_limit}]]\n',
        },
    ]


def default_candidates() -> list[CandidateSpec]:
    compact5 = compact_patch_set(
        selected_limit=5,
        constraint_limit=4,
        facts_limit=3,
        procedures_limit=3,
        pitfalls_limit=3,
    )
    compact6 = compact_patch_set(
        selected_limit=6,
        constraint_limit=5,
        facts_limit=4,
        procedures_limit=3,
        pitfalls_limit=3,
    )

    return [
        CandidateSpec(
            candidate_id="baseline",
            description="Unmodified upstream skill.",
            patches=[],
        ),
        CandidateSpec(
            candidate_id="compact-5-allcaps",
            description="More aggressive compactness: selected memory cap 5 plus tighter field caps.",
            patches=compact5,
        ),
        CandidateSpec(
            candidate_id="executor-pref",
            description="Allow executor steps to reuse durable preference memories as hard constraints.",
            patches=patch_executor_reads_preferences(),
        ),
        CandidateSpec(
            candidate_id="directional-contradiction",
            description="Treat contradiction edges directionally so contradicted memories are penalized, not the newer contradictory memory.",
            patches=patch_directional_contradiction(),
        ),
        CandidateSpec(
            candidate_id="executor-pref-directional",
            description="Combine executor preference recall with directional contradiction handling.",
            patches=patch_executor_reads_preferences() + patch_directional_contradiction(),
        ),
        CandidateSpec(
            candidate_id="executor-pref-directional-compact6",
            description="Functional fixes plus moderate packet compactness.",
            patches=patch_executor_reads_preferences() + patch_directional_contradiction() + compact6,
        ),
        CandidateSpec(
            candidate_id="executor-pref-directional-compact5",
            description="Functional fixes plus aggressive compactness tuned against the benchmark suite.",
            patches=patch_executor_reads_preferences() + patch_directional_contradiction() + compact5,
        ),
        CandidateSpec(
            candidate_id="executor-pref-directional-support08-compact5",
            description="Functional fixes plus compactness and a stronger graph-support weight.",
            patches=patch_executor_reads_preferences() + patch_directional_contradiction() + patch_support_weight(0.08) + compact5,
        ),
        CandidateSpec(
            candidate_id="executor-pref-directional-support10-compact5",
            description="Functional fixes plus compactness and an aggressive graph-support weight.",
            patches=patch_executor_reads_preferences() + patch_directional_contradiction() + patch_support_weight(0.10) + compact5,
        ),
        CandidateSpec(
            candidate_id="executor-pref-directional-support08-importance11-compact5",
            description="Functional fixes plus compactness, higher graph support weight, and slightly reduced importance dominance.",
            patches=patch_executor_reads_preferences() + patch_directional_contradiction() + patch_support_weight(0.08) + patch_importance_weight(0.11) + compact5,
        ),
    ]


def apply_patches(repo_root: Path, patches: list[dict[str, str]]) -> list[dict[str, str]]:
    applied: list[dict[str, str]] = []
    for patch in patches:
        path = repo_root / patch["path"]
        text = path.read_text()
        old = patch["old"]
        new = patch["new"]
        if old not in text:
            raise ValueError(f"Patch target not found in {path}: {old[:80]!r}")
        path.write_text(text.replace(old, new, 1))
        applied.append({"path": patch["path"], "old": old, "new": new})
    return applied


def materialize_candidate(base_repo: Path, out_root: Path, candidate: CandidateSpec) -> tuple[Path, list[dict[str, str]]]:
    candidate_root = out_root / candidate.candidate_id
    shutil.copytree(base_repo, candidate_root, dirs_exist_ok=False)
    applied = apply_patches(candidate_root, candidate.patches) if candidate.patches else []
    return candidate_root, applied


def collect_route_metrics(results: list[Any]) -> dict[str, float]:
    route_steps = 0
    selected_memories_total = 0
    selected_blocks_total = 0
    packet_items_total = 0
    hard_constraints_total = 0
    procedures_total = 0
    facts_total = 0
    pitfalls_total = 0

    for result in results:
        for step_output in result.step_outputs.values():
            if not isinstance(step_output, dict) or "packet" not in step_output:
                continue
            route_steps += 1
            packet = step_output["packet"]
            debug = step_output.get("debug", {})
            selected_memories_total += len(packet.get("selected_memory_ids", []))
            selected_blocks_total += sum(1 for b in debug.get("selected_blocks", []) if b.get("selected"))
            hard_constraints_total += len(packet.get("hard_constraints", []))
            procedures_total += len(packet.get("procedures_to_follow", []))
            facts_total += len(packet.get("relevant_facts", []))
            pitfalls_total += len(packet.get("pitfalls_to_avoid", []))
            packet_items_total += (
                len(packet.get("hard_constraints", []))
                + len(packet.get("relevant_facts", []))
                + len(packet.get("procedures_to_follow", []))
                + len(packet.get("pitfalls_to_avoid", []))
                + len(packet.get("open_questions", []))
                + len(packet.get("selected_memory_ids", []))
            )

    denom = max(route_steps, 1)
    return {
        "route_steps": float(route_steps),
        "avg_selected_memories": selected_memories_total / denom,
        "avg_selected_blocks": selected_blocks_total / denom,
        "avg_packet_items": packet_items_total / denom,
        "avg_hard_constraints": hard_constraints_total / denom,
        "avg_procedures": procedures_total / denom,
        "avg_relevant_facts": facts_total / denom,
        "avg_pitfalls": pitfalls_total / denom,
    }


def ranking_tuple(summary: dict[str, Any], metrics: dict[str, float]) -> tuple[float, float, float, float, float]:
    return (
        float(summary["passed_checks"]),
        float(summary["passed_cases"]),
        -float(metrics["avg_packet_items"]),
        -float(metrics["avg_selected_memories"]),
        -float(metrics["avg_selected_blocks"]),
    )


def export_optimized_skill(candidate_repo: Path, dest_root: Path) -> None:
    if dest_root.exists():
        shutil.rmtree(dest_root)
    shutil.copytree(candidate_repo, dest_root)


def write_mutation_report(run_root: Path, evaluations: list[CandidateEvaluation], winner: CandidateEvaluation) -> None:
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "winner": winner.candidate_id,
        "evaluations": [
            {
                "candidate_id": ev.candidate_id,
                "description": ev.description,
                "repo_path": ev.repo_path,
                "router_path": ev.router_path,
                "summary": ev.summary,
                "metrics": ev.metrics,
                "ranking": ev.ranking,
            }
            for ev in evaluations
        ],
    }
    run_root.mkdir(parents=True, exist_ok=True)
    (run_root / "results.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False))

    lines = [
        "# Mutation Loop Summary",
        "",
        f"- Winner: **{winner.candidate_id}**",
        f"- Exported skill: `optimized-skill/`",
        "",
        "## Candidates",
        "",
    ]
    for ev in evaluations:
        lines.extend(
            [
                f"### {ev.candidate_id}",
                "",
                f"- Description: {ev.description}",
                f"- Cases passed: {ev.summary['passed_cases']}/{ev.summary['case_count']}",
                f"- Checks passed: {ev.summary['passed_checks']}/{ev.summary['check_count']}",
                f"- Avg packet items: {ev.metrics['avg_packet_items']:.2f}",
                f"- Avg selected memories: {ev.metrics['avg_selected_memories']:.2f}",
                f"- Avg selected blocks: {ev.metrics['avg_selected_blocks']:.2f}",
                f"- Repo path: `{ev.repo_path}`",
                "",
            ]
        )
    (run_root / "summary.md").write_text("\n".join(lines) + "\n")


def run_mutation_loop(project_root: Path) -> dict[str, Any]:
    base_repo = project_root / "vendor-memory-attention-router"
    benchmarks_root = project_root / "benchmarks"
    cases = discover_cases(benchmarks_root, split="all")
    run_id = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    mutation_run_root = project_root / "mutation-runs" / run_id
    candidates_root = mutation_run_root / "candidates"
    candidates_root.mkdir(parents=True, exist_ok=True)

    evaluations: list[CandidateEvaluation] = []
    for candidate in default_candidates():
        candidate_repo, applied = materialize_candidate(base_repo, candidates_root, candidate)
        router_path = candidate_repo / "skills" / "scripts" / "memory_router.py"
        results = [run_case(case, str(router_path)) for case in cases]
        summary = summarize(results)
        metrics = collect_route_metrics(results)
        ranking = list(ranking_tuple(summary, metrics))

        candidate_payload = {
            "candidate_id": candidate.candidate_id,
            "description": candidate.description,
            "applied_patches": applied,
            "summary": summary,
            "metrics": metrics,
            "results": [
                {
                    "case_id": r.case_id,
                    "split": r.split,
                    "passed": r.passed,
                    "checks_passed": r.checks_passed,
                    "checks_total": r.checks_total,
                }
                for r in results
            ],
        }
        (candidate_repo / "mutation-result.json").write_text(json.dumps(candidate_payload, indent=2, ensure_ascii=False))

        evaluations.append(
            CandidateEvaluation(
                candidate_id=candidate.candidate_id,
                description=candidate.description,
                repo_path=str(candidate_repo),
                router_path=str(router_path),
                summary=summary,
                metrics=metrics,
                ranking=ranking,
            )
        )

    winner = max(evaluations, key=lambda ev: tuple(ev.ranking))
    export_optimized_skill(Path(winner.repo_path), project_root / "optimized-skill")
    write_mutation_report(mutation_run_root, evaluations, winner)

    return {
        "run_root": str(mutation_run_root),
        "winner": winner.candidate_id,
        "optimized_skill": str(project_root / "optimized-skill"),
        "evaluations": [
            {
                "candidate_id": ev.candidate_id,
                "summary": ev.summary,
                "metrics": ev.metrics,
                "ranking": ev.ranking,
            }
            for ev in evaluations
        ],
    }
