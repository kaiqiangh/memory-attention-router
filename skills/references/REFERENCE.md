# Reference Guide

This skill implements attention-style memory routing for OpenClaw.

## Goal

Convert a large memory store into a compact working-memory packet tuned to the current step role:

- planner
- executor
- critic
- responder

## Memory philosophy

This skill is not plain RAG.

Instead of:

1. encode everything
2. retrieve top-k chunks
3. paste them into context

it does:

1. gather deterministic candidates from scope matches, FTS recall, durable memory, and recent fallback
2. assign each candidate to one block: `task_scoped`, `session_scoped`, `durable_global`, or `recent_fallback`
3. score and select the best blocks
4. score memories only inside those selected blocks
5. compose a compact working-memory packet
6. write back learnings and retire stale memory when needed

## Memory types

- `episode` - concrete event, observation, tool result, failure, or action
- `summary` - compressed session or task-level summary
- `reflection` - lesson, warning, diagnosis, or postmortem
- `procedure` - reusable steps for future tasks
- `preference` - durable user or system preference or constraint

## Abstraction levels

- `0` - raw or immediate
- `1` - session-level
- `2` - task-level
- `3` - long-term or durable

## Recommended writing rules

### `episode`

Use when:

- a tool produced an important result
- a tool failed in a way that may happen again
- the agent observed something concrete that should be recoverable later

Avoid when:

- the event is obvious and immediately superseded
- the content is only temporary scratch work

### `summary`

Use when:

- a session or subtask finished
- several raw events can be compressed into a short stable note

### `reflection`

Use when:

- a failure pattern matters
- a lesson should affect future behavior
- a retry strategy or caution is worth remembering

### `procedure`

Use when:

- the steps are reusable
- the procedure has already worked or is strongly grounded
- the agent should follow these steps first next time

### `preference`

Use when:

- the user expresses a stable preference
- the environment has a durable rule or hard constraint

## Route scoring logic

The router uses these broad signals:

- block-level scope bias
- step-role compatibility
- task and session scope match
- lexical overlap with goal, constraints, failures, and open questions
- importance
- confidence
- success score
- freshness
- graph support or contradiction edges

The exact weights live in:

`scripts/memory_router.py`

## Working-memory packet design

Every packet should be small and structured.

Target shape:

- `hard_constraints`
- `relevant_facts`
- `procedures_to_follow`
- `pitfalls_to_avoid`
- `open_questions`
- `selected_memory_ids`

Composition is strict by type:

- `preference` -> `hard_constraints`
- `procedure` -> `procedures_to_follow`
- `reflection` -> `pitfalls_to_avoid`
- `summary` and `episode` -> `relevant_facts`

The packet is the input the downstream reasoning step should consume.

## Replacement and refresh policy

Use replacement or refresh whenever:

- a new memory supersedes an old one
- an old preference is explicitly changed
- a procedure is proven wrong
- a summary is outdated after better evidence appears

Recommended actions:

1. mark stale memory inactive
2. set `replaced_by_memory_id`
3. persist a retirement reason
4. add a `contradicts` edge when a replacement exists
5. keep the new memory active

## Suggested integration points in an agent graph

Read before:

- planning
- execution after a failure
- critique or review
- final response composition

Write after:

- important tool result
- major failure
- task completion
- preference discovery
- procedure discovery

Refresh after:

- contradictions
- explicit corrections
- updated durable rules
