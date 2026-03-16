---
name: memory-attention-router
description: Route, write, reflect on, and refresh long-term agent memory for multi-step OpenClaw tasks. Use when work depends on prior sessions, repeated workflows, user preferences, past failures, procedural learnings, or long-running project context. Trigger on explicit preference-memory phrases such as "from now on", "remember that", "always", "prefer", "avoid", "my rule is", and "use this style going forward". Build a compact working-memory packet instead of dumping raw memory or using plain document RAG.
---

# Memory Attention Router Skill

This skill turns long agent memory into a small, role-aware working-memory packet.

Trigger this skill immediately when the user states a durable preference or rule, especially with phrases like:

- from now on
- remember that
- record to memory
- always
- prefer
- avoid
- my rule is
- going forward

Do not treat this as normal document RAG.
Do not dump large raw memory lists into model context.
Route to the right memory blocks, select a small set of memories, compose a compact packet, write back new learnings, and retire stale memories when better evidence appears.

## Step roles

Choose the current step role before reading memory:

- `planner`
- `executor`
- `critic`
- `responder`

Default type preferences:

- `planner` -> `preference`, `procedure`, `summary`
- `executor` -> `procedure`, `episode`, `reflection`
- `critic` -> `reflection`, `preference`, `summary`
- `responder` -> `preference`, `summary`, `procedure`

## Read flow

1. Build a route request with:
   - `goal`
   - `step_role`
   - `session_id` if known
   - `task_id` if known
   - `user_constraints`
   - `recent_failures`
   - `unresolved_questions`
2. Run:
   `python3 {baseDir}/scripts/memory_router.py route --input-json '<JSON>'`
3. Read the `packet`.
4. Use the packet in downstream reasoning.
5. Inspect `debug.selected_blocks` and `debug.selected_memories` when you need to understand why the router picked a particular packet.

The router uses a deterministic two-stage flow:

1. select the best blocks from `task_scoped`, `session_scoped`, `durable_global`, and `recent_fallback`
2. score memories only inside the selected blocks

## Write flow

Store memory after important outcomes:

`python3 {baseDir}/scripts/memory_router.py add --input-json '<JSON>'`

Write memory when:

- a tool call succeeds and the result will matter later
- a tool call fails in a reusable way
- the user states a durable preference or rule
- the agent learns a reusable procedure
- the agent reaches a stable summary worth keeping

If a new memory replaces an older one, include `replaces_memory_id` in the add payload. The older memory will be retired, linked forward to the new memory, and marked with a stored retirement reason.

## Reflect flow

At the end of a meaningful task or after a failure cluster, create reflection and optionally procedure memory:

`python3 {baseDir}/scripts/memory_router.py reflect --input-json '<JSON>'`

## Refresh flow

When new evidence invalidates or replaces older memory:

`python3 {baseDir}/scripts/memory_router.py refresh --input-json '<JSON>'`

Use refresh to:

- deactivate stale memories
- mark replacements with `replacement_memory_id`
- persist why the memory was retired with `refresh_reason`
- create contradiction links when a replacement exists

## Packet rules

A good packet contains:

- `hard_constraints`
- `relevant_facts`
- `procedures_to_follow`
- `pitfalls_to_avoid`
- `open_questions`
- `selected_memory_ids`

Keep packets small:

- prefer 4 to 8 selected memories
- never include more than 10 unless the user explicitly wants a retrospective
- prefer summaries and procedures over raw episodes when both exist

## Bootstrap

Initialize the database:

`python3 {baseDir}/scripts/memory_router.py init`

Default DB path behavior:

- if `MAR_DB_PATH` is set, that path is used
- otherwise, when installed at `<workspace>/skills/memory-attention-router`, the default is `<workspace>/.openclaw-memory-router.sqlite3`

Inspect stored memories:

`python3 {baseDir}/scripts/memory_router.py list --limit 20`

Inspect one memory:

`python3 {baseDir}/scripts/memory_router.py inspect --memory-id <ID>`

## File guide

See:

- [reference guide](references/REFERENCE.md)
- [memory schema](references/MEMORY_SCHEMA.md)
- [prompt templates](references/PROMPTS.md)
- [testing guide](references/TESTING.md)

## Important behavior rules

- Prefer long-lived, verified, reusable memory over noisy transient notes.
- When in doubt, write a `summary` instead of a verbose raw note.
- Use `preference` only for stable user or system constraints.
- Use `procedure` only for instructions that should be reused later.
- Use `reflection` for lessons, pitfalls, and failure patterns.
- Use `episode` for concrete events or observations.
- If two active memories conflict, retire the stale one or add a contradiction edge.
- Treat prompt templates as optional reference material; the default router is fully deterministic and local.
