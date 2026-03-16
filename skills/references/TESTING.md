# Testing Guide

## 1. Put the skill in your workspace

Place the skill folder at:

```text
<your-openclaw-workspace>/skills/memory-attention-router
```

If you are using this Git repo directly, copy the repo's `skills/` directory so that:

```text
<your-openclaw-workspace>/skills/memory-attention-router/SKILL.md
```

exists exactly at that path.

## 2. Initialize the database

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py init
```

Default DB path behavior:

- with `MAR_DB_PATH`, that explicit path is used
- without `MAR_DB_PATH`, and with standard install layout, DB defaults to:
  `<your-openclaw-workspace>/.openclaw-memory-router.sqlite3`

Optional custom DB path:

```bash
MAR_DB_PATH=/absolute/path/to/.memory-router.sqlite3 python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py init
```

## 3. Route a packet

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py route --input-json '{
  "session_id":"sess_demo_001",
  "task_id":"task_openclaw_skill",
  "goal":"Build and test an OpenClaw skill for long-term agent memory routing",
  "step_role":"planner",
  "user_constraints":["Use English only.","Keep the explanation implementation-focused.","Do not turn this into plain document RAG."],
  "recent_failures":["FTS query broke due to punctuation"],
  "unresolved_questions":["how to structure skill files","how to refresh stale memories"]
}'
```

Inspect the route trace in:

- `debug.selected_blocks`
- `debug.selected_memories`

## 4. Add a new memory

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py add --input-json '{
  "memory_type":"reflection",
  "abstraction_level":2,
  "role_scope":"critic",
  "session_id":"sess_demo_001",
  "task_id":"task_openclaw_skill",
  "title":"Need sanitized FTS queries",
  "summary":"When routing through SQLite FTS5, sanitize punctuation and fallback to recency if no lexical terms remain.",
  "details":{"why":"Unescaped punctuation can break MATCH queries."},
  "keywords":["sqlite","fts5","query","sanitize"],
  "tags":["failure","reflection","router"],
  "source_refs":["local-test"],
  "importance":0.82,
  "confidence":0.93,
  "success_score":0.70
}'
```

Add a replacement memory:

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py add --input-json '{
  "memory_type":"procedure",
  "title":"Validated workflow",
  "summary":"Use a workspace-level skill folder before iterating on prompts so the skill overrides shared copies cleanly.",
  "replaces_memory_id":"mem_old_001"
}'
```

## 5. Reflect

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py reflect --input-json '{
  "session_id":"sess_demo_001",
  "task_id":"task_openclaw_skill",
  "goal":"Build an OpenClaw skill for memory routing",
  "outcome":"completed",
  "what_worked":["workspace skill precedence","structured packet composition"],
  "what_failed":["raw context dumping"],
  "lessons":["Use role-aware routing before every major step."],
  "next_time":["Write procedure memories for stable workflows."],
  "create_procedure":true
}'
```

## 6. Refresh stale memory

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py refresh --input-json '{
  "stale_memory_ids":["mem_replace_me"],
  "replacement_memory_id":"mem_newer_one",
  "refresh_reason":"Superseded by validated workflow."
}'
```

## 7. Debugging

List memories:

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py list --limit 50
```

Inspect one:

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py inspect --memory-id <MEMORY_ID>
```

Show recent packets:

```bash
python3 <your-openclaw-workspace>/skills/memory-attention-router/scripts/memory_router.py packets --limit 10
```
