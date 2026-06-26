---
name: using-memorize
description: Use when you need to recall cross-session decisions/progress or "why did we decide X"; check whether memorize's memory capture is healthy; or import pre-existing notes into the shared project brain — for projects using memorize.
---

# Using memorize

## Overview
memorize is the project's shared brain: past decisions, rationale, and cross-session progress in a local DB — NOT in the repo's files. Grep finds what was written to disk; memorize finds what was decided in conversation or by other sessions and never written down.

## When to use
- **Recall** — what another or earlier session worked on, decided, or handed off; a decision/rationale discussed but not in any doc; "what did we decide / why did we choose X" when the repo has no clear answer.
- **Health** — checking whether memory capture / consolidation is actually working.
- **Import** — getting pre-existing notes/decisions into the shared brain.

## When NOT to use
- The answer lives in code or docs → grep/read the files. memorize does not replace reading the repo.
- A single file/function lookup → Glob/Grep/Read.

For recall, grep silently omits conversation-only decisions — so for "what did we decide" or cross-session questions, check memorize even when grep returned something.

## Recall
`memorize search "<query>"` · `memorize task resume` · `memorize session activity`

`memorize search` returns truncated snippets — to read a memory's full text, open the source it cites (often a `docs/` spec).

## Health — "is capture/consolidation working?"
Run `memorize doctor` (add `--json` for detail). Trust its output — it aggregates hooks, watermarks, last attempt, and pending observations. Do NOT hand-query the SQLite DB to reconstruct health, and do NOT run `memorize consolidate` to "check" — that executes a real consolidation boundary (side effect).

## Import pre-existing notes into shared memory
`memorize memory import --source <label>`, piping a JSON array on stdin:
`[{"kind":"decision|rationale|progress","text":"...","salience":1-10}]`. Idempotent (dedup by kind+text). That's the full schema — don't read source to rediscover it.

## Conventions
Use the `memorize` binary directly (not `node dist/...`).

## Common mistake
Answering a cross-session or "why did we decide" question from grep alone and calling it complete — grep can't see decisions only ever spoken in conversation.
