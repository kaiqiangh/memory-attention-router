# Memory Attention Router Skill

An OpenClaw skill for deterministic long-term memory routing.

This project helps an agent convert large historical memory into a small, role-aware working-memory packet for the current step. It is built as a local-first skill package with a Python router and SQLite persistence.

## 1) Introduction

Most agent memory systems fail in one of two ways:

- they forget important prior decisions, preferences, and failure patterns
- they retrieve too much history and overload the model context

`memory-attention-router` is designed to avoid both.

Instead of dumping raw history into prompts, it routes memory in two stages:

1. pick the best memory blocks for the current step
2. pick the best memories inside those blocks

Then it emits a compact packet with only what the next reasoning step should use.

## 2) Why create this skill

This skill exists to solve practical problems in multi-step OpenClaw workflows:

- repeated tasks should reuse successful procedures
- user preferences should persist across sessions
- known pitfalls should be surfaced before repeating mistakes
- long-running projects need durable task memory without context bloat

In short: retain useful experience, discard noise, and keep reasoning inputs small.

## 3) Intuition: inspired by Attention Residual (Moonshot)

The intuition is inspired by the "attention residual" way of thinking often associated with Moonshot/Kimi discussions:

- keep a compact, high-signal state that survives across steps
- do not feed the full history every time
- preserve what matters most for the next decision

This skill applies that intuition to agent memory:

- long-term store in SQLite
- selective retrieval by role and task context
- compact "residual-like" packet for the active step

It is an intuition-level inspiration, not an implementation of Moonshot internals.

Reference: https://github.com/MoonshotAI/Attention-Residuals

## 4) Principle, core logic, and rationale

### Core principle

Memory should be routed, not dumped.

### Core logic

The router (`skills/scripts/memory_router.py`) follows this loop:

1. `route`: build a packet for the current `step_role`
2. `add`: write reusable outcomes into memory
3. `reflect`: summarize lessons after meaningful work
4. `refresh`: retire stale memory when contradicted

### Two-stage retrieval

Stage A: block routing

- `task_scoped`
- `session_scoped`
- `durable_global`
- `recent_fallback`

Stage B: in-block scoring

- role compatibility
- lexical overlap with goal/constraints/questions/failures
- importance, confidence, success score
- freshness
- graph support/contradiction edges

### Typed packet composition

The output packet uses strict mapping:

- `preference` -> `hard_constraints`
- `procedure` -> `procedures_to_follow`
- `reflection` -> `pitfalls_to_avoid`
- `summary` / `episode` -> `relevant_facts`

Rationale:

- better control over what enters the next reasoning step
- lower token noise than flat top-k retrieval
- clearer lifecycle for writing, replacing, and retiring memory

### Code mapping to the "attention residual" intuition

This project does not implement Moonshot internals. It applies the same engineering intuition: keep a compact, high-signal state and update it incrementally.

The mapping in code is explicit:

- Role-aware attention prior:
  `ROLE_TO_TYPES`, `TYPE_PRIORITY`, and `BLOCK_PRIORITY` in `skills/scripts/memory_router.py`
- Coarse attention (select memory blocks first):
  `fetch_candidate_pool` -> `classify_block` -> `score_block`
- Fine attention (rank memories inside chosen blocks):
  `score_row`
- Residual-like working state (compact packet for the current step):
  `route_memory` packet assembly plus `debug.selected_blocks` and `debug.selected_memories`
- Residual update lifecycle:
  `add_memory`, `reflect_memory`, `refresh_memory`, and `retire_memories`
- Consistency correction signal:
  `edge_bonus` (supports/contradicts/derived graph edges) adjusts ranking

In short:

- block routing = coarse attention
- in-block scoring = fine attention
- packet = residual-like state passed to the next reasoning step
- add/reflect/refresh = residual state updates over time

### End-to-end process (full lifecycle)

The full runtime loop is:

1. Input state arrives for a step:
   goal, role, task/session scope, user constraints, failures, unresolved questions.
2. Candidate recall runs:
   task/session exact matches, FTS lexical recall, durable global memories, recent fallback.
3. Block routing chooses top blocks:
   `task_scoped`, `session_scoped`, `durable_global`, `recent_fallback`.
4. In-block scoring ranks memories:
   role match, lexical overlap, importance, confidence, success, freshness, graph signals.
5. Packet composition compresses output:
   constraints/facts/procedures/pitfalls/questions + selected memory IDs.
6. Downstream reasoning consumes only this compact packet.
7. Writeback persists outcomes:
   new memory entries (`add`) and synthesized lessons/procedures (`reflect`).
8. Refresh handles contradictions:
   stale memories are retired, linked to replacements, and marked with retirement reasons.
9. Next step repeats:
   the updated store influences future routing, so memory quality compounds over time.

Why this works better than flat retrieval:

- the model sees less noise
- each step gets role-appropriate context
- stale knowledge is actively retired instead of silently accumulating
- routing decisions are inspectable through debug traces

## Project layout

```text
.
├── README.md
├── LICENSE
└── skills/
    ├── SKILL.md
    ├── scripts/
    │   ├── memory_router.py
    │   ├── schema.sql
    │   └── prompts/
    ├── references/
    │   ├── REFERENCE.md
    │   ├── MEMORY_SCHEMA.md
    │   ├── PROMPTS.md
    │   └── TESTING.md
    └── assets/examples/
        ├── add-memory.json
        ├── route-memory.json
        ├── refresh-memory.json
        └── openclaw.config.snippet.jsonc
```

## Prerequisites

- OpenClaw with skills enabled
- `python3`
- SQLite with FTS5 support

## Quick start

1. Install the skill folder in your OpenClaw workspace.

Important: in this repository, the actual skill directory is `./skills`.
Copy `./skills` to:

```text
<workspace>/skills/memory-attention-router
```

After copying, this file must exist:

```text
<workspace>/skills/memory-attention-router/SKILL.md
```

2. Configure database path.

By default (without `MAR_DB_PATH`), the router now uses:

```text
<workspace>/.openclaw-memory-router.sqlite3
```

Set `MAR_DB_PATH` only if you want to override that location:

```json
{
  "skills": {
    "entries": {
      "memory-attention-router": {
        "enabled": true,
        "env": {
          "MAR_DB_PATH": "/absolute/path/to/.openclaw-memory-router.sqlite3"
        }
      }
    }
  }
}
```

3. Initialize the DB:

```bash
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py init
```

## CLI reference

Use absolute script paths to avoid cwd-dependent DB behavior:

```bash
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py init
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py add --input-json '<JSON>'
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py route --input-json '<JSON>'
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py reflect --input-json '<JSON>'
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py refresh --input-json '<JSON>'
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py list --limit 20
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py inspect --memory-id <ID>
python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py packets --limit 10
```

## 5) Fast IM verification scenarios (clear pass/fail)

Use this section as a practical acceptance test.

### Preflight (run once)

```bash
export OC_WS=/root/.openclaw/workspace
export ROUTER="$OC_WS/skills/memory-attention-router/scripts/memory_router.py"
python3 "$ROUTER" init
```

Pass condition:

- `db_path` in output is `/root/.openclaw/workspace/.openclaw-memory-router.sqlite3`

If not, set `MAR_DB_PATH` in OpenClaw skill config and start a new OpenClaw session.

### Scenario A: preference is written from IM

In IM, send exactly:

```text
From now on, answer architecture explanations in concise English and focus on implementation detail.
```

Verify:

```bash
python3 "$ROUTER" list --limit 100 | python3 -c 'import sys,json;d=json.load(sys.stdin);prefs=[i for i in d["items"] if i["memory_type"]=="preference"];print("preference_count=",len(prefs));print("\n".join(f"{x[\"id\"]} | {x[\"title\"]}" for x in prefs[:10]))'
```

Pass condition:

- at least one recent `preference` memory appears

### Scenario B: preference is reused in routed packet

In IM, send:

```text
Plan a backend architecture for an event-driven notification service.
```

Verify:

```bash
python3 "$ROUTER" route --input-json '{
  "goal":"Plan backend architecture for an event-driven notification service",
  "step_role":"planner",
  "session_id":"im_verify_pref_reuse",
  "task_id":"im_verify_pref_reuse",
  "user_constraints":[],
  "recent_failures":[],
  "unresolved_questions":[]
}' | python3 -c 'import sys,json;d=json.load(sys.stdin);print("hard_constraints=",d["packet"]["hard_constraints"]);print("selected_blocks=",d["debug"]["selected_blocks"]);print("selected_memory_ids=",d["packet"]["selected_memory_ids"])'
```

Pass condition:

- `hard_constraints` includes your style preference semantics (concise English + implementation detail)

### Scenario C: procedure memory is reused

In IM, send first:

```text
Create a reusable procedure for adding memory, routing memory, and verifying packet quality.
```

Then send:

```text
Run the same workflow for a new task and reuse the procedure you stored.
```

Verify:

```bash
python3 "$ROUTER" route --input-json '{
  "goal":"Execute the same memory-routing workflow for a new task",
  "step_role":"executor",
  "session_id":"im_verify_proc_reuse",
  "task_id":"im_verify_proc_reuse",
  "user_constraints":[],
  "recent_failures":[],
  "unresolved_questions":[]
}' | python3 -c 'import sys,json;d=json.load(sys.stdin);print("procedures_to_follow=",d["packet"]["procedures_to_follow"]);print("selected_memories=",d["debug"]["selected_memories"])'
```

Pass condition:

- `procedures_to_follow` is non-empty and clearly procedural

### Scenario D: stale rule is retired after replacement

In IM, send:

```text
Replace my previous architecture style rule with: concise English, implementation detail first, and explicit bullet points. Retire the old rule.
```

Verify:

```bash
python3 "$ROUTER" list --limit 200 | python3 -c 'import sys,json;d=json.load(sys.stdin);ret=[i for i in d["items"] if i["memory_type"]=="preference" and i["is_active"]==0 and i.get("replaced_by_memory_id")];print("retired_preference_count=",len(ret));print(ret[:5])'
```

Pass condition:

- at least one inactive preference exists with `replaced_by_memory_id` populated

Optional deep check:

```bash
python3 "$ROUTER" inspect --memory-id <retired_preference_id>
```

Confirm:

- `is_active` is `0`
- `replaced_by_memory_id` is not null
- `retired_reason` is not empty

## Example payload files

- `skills/assets/examples/add-memory.json`
- `skills/assets/examples/route-memory.json`
- `skills/assets/examples/refresh-memory.json`

Use these as templates for manual testing and integrations.

## Troubleshooting: skill not triggered

If OpenClaw replies with generic memory behavior (for example writing only to a default memory note) and does not call this router, check:

1. Skill path: confirm `<workspace>/skills/memory-attention-router/SKILL.md` exists (not nested under an extra `skills/` directory).
2. New session: restart or open a new OpenClaw session after installing or editing `SKILL.md`.
3. Trigger phrase: use explicit durable-preference language such as "from now on", "remember that", "always", "prefer", or "avoid".
4. Runtime check: run `python3 <workspace>/skills/memory-attention-router/scripts/memory_router.py list --limit 20` and confirm preference memories are being written.

## License

MIT. See `LICENSE`.
