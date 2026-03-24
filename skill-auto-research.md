# Memory Attention Router Autoresearch Harness

This project wraps the upstream `memory-attention-router` skill in a **machine-evaluable benchmark harness**.

## Goal

Turn the skill from a manually tested package into something closer to an autoresearch-ready artifact:

1. seed a fresh memory DB for each benchmark case
2. run deterministic `add` / `route` / `reflect` / `refresh` flows
3. assert on routed packets and memory state transitions
4. aggregate results by `dev`, `holdout`, and `adversarial` splits
5. provide a stable surface for future mutation and promotion loops

## What is included

- vendored upstream repo under `vendor-memory-attention-router/`
- benchmark fixtures under `benchmarks/`
- stdlib-only runner under `src/mar_bench/`
- venv bootstrap script under `scripts/setup_venv.sh`
- evaluation CLI under `scripts/run_benchmarks.py`
- mutation loop CLI under `scripts/run_mutation_loop.py`
- design docs under `docs/`

## Benchmark splits

- `dev/` — core functional correctness
- `holdout/` — regression guardrail cases not used for iterative tuning
- `adversarial/` — stale memory, contradiction, and dense-memory stress cases

## Quickstart

### 1. Create and activate the virtual environment

```bash
./scripts/setup_venv.sh
source .venv/bin/activate
```

### 2. Run all benchmark splits

```bash
python scripts/run_benchmarks.py --split all
```

### 3. Run one split

```bash
python scripts/run_benchmarks.py --split dev
```

### 4. Run one specific case

```bash
python scripts/run_benchmarks.py --case dev-001-preference-route-reuse
```

### 5. Run the mutation loop

```bash
python scripts/run_mutation_loop.py
```

This will:

- materialize several candidate variants
- run all benchmark splits against each candidate
- pick the best candidate by correctness-first, compactness-second ranking
- export the current winner to `optimized-skill/`

## Output

Benchmark reports are written to `runs/<timestamp>/`:

- `summary.json`
- `summary.md`
- `cases/<case-id>.json`

Mutation loop reports are written to `mutation-runs/<timestamp>/`:

- `results.json`
- `summary.md`
- `candidates/<candidate-id>/...`

The current best export is written to:

- `optimized-skill/`

If you want to upload the optimized skill to GitHub, `optimized-skill/` is the directory to push.

## Current scope

This harness evaluates the current upstream router logic.

It does **not yet** implement:

- automatic mutation of router weights
- automatic champion promotion
- online traffic replay
- model-in-the-loop reflective judging

Those should come later, after the benchmark surface stabilizes.
