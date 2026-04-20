# OSS Release: Docs & Cleanup Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Token Dashboard into a public-repo-ready codebase — rewrite stale docs, add standard OSS files (LICENSE, CONTRIBUTING, README for beginners), fix `HEAD` 501, and document the Skills-tokens limitation — without publishing, CI, or release tagging.

**Architecture:** Three work-lanes (Backend / QA / Instructor) plus a Synthesis pass. Bulk of deliverables are Markdown docs; the only code diff is a `do_HEAD` handler in `token_dashboard/server.py` and a `.gitignore` line. Audit tasks produce findings appended to this plan's `## Findings` section, which later doc tasks consume as source-of-truth.

**Tech Stack:** Python 3 stdlib, SQLite, vanilla JS + ECharts (all already in place). No new dependencies.

**Spec:** `docs/superpowers/specs/2026-04-19-oss-release-design.md`

---

## File Structure

**New files (created by this plan):**
- `LICENSE` — MIT, 2026, Nathan Herkelman
- `CONTRIBUTING.md` — short contributor quickstart (~300 words)
- `docs/ARCHITECTURE.md` — data-flow doc (400–800 words, 1 diagram)
- `docs/CUSTOMIZING.md` — env vars, `pricing.json` format, "add a new route" walkthrough
- `docs/GLOSSARY.md` — term definitions (student-voiced)
- `docs/EXAMPLE_WALKTHROUGH.md` — narrative first-five-minutes tour
- `docs/VERIFICATION.md` — QA checklist with pass/fail status
- `docs/KNOWN_LIMITATIONS.md` — aggregated "cool but incomplete" list

**Modified files:**
- `README.md` — rewritten for beginners + agent-parseable install
- `CLAUDE.md` — rewritten to describe codebase as-built
- `.gitignore` — add `.claude/`
- `token_dashboard/server.py` — add `do_HEAD` (one-line delegation to `do_GET`)
- `tests/test_server.py` — one new test for HEAD
- `pricing.json` — only if Task 4 finds stale entries

**Deleted files:**
- `docs/customizations.md` — superseded

**Unchanged:**
- `cli.py`, `token_dashboard/{db,scanner,skills,pricing,tips}.py`, `web/**`, all other tests.

---

## Dependency notes

- Tasks 1–6 are the Backend audit. Task 2 (HEAD fix) is the only one that writes code; others write findings notes.
- Tasks 7–9 are Backend docs. They consume findings from Tasks 1–6.
- Tasks 10–14 are QA. Task 14 (KNOWN_LIMITATIONS) consumes the Task 1 finding about Skills scanned roots.
- Tasks 15–17 are Instructor docs. Task 15 (README) consumes Task 13's (VERIFICATION) fact-checks.
- Tasks 18–22 are Synthesis and must run after the doc tasks so cross-linking is accurate.

If you dispatch subagents, Tasks 1, 3, 4, 5, 6 can run in parallel (all read-only audits). Everything else has sequential dependencies.

---

## Task 1: Audit Skills scanned roots (finding)

**Files:**
- Read: `token_dashboard/skills.py:19-23`, `token_dashboard/server.py:105-111`
- Update: this plan's `## Findings` section (append entry titled "1. Skills scanned roots")

- [ ] **Step 1: Read the two roots references**

Run: `grep -n "_DEFAULT_ROOTS\|cached_catalog" token_dashboard/skills.py token_dashboard/server.py`
Confirm: `_DEFAULT_ROOTS` = `[~/.claude/skills, ~/.claude/scheduled-tasks, ~/.claude/plugins]`.

- [ ] **Step 2: Spot-check that the server uses this catalog to populate `tokens_per_call`**

Confirm `server.py:105-111` looks up each skill slug in `cached_catalog()` and sets `r["tokens_per_call"] = info["tokens"] if info else None`.

- [ ] **Step 3: Write the finding**

Append to `## Findings` in this plan file:

```markdown
### 1. Skills scanned roots — confirmed

`token_dashboard/skills.py:19-23` scans exactly three roots:
- `~/.claude/skills/`
- `~/.claude/scheduled-tasks/`
- `~/.claude/plugins/` (and its nested `marketplaces/…/plugins/<plugin>/skills/` tree)

Skills whose `SKILL.md` lives outside those roots (project-local `.claude/skills/`, or subagent dispatches via `Task` tool with a skill-shaped `subagent_type`) are invoked correctly by Claude Code but have no entry in the catalog. The `/api/skills` route (`server.py:105-111`) still returns invocation counts for those skills — only `tokens_per_call` is null.

**Impact:** documented as a known limitation; no code change this pass.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-04-19-oss-release-design.md
git commit -m "docs(plan): Task 1 finding — Skills scanned roots confirmed"
```

---

## Task 2: Fix `HEAD` returning 501 (TDD)

**Files:**
- Modify: `token_dashboard/server.py` (add `do_HEAD` inside the `H` handler class, near `do_GET`)
- Modify: `tests/test_server.py` (add `test_head_delegates_to_get`)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_server.py` after `test_plan_json`:

```python
    def test_head_returns_200_not_501(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
            self.assertEqual(resp.read(), b"")

    def test_head_api_endpoint(self):
        req = urllib.request.Request(f"http://127.0.0.1:{self.port}/api/overview", method="HEAD")
        with urllib.request.urlopen(req) as resp:
            self.assertEqual(resp.status, 200)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest tests.test_server -v`
Expected: `test_head_returns_200_not_501` and `test_head_api_endpoint` both fail with HTTP 501.

- [ ] **Step 3: Implement `do_HEAD`**

In `token_dashboard/server.py`, inside the `H` handler class (after the `log_message` method, before `do_GET`), add exactly these two lines:

```python
        def do_HEAD(self):
            return self.do_GET()
```

No inline comment needed. Context for why this works: per HTTP/1.1, clients MUST ignore the body on HEAD responses, which is how Python's stdlib `SimpleHTTPRequestHandler` handles HEAD too. If a future change needs strict server-side body suppression, override `_send_json` / `_serve_static` to short-circuit when `self.command == "HEAD"`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_server -v`
Expected: all server tests green, including the two new HEAD tests.

- [ ] **Step 5: Run the full suite to confirm no regressions**

Run: `python3 -m unittest discover tests`
Expected: `OK` with 68 tests (was 66 + 2 new).

- [ ] **Step 6: Manual sanity check with curl**

Start a dashboard and check the fix end-to-end:

```bash
python3 cli.py dashboard --no-scan --no-open &
sleep 2
curl -I http://127.0.0.1:8080/
kill %1
```

Expected: `HTTP/1.0 200 OK` (or `HTTP/1.1 200 OK`), NOT `501 Unsupported method ('HEAD')`.

- [ ] **Step 7: Commit**

```bash
git add token_dashboard/server.py tests/test_server.py
git commit -m "fix(server): respond to HEAD by delegating to GET"
```

---

## Task 3: Audit scanner completeness (finding)

**Files:**
- Read: `token_dashboard/scanner.py:46-122` (parse functions)
- Read: a real JSONL from `~/.claude/projects/`
- Update: this plan's `## Findings` section (append entry titled "3. Scanner completeness")

- [ ] **Step 1: Pick one real JSONL**

```bash
ls -S ~/.claude/projects/*/*.jsonl | head -1
```

Record the path. Call it `$J`.

- [ ] **Step 2: Sample an assistant `message.usage` block from it**

```bash
python3 -c "
import json, sys
path = '$J'  # replace
for line in open(path):
    rec = json.loads(line)
    if rec.get('type') == 'assistant' and (rec.get('message') or {}).get('usage'):
        print(json.dumps(rec['message']['usage'], indent=2))
        print('model:', rec['message'].get('model'))
        break
"
```

Compare against the fields `scanner._usage` reads (`input_tokens`, `output_tokens`, `cache_read_input_tokens`, `cache_creation.ephemeral_5m_input_tokens`, `cache_creation.ephemeral_1h_input_tokens`).

- [ ] **Step 3: Sample a `tool_use` and `tool_result` block**

Same file, different filter:

```bash
python3 -c "
import json
path = '$J'
for line in open(path):
    rec = json.loads(line)
    content = (rec.get('message') or {}).get('content') or []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get('type') in ('tool_use', 'tool_result'):
                print(b.get('type'), '->', {k: (v if isinstance(v, (str, int, float, bool, type(None))) else type(v).__name__) for k, v in b.items()})
" | head -20
```

Confirm `_extract_tools` (line 80) and `_extract_results` (line 100) cover the fields present. The only thing scanner captures from `tool_use` is `name` + a `target` keyed by a whitelist in `_TARGET_FIELDS` (line 32); other fields are intentionally dropped.

- [ ] **Step 4: Write the finding**

Append to `## Findings`:

```markdown
### 3. Scanner completeness — confirmed

Every `message.usage` field Claude Code emits is captured: input, output, cache-read, cache-create-5m, cache-create-1h. Top-level fields captured: `uuid`, `parentUuid`, `sessionId`, `cwd`, `gitBranch`, `version` (→ `cc_version`), `entrypoint`, `type`, `isSidechain`, `agentId`, `timestamp`, `promptId`. Nested `message.*` captured: `model`, `stop_reason`, `id` (→ `message_id` for streaming-snapshot dedup).

Tool calls: `tool_use` blocks are captured with `name` + the whitelisted primary-input field (see `scanner._TARGET_FIELDS`). Other input fields (e.g. Edit's `old_string`/`new_string`) are intentionally dropped — the dashboard only needs the identifier/target, not the body. `tool_result` blocks are captured as synthetic `_tool_result` rows with `result_tokens = chars // 4` (approximate).

**Intentionally not captured:** per-block tool-call timings, tool-call argument bodies beyond the primary target, any field outside `message.usage` and `message.content`. This matches the spec intent ("aggregate analytics, not a replay of every byte").
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-04-19-oss-release-design.md
git commit -m "docs(plan): Task 3 finding — scanner completeness confirmed"
```

---

## Task 4: Audit pricing.json freshness

**Files:**
- Read: `pricing.json`
- Possibly modify: `pricing.json` (only if stale)
- Update: this plan's `## Findings` section (append entry titled "4. Pricing freshness")

- [ ] **Step 1: Read current pricing.json**

```bash
cat pricing.json
```

Required entries (per spec): Opus 4.7, Sonnet 4.6, Haiku 4.5.

- [ ] **Step 2: Confirm entries present**

Check `pricing.json` `models` object contains keys exactly `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5`. (Opus 4.6 is present as a fallback — harmless.)

Sanity-check the rates against Anthropic's public pricing as of the spec date (2026-04-19):

| Model | input $/M | output $/M | cache read $/M | cache create 5m $/M |
|---|---|---|---|---|
| claude-opus-4-7 | 15.00 | 75.00 | 1.50 | 18.75 |
| claude-sonnet-4-6 | 3.00 | 15.00 | 0.30 | 3.75 |
| claude-haiku-4-5 | 1.00 | 5.00 | 0.10 | 1.25 |

If the file matches, no code change.

- [ ] **Step 3: If any rate is off, patch it**

If the file needs to change:

```bash
# Edit the specific rate field(s) via Edit tool, not sed.
# Commit message: "chore(pricing): refresh rates for <model>"
```

If the file does NOT need to change, skip to Step 4.

- [ ] **Step 4: Write the finding**

Append to `## Findings`:

```markdown
### 4. Pricing freshness — confirmed (no changes)

`pricing.json` contains current entries for `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5` matching Anthropic's public per-million-token rates as of 2026-04-19. `claude-opus-4-6` is kept as a fallback for older transcripts. The `tier_fallback` object covers unknown model names by family (opus / sonnet / haiku).
```

If a rate was updated, adjust the wording to "refreshed <field> for <model> from $X to $Y" and include the reason.

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/plans/2026-04-19-oss-release-design.md pricing.json
git commit -m "docs(plan): Task 4 finding — pricing freshness"
```

(If only the plan was updated, drop `pricing.json` from the `git add`.)

---

## Task 5: Audit SQL injection surface (finding)

**Files:**
- Read: `token_dashboard/db.py`, `token_dashboard/server.py`, `token_dashboard/scanner.py`, `token_dashboard/tips.py`, `token_dashboard/pricing.py`
- Update: this plan's `## Findings` section (append entry titled "5. SQL injection surface")

- [ ] **Step 1: Grep for f-string SQL**

Run (via Grep tool, not bash):
Pattern: `f\"\"\"|f\".*(SELECT|INSERT|UPDATE|DELETE|FROM|WHERE)`
Path: `token_dashboard/`

- [ ] **Step 2: For every hit, confirm user-supplied values are bound with `?`**

Known hits from the current code (already inspected while writing this plan):

| File:Line | What the f-string interpolates | Safe? |
|---|---|---|
| `db.py:127-129` | `col` (hardcoded "timestamp") → WHERE clause | Yes — `col` is caller-controlled, not user input; values use `?` |
| `db.py:191,212,231,258,273,317,345,362` | `rng` (composed of hardcoded column + `?`) and fixed `order` strings | Yes — all values via `?` |
| `scanner.py:183-184` | `placeholders` = `"?,?,?"` built from internal uuid list | Yes — only builds placeholder count; values via `?` |

Every user-reachable value (query-string params, POST body fields, DB column values) uses sqlite3 parameter binding. No string-concatenated user input into SQL.

- [ ] **Step 3: Write the finding**

Append to `## Findings`:

```markdown
### 5. SQL injection surface — clean

All f-string SQL in `token_dashboard/` interpolates only internal values: hardcoded column names (`timestamp`), fixed sort directions, and `?`-placeholder lists built from internal UUIDs. Every user-reachable value (since/until query strings, plan name, tip key, session id) is passed via sqlite3 parameter binding.

Spot-checked:
- `db.py:127-129` (`_range_clause`) — column name is literal, values parameterized.
- `db.py:191-362` — every `f"""..."""` query uses `?` for user-supplied values.
- `scanner.py:183-184` (`_evict_prior_snapshots`) — `placeholders` is `?,?,?`, uuids bound via sqlite3.
- `server.py` — no SQL strings; all queries go through `db.py` helpers.

**Verdict:** no action required.
```

- [ ] **Step 4: Commit**

```bash
git add docs/superpowers/plans/2026-04-19-oss-release-design.md
git commit -m "docs(plan): Task 5 finding — SQL injection surface clean"
```

---

## Task 6: Audit path-write safety (finding)

**Files:**
- Read: `token_dashboard/db.py:78-86`, `token_dashboard/scanner.py:218-247`, `token_dashboard/server.py:40-53`, `cli.py:15-25`
- Update: this plan's `## Findings` section (append entry titled "6. Path-write safety")

- [ ] **Step 1: Enumerate all file-writing code paths**

Search for write operations:
Pattern: `\.write\(|\.write_text|\.write_bytes|open\(.*['\"][wa]|sqlite3\.connect|conn\.execute.*INSERT`
Path: `token_dashboard/` and `cli.py`

Expected call sites:
- `db.init_db` (line 82-87) writes SQLite at `db_path`
- Scanner writes rows into the SQLite at `db_path`
- Server writes HTTP response bodies (`self.wfile.write`) — not filesystem
- `_serve_static` (server.py:40-53) reads only; rejects paths that escape `WEB_ROOT`

- [ ] **Step 2: Confirm `db_path` is user-controlled via `--db` / `TOKEN_DASHBOARD_DB`**

Read `cli.py:15-16`: `args.db or os.environ.get("TOKEN_DASHBOARD_DB") or str(default_db_path())`. Default is `~/.claude/token-dashboard.db`.

- [ ] **Step 3: Confirm `_serve_static` rejects path traversal**

Read `server.py:40-46`. It resolves the candidate path and checks `str(p).startswith(str(WEB_ROOT.resolve()))`. That blocks `/web/../../etc/passwd`-style attacks.

- [ ] **Step 4: Confirm scanner only reads from `projects_dir`**

Read `scanner.py:218-247`. It iterates `root.rglob("*.jsonl")` and opens each file read-only. No writes under `projects_dir`.

- [ ] **Step 5: Write the finding**

Append to `## Findings`:

```markdown
### 6. Path-write safety — clean

Writes outside process memory are limited to:
1. The SQLite DB path (default `~/.claude/token-dashboard.db`, overridable via `--db` flag or `TOKEN_DASHBOARD_DB` env var — both user-supplied).
2. No other filesystem writes.

Reads:
- `scanner` reads `*.jsonl` under `projects_dir` (default `~/.claude/projects/`, overridable via `--projects-dir` / `CLAUDE_PROJECTS_DIR`) — read-only.
- `_serve_static` (`server.py:40-46`) resolves the candidate path and verifies `startswith(WEB_ROOT)` before reading — blocks `../` traversal.

**Verdict:** no code path writes outside user-supplied locations; no read path escapes `WEB_ROOT`.
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/2026-04-19-oss-release-design.md
git commit -m "docs(plan): Task 6 finding — path-write safety clean"
```

---

## Task 7: Write `docs/ARCHITECTURE.md`

**Files:**
- Create: `docs/ARCHITECTURE.md`

- [ ] **Step 1: Write the file**

Create `docs/ARCHITECTURE.md` with these sections (400–800 words total):

```markdown
# Architecture

Token Dashboard is a local Python app with four layers: a **scanner** that parses Claude Code's JSONL transcripts into a **SQLite** cache, an **HTTP server** that exposes that cache as JSON and streams live updates, and a **vanilla-JS frontend** that renders it. Everything runs on your machine; nothing leaves it.

## Data flow

```
~/.claude/projects/<slug>/<session>.jsonl
           │
           │  scanner.scan_dir()  (incremental; tracks mtime + byte offset)
           ▼
~/.claude/token-dashboard.db  ← SQLite
           │
           │  token_dashboard/db.py query helpers
           ▼
http.server  (token_dashboard/server.py)
  ├── GET /api/overview        → daily totals, cost
  ├── GET /api/prompts         → most expensive user prompts
  ├── GET /api/sessions        → recent sessions
  ├── GET /api/sessions/<id>   → turn-by-turn drill-down
  ├── GET /api/projects        → per-project comparison
  ├── GET /api/tools           → tool usage breakdown
  ├── GET /api/skills          → skill invocations
  ├── GET /api/tips            → rule-based suggestions
  ├── GET /api/plan            → current pricing plan
  ├── GET /api/stream          → Server-Sent Events (live refresh)
  └── POST /api/plan           → update pricing plan
           │
           ▼
  web/index.html  +  web/app.js  +  web/charts.js  +  web/routes/*
  (Hash-based router; ECharts for visualizations; no build step)
```

## Components

- **`cli.py`** — argparse dispatcher for `scan`, `today`, `stats`, `tips`, `dashboard`. `dashboard` starts a 30-second background scan thread plus the HTTP server.
- **`token_dashboard/scanner.py`** — walks `~/.claude/projects/`, reads new/changed JSONL lines, upserts rows into `messages` and `tool_calls`. Dedupes streaming snapshots by `(session_id, message_id)`: Claude Code writes partial snapshots of an assistant response 2–3 times as the stream grows; only the final snapshot is kept.
- **`token_dashboard/db.py`** — SQLite schema + query helpers. Two tables: `messages` (one row per assistant/user turn) and `tool_calls` (one row per `tool_use` or `tool_result` block). Plus small `plan` and `dismissed_tips` tables for user state.
- **`token_dashboard/skills.py`** — builds an in-memory catalog of installed skills (SKILL.md files under `~/.claude/skills/`, `~/.claude/scheduled-tasks/`, `~/.claude/plugins/`) with a TTL cache. Used by `/api/skills` to populate `tokens_per_call`.
- **`token_dashboard/pricing.py`** — loads `pricing.json` at startup, computes per-turn and aggregate cost estimates, stores the active plan (`api`/`pro`/`max`/`max-20x`) in SQLite.
- **`token_dashboard/tips.py`** — rule-based suggestions (e.g. "you re-read the same file 12 times", "tool result over 50k tokens"). Pure functions over the DB.
- **`token_dashboard/server.py`** — routes, JSON serialization, static file serving, SSE stream. Spawns a background thread that re-scans every 30s and pushes `{"type": "scan", ...}` events to connected SSE clients.
- **`web/`** — vanilla JS, no bundler, no framework. `app.js` is the hash router + fetch client; `charts.js` wraps ECharts; `routes/` has one file per route (overview, prompts, sessions, tools, projects, skills, tips, settings).

## Why SQLite, why stdlib only

The dashboard has to work for a beginner who just cloned a repo. Adding `pip install` or a Node toolchain would move the failure mode from "I don't see my data" to "I can't get the thing to start." Python's `sqlite3` and `http.server` stdlib modules are ugly but zero-friction. The JSONL volume on a heavy user's machine is tens of MB per month, not GB — SQLite handles that comfortably.

## Where to change things

- Add a new API route → `token_dashboard/server.py` (routing) + a query helper in `token_dashboard/db.py`. See `docs/CUSTOMIZING.md` for a full walkthrough.
- Add a new visualization → `web/routes/` (one file per route) + `web/app.js` to register it in the router.
- Change cost math → `token_dashboard/pricing.py` + `pricing.json`.
- Add a new tip rule → `token_dashboard/tips.py`.

See `docs/CUSTOMIZING.md` for practical recipes.
```

- [ ] **Step 2: Verify file exists and has required sections**

Run: `grep -c "^##" docs/ARCHITECTURE.md`
Expected: at least 4 (Data flow, Components, Why SQLite…, Where to change things).

Word count: `wc -w docs/ARCHITECTURE.md` should be 400–800.

- [ ] **Step 3: Commit**

```bash
git add docs/ARCHITECTURE.md
git commit -m "docs: add ARCHITECTURE.md with data-flow diagram"
```

---

## Task 8: Write `docs/CUSTOMIZING.md`

**Files:**
- Create: `docs/CUSTOMIZING.md`

- [ ] **Step 1: Write the file**

```markdown
# Customizing Token Dashboard

Configuration lives in three places: **command-line flags**, **environment variables**, and **`pricing.json`**. Plus one code walkthrough: how to add a new API route.

## Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `HOST` | Bind address for the server | `127.0.0.1` |
| `PORT` | Port for the server | `8080` |
| `CLAUDE_PROJECTS_DIR` | Where to scan for JSONL transcripts | `~/.claude/projects` |
| `TOKEN_DASHBOARD_DB` | Path to the local SQLite cache | `~/.claude/token-dashboard.db` |

Examples:

```bash
# Run on a LAN IP so a second laptop can view your dashboard
HOST=0.0.0.0 PORT=9000 python3 cli.py dashboard

# Scan a transcript archive you copied from another machine
CLAUDE_PROJECTS_DIR=/Volumes/archive/claude-projects python3 cli.py scan
```

## Command-line flags

`cli.py` takes the same overrides:

```bash
python3 cli.py dashboard --projects-dir /path/to/projects --db /path/to/cache.db
python3 cli.py dashboard --no-open    # don't auto-open the browser
python3 cli.py dashboard --no-scan    # serve from cached DB only; skip initial scan
```

Flags win over env vars. Env vars win over defaults.

## `pricing.json`

One JSON file at the repo root defines per-model rates and the four pricing plans. Schema:

```json
{
  "models": {
    "<model-id>": {
      "tier": "opus" | "sonnet" | "haiku",
      "input": <USD per million tokens>,
      "output": <USD per million tokens>,
      "cache_read": <USD per million tokens>,
      "cache_create_5m": <USD per million tokens>,
      "cache_create_1h": <USD per million tokens>
    }
  },
  "tier_fallback": {
    "opus":   { …same shape as a model entry… },
    "sonnet": { … },
    "haiku":  { … }
  },
  "plans": {
    "api":     { "monthly": 0,   "label": "API (pay-per-token)" },
    "pro":     { "monthly": 20,  "label": "Pro" },
    "max":     { "monthly": 100, "label": "Max" },
    "max-20x": { "monthly": 200, "label": "Max 20x" }
  }
}
```

When a transcript mentions a model not in `models`, the dashboard falls back to the `tier_fallback` block by matching the substring `opus`/`sonnet`/`haiku` in the model name. If no tier matches, cost is reported as null (the UI shows `—`).

Edit rates in place — no restart needed for the CLI commands (`today`, `stats`), but the server loads `pricing.json` at startup, so restart the dashboard to pick up new rates.

## How to add a new API route

Say you want `/api/weekday-totals` — tokens grouped by day-of-week.

**1. Add a query helper in `token_dashboard/db.py`:**

```python
def weekday_totals(db_path, since=None, until=None) -> list:
    rng, args = _range_clause(since, until)
    sql = f"""
      SELECT strftime('%w', timestamp) AS weekday,
             COALESCE(SUM(input_tokens + output_tokens), 0) AS tokens
        FROM messages
       WHERE 1=1 {rng}
       GROUP BY weekday
       ORDER BY weekday
    """
    with connect(db_path) as c:
        return [dict(r) for r in c.execute(sql, args)]
```

Keep user-reachable values bound via `?`, never f-string-interpolated.

**2. Wire it up in `token_dashboard/server.py`:**

Add the import at the top:
```python
from .db import (…, weekday_totals)
```

Add the route inside `do_GET`:
```python
if path == "/api/weekday-totals":
    return _send_json(self, weekday_totals(db_path, since, until))
```

**3. (Optional) Add a test:**

```python
# tests/test_queries.py
def test_weekday_totals_empty(self):
    self.assertEqual(weekday_totals(self.db), [])
```

**4. (Optional) Add a frontend route:**

Create `web/routes/weekday.js` and register it in `web/app.js`. See `web/routes/overview.js` for the simplest existing example.

That's it — no build step, no bundler, no restart beyond the dashboard itself.
```

- [ ] **Step 2: Verify sections present**

Run: `grep -c "^##" docs/CUSTOMIZING.md`
Expected: 4 (Environment variables, Command-line flags, `pricing.json`, How to add…).

- [ ] **Step 3: Commit**

```bash
git add docs/CUSTOMIZING.md
git commit -m "docs: add CUSTOMIZING.md with env vars and extension walkthrough"
```

---

## Task 9: Rewrite `CLAUDE.md`

**Files:**
- Modify: `CLAUDE.md` (full replacement)

- [ ] **Step 1: Replace contents**

Overwrite `CLAUDE.md` entirely with:

```markdown
# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Project overview

**Token Dashboard** — a local dashboard for tracking Claude Code token usage, costs, and session history. Reads the JSONL transcripts Claude Code writes to `~/.claude/projects/` and turns them into per-prompt cost analytics, tool/file heatmaps, subagent attribution, cache analytics, project comparisons, and a rule-based tips engine.

Inspired by [phuryn/claude-usage](https://github.com/phuryn/claude-usage) but diverges in UI (vanilla JS + ECharts, dark theme, hash router, SSE refresh) and scope (expensive-prompt drill-down, skills view, tips engine, streaming-snapshot dedup). See `docs/inspiration.md` for the original's feature set and known limitations.

## Status

Working codebase. 66 Python unit tests (`python3 -m unittest discover tests`). Seven UI routes wired up. Runs on macOS, Windows, and Linux.

## Architecture

See `docs/ARCHITECTURE.md` for the full data-flow diagram and component descriptions. Short version:

- `cli.py` → `token_dashboard/scanner.py` → `~/.claude/token-dashboard.db` (SQLite)
- `token_dashboard/server.py` exposes JSON APIs (`/api/*`) + SSE stream (`/api/stream`) + static frontend (`web/`)
- `web/` is vanilla JS, no build step — hash router + ECharts

## Data source

Claude Code writes one JSONL file per session to `~/.claude/projects/<project-slug>/<session-id>.jsonl`. Each line is a message record; usage fields live at `message.usage` and model identifier at `message.model`. The scanner is incremental — it tracks each file's mtime and byte offset in the `files` table and only reads new bytes on subsequent scans.

## Conventions

- **Fully local.** No telemetry, no remote calls for user data. Tests run offline.
- **Stdlib only.** No `pip install`. If a new feature needs a third-party library, argue for it first — we're willing to pay ergonomics cost to keep install friction at zero.
- **SQLite parameter binding always.** Any f-string in a SQL statement must interpolate only internal, caller-controlled values (column names, placeholder lists). User-reachable values go through `?`.
- **Small files with clear responsibilities.** If a file grows past ~400 lines or accretes three distinct concerns, split it.
- **Streaming-snapshot dedup.** When adding scanner logic that joins the `messages` table, remember `(session_id, message_id)` is the dedup key, not `uuid`. See `scanner._evict_prior_snapshots` and the migration note in `db._migrate_add_message_id`.

## Customizing

See `docs/CUSTOMIZING.md` for env vars (`PORT`, `HOST`, `CLAUDE_PROJECTS_DIR`, `TOKEN_DASHBOARD_DB`), `pricing.json` format, and a walkthrough of how to add a new API route.

## Known limitations

See `docs/KNOWN_LIMITATIONS.md`. Current summary: Skills `tokens_per_call` is populated only for skills installed under the three scanned roots (`~/.claude/skills/`, `~/.claude/scheduled-tasks/`, `~/.claude/plugins/`); project-local skills and subagent-dispatched skills show invocation counts but blank token counts.

## Verifying changes

```bash
python3 -m unittest discover tests        # all tests
python3 cli.py dashboard --no-open        # start the server
curl http://127.0.0.1:8080/api/overview   # sanity-check an endpoint
```

See `docs/VERIFICATION.md` for the full end-to-end checklist.
```

- [ ] **Step 2: Sanity-check the new content**

```bash
grep -c "C:\\\\Users" CLAUDE.md   # must be 0 — no Windows hardcoded paths
grep "empty scaffold" CLAUDE.md    # must return nothing
```

Expected: first command prints `0`, second prints nothing.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: rewrite CLAUDE.md to describe codebase as-built"
```

---

## Task 10: Update `.gitignore` for fork-safety

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Add `.claude/` to `.gitignore`**

Using the Edit tool, append a new line to `.gitignore`. The final file should be:

```
__pycache__/
*.pyc
.venv/
.DS_Store
out/
node_modules/
*.db
.superpowers/
.claude/
```

**Why `.claude/` specifically:** a student who forks this repo and opens it in Claude Code will end up with a `.claude/` directory containing their own session transcripts and settings. Committing that would leak their data into every PR.

- [ ] **Step 2: Verify the line is present**

Run: `grep -x "\.claude/" .gitignore`
Expected: prints `.claude/`.

- [ ] **Step 3: Verify `git status` still works and doesn't stage `.claude/` accidentally**

```bash
git status --short
```

Expected: `.claude/` (which already exists locally, per the initial repo snapshot) is no longer listed as untracked.

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore(gitignore): add .claude/ to keep forker transcripts private"
```

---

## Task 11: Confirm tests still pass after Tasks 1–10

**Files:** (none modified — verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m unittest discover tests`
Expected: `OK` with 68 tests (66 original + 2 new HEAD tests from Task 2).

- [ ] **Step 2: If any test fails, STOP and report**

Do not proceed to later tasks. Diagnose the regression and fix it before continuing.

- [ ] **Step 3: If green, no commit — just record the pass**

(Task 13 will capture this in `VERIFICATION.md`. No filesystem change here.)

---

## Task 12: Cross-check `pricing.json` against `/api/overview` cost

**Files:** (read-only — informs Task 13)

- [ ] **Step 1: Start the dashboard in the background**

```bash
python3 cli.py dashboard --no-scan --no-open &
DASH_PID=$!
sleep 2
```

- [ ] **Step 2: Fetch overview**

```bash
curl -s http://127.0.0.1:8080/api/overview > /tmp/overview.json
cat /tmp/overview.json
```

Note the `cost_usd` value.

- [ ] **Step 3: Fetch by-model breakdown**

```bash
curl -s http://127.0.0.1:8080/api/by-model > /tmp/by-model.json
cat /tmp/by-model.json
```

- [ ] **Step 4: Manually sum the per-model costs**

For each model row, compute `(input_tokens * input_rate + output_tokens * output_rate + …) / 1_000_000` using `pricing.json` rates. Total across all models should equal `cost_usd` from `/api/overview` within rounding (6-decimal precision in `cost_for`, rounded to 4 in the overview).

If they disagree by more than ~$0.01, there's a bug — dig in before Task 13.

- [ ] **Step 5: Stop the server**

```bash
kill $DASH_PID
```

- [ ] **Step 6: Record the result for Task 13**

Note whether the sums matched. No file change; Task 13 writes it up.

---

## Task 13: Write `docs/VERIFICATION.md`

**Files:**
- Create: `docs/VERIFICATION.md`

- [ ] **Step 1: Run all the verification items, record pass/fail for each**

Do each item fresh (don't just transcribe earlier memory):

1. `python3 -m unittest discover tests` → expected `OK, 68 tests`
2. `python3 cli.py dashboard --no-open --no-scan` starts → expected `Token Dashboard listening on http://127.0.0.1:8080/`
3. `curl -sI http://127.0.0.1:8080/` → status 200 (NOT 501)
4. `curl -s http://127.0.0.1:8080/` | head -5 → contains `<html`
5. For each of the 7 UI-backing `/api/*` endpoints — `overview`, `prompts`, `sessions`, `projects`, `skills`, `tips`, `plan` — `curl -s http://127.0.0.1:8080/api/<name> | python3 -c "import sys,json; json.load(sys.stdin)"` → exits 0 (valid JSON)
6. `curl -s http://127.0.0.1:8080/api/plan` → contains both `plan` and `pricing` keys
7. Cost reconciliation from Task 12 → sums match `/api/overview.cost_usd`
8. `.gitignore` contains `.claude/`
9. No `*.db` accidentally tracked → `git ls-files | grep -E '\.db$'` returns nothing

- [ ] **Step 2: Write the file**

```markdown
# Verification Checklist

Last run: 2026-04-19 (main branch at HEAD).

| # | Check | Status |
|---|---|---|
| 1 | `python3 -m unittest discover tests` | ✅ 68/68 pass |
| 2 | `python3 cli.py dashboard --no-open --no-scan` starts and prints the listening URL | ✅ |
| 3 | `curl -I http://127.0.0.1:8080/` returns 200, not 501 | ✅ (was 501 before Task 2's `do_HEAD` fix) |
| 4 | `GET /` serves `index.html` | ✅ |
| 5 | All 7 UI-backing `/api/*` endpoints return valid JSON | ✅ `overview`, `prompts`, `sessions`, `projects`, `skills`, `tips`, `plan` |
| 6 | `GET /api/plan` returns both `plan` and `pricing` | ✅ |
| 7 | `/api/overview.cost_usd` equals the sum of per-model costs from `/api/by-model` within 4-decimal rounding | ✅ |
| 8 | `.gitignore` contains `.claude/` | ✅ (Task 10) |
| 9 | No `*.db` tracked in git | ✅ `git ls-files \| grep '\\.db$'` returns nothing |
| 10 | No `__pycache__` tracked | ✅ |
| 11 | `pricing.json` entries for Opus 4.7, Sonnet 4.6, Haiku 4.5 current | ✅ (Task 4 finding) |

## HEAD request handling

The server now delegates `HEAD` to `GET` (see `token_dashboard/server.py` `do_HEAD`). Body is still written to the socket — HTTP/1.1 specifies clients MUST ignore the body on HEAD responses, matching how `SimpleHTTPRequestHandler` handles it. If a future change needs strict compliance (suppressing the body server-side), the right hook is to override `copyfile` or short-circuit `_send_json` / `_serve_static` when `self.command == "HEAD"`.

## What wasn't verified in this pass

- Behavior on an empty `~/.claude/projects/` directory (smoke-tested but not in CI).
- High-volume scan (>1 GB of JSONL) — unchanged from the pre-release behavior.
- Browser compatibility beyond the current dev-machine browser.

These are deferred to the first post-publish pass.
```

If any item actually failed in Step 1, record the failure honestly — do not paper over it.

- [ ] **Step 3: Commit**

```bash
git add docs/VERIFICATION.md
git commit -m "docs: add VERIFICATION.md with end-to-end checklist"
```

---

## Task 14: Write `docs/KNOWN_LIMITATIONS.md`

**Files:**
- Create: `docs/KNOWN_LIMITATIONS.md`

- [ ] **Step 1: Aggregate the known limitations**

Sources:
- Task 1 finding (Skills scanned roots)
- Spec §7 "Open follow-ups" — especially the `<your-handle>` placeholder in README
- General dashboard caveats (no Cowork sessions; cost for Pro/Max users is API-equivalent, not subscription value)

- [ ] **Step 2: Write the file**

```markdown
# Known Limitations

None of these are blockers — the dashboard still gives you useful information. They're the rough edges you'll notice if you look hard.

## Skills token counts are partial

The Skills route shows every skill Claude Code invoked, how many times, across how many sessions, and when. The **tokens-per-call** column is populated only for skills whose `SKILL.md` lives under `~/.claude/skills/`, `~/.claude/scheduled-tasks/`, or `~/.claude/plugins/`. Skills registered elsewhere (project-local `.claude/skills/`, or invocations that go through the `Task` tool with a skill-shaped `subagent_type`) show invocation counts but leave the token column blank.

It's still a useful view — you can see which skills dominate your session time — just don't expect a complete per-skill token cost. PRs to broaden the catalog scan welcome.

## Cost for Pro / Max / Max-20x users is shown as API-equivalent, not subscription value

The Settings route lets you select your pricing plan, but the Overview cost number is always the API-equivalent (what the same usage would have cost on pay-per-token rates). If you're on Pro you pay a flat $20/month regardless of how much of that API-equivalent number you rack up. We don't do "subscription ROI" math yet — Anthropic doesn't publish per-plan rate limits as public JSON, and faking it would be worse than not doing it.

## Cowork sessions are invisible

If you use Claude's Cowork mode (server-side sessions, not local `claude` CLI), those sessions don't write JSONL to `~/.claude/projects/` and the dashboard can't see them.

## Non-standard model names get tier-fallback pricing

If a transcript references a model ID not in `pricing.json` (e.g. a future snapshot that isn't in our table yet), cost is estimated from the tier substring (`opus` / `sonnet` / `haiku`) in the name. The UI marks these as `estimated: true`. If the model name contains none of those substrings, cost is reported as null.

## README repo URL is a placeholder

`README.md` currently shows `git clone https://github.com/<your-handle>/token-dashboard.git`. This is a placeholder until the repo is published — it's intentional, so the spec's out-of-scope list doesn't leak into docs. Once published, swap `<your-handle>` for the real GitHub handle.

## First scan can be slow

The first `python3 cli.py scan` on a heavy user's machine can read tens of MB across hundreds of JSONLs. Subsequent scans are incremental (mtime + byte-offset tracking in the `files` table), so they're fast.

## Running two dashboards against the same DB

Both will fight over the SQLite file and you'll see inconsistent numbers and occasional `database is locked` errors. Only run one at a time. If you want to view the dashboard from a second device, use `HOST=0.0.0.0` on the one running machine and point the second device's browser at it.
```

- [ ] **Step 3: Commit**

```bash
git add docs/KNOWN_LIMITATIONS.md
git commit -m "docs: add KNOWN_LIMITATIONS.md including Skills tokens caveat"
```

---

## Task 15: Rewrite `README.md`

**Files:**
- Modify: `README.md` (full replacement)

- [ ] **Step 1: Replace contents**

Overwrite `README.md` entirely with:

````markdown
# Token Dashboard

A local dashboard that reads the JSONL transcripts Claude Code writes to `~/.claude/projects/` and turns them into per-prompt cost analytics, tool/file heatmaps, subagent attribution, cache analytics, project comparisons, and a rule-based tips engine.

**Everything runs locally.** No data leaves your machine — no telemetry, no API calls for your data, no login.

## What this is useful for

- Seeing which of your prompts are expensive (surprise: they usually involve large tool results).
- Comparing token usage across projects you've worked on.
- Spotting wasteful patterns — the same file read twenty times in a session, a tool call returning 80k tokens.
- Understanding what a "cache hit" actually saves you.
- If you're on Pro or Max, confirming you're getting your money's worth in API-equivalent dollars.

## Prerequisites

- **Python 3.8 or newer** — already installed on macOS and most Linux. On Windows: `winget install Python.Python.3.12` or download from python.org.
- **Claude Code** — installed and with at least one session run. The dashboard reads those sessions. If you just installed Claude Code and haven't used it yet, run at least one prompt first.
- **A web browser.** Any modern one.

No `pip install`. No Node.js. No build step.

## Quickstart

```bash
git clone https://github.com/<your-handle>/token-dashboard.git
cd token-dashboard
python3 cli.py dashboard
```

The command:
1. Scans `~/.claude/projects/` (first run can take 20–60 seconds on a heavy user's machine).
2. Starts a local server at http://127.0.0.1:8080.
3. Opens your default browser to that URL.

Leave it running; it re-scans every 30 seconds and pushes updates live. Stop with `Ctrl+C`.

## Where the data comes from

Claude Code writes one JSONL file per session here:

| OS | Path |
|---|---|
| macOS / Linux | `~/.claude/projects/<project-slug>/<session-id>.jsonl` |
| Windows | `C:\Users\<you>\.claude\projects\<project-slug>\<session-id>.jsonl` |

The dashboard never modifies those files — it only reads them and keeps a local SQLite cache at `~/.claude/token-dashboard.db`.

To point at a different location:

```bash
python3 cli.py dashboard --projects-dir /path/to/projects --db /path/to/cache.db
```

See [`docs/CUSTOMIZING.md`](docs/CUSTOMIZING.md) for all env vars and flags.

## CLI reference

```bash
python3 cli.py scan          # populate / refresh the local DB, then exit
python3 cli.py today         # today's totals (terminal)
python3 cli.py stats         # all-time totals (terminal)
python3 cli.py tips          # active suggestions (terminal)
python3 cli.py dashboard     # scan + serve the UI at http://localhost:8080

# dashboard flags
python3 cli.py dashboard --no-open   # don't auto-open the browser
python3 cli.py dashboard --no-scan   # skip the initial scan (use cached DB only)
```

Change the port: `PORT=9000 python3 cli.py dashboard`.

## What you'll see (7 routes)

- **Overview** — all-time input/output/cache tokens, sessions, turns, estimated cost on your chosen plan, plus a per-tool breakdown chart.
- **Prompts** — your most expensive user prompts. Click in to see the assistant response, tool calls, and result sizes.
- **Sessions** — turn-by-turn view of any session.
- **Projects** — per-project comparison (tokens, sessions, active files).
- **Skills** — which skills you invoke most, how often. See [limitations](docs/KNOWN_LIMITATIONS.md#skills-token-counts-are-partial).
- **Tips** — rule-based suggestions for reducing token usage (repeated file reads, oversized tool results, low cache hit rate).
- **Settings** — switch pricing between API / Pro / Max / Max-20x.

For a guided tour, see [`docs/EXAMPLE_WALKTHROUGH.md`](docs/EXAMPLE_WALKTHROUGH.md).

Unfamiliar term? [`docs/GLOSSARY.md`](docs/GLOSSARY.md).

## Troubleshooting

**"No data" or empty charts.** Run `python3 cli.py scan` once to populate the DB, then reload.

**Port 8080 already in use.** `PORT=9000 python3 cli.py dashboard`.

**Numbers look wrong / stuck.** The DB lives at `~/.claude/token-dashboard.db`. Delete it and re-run `python3 cli.py scan` to rebuild from scratch.

**Running the dashboard twice at the same time.** Don't — both processes will fight over the SQLite DB. Stop all instances before starting a new one.

## Accuracy note

Claude Code writes each assistant response 2–3 times to disk while it streams (the same API message gets snapshotted as output grows). The dashboard dedupes these by `message.id` so the final tally matches what the API actually billed. If you compare against another tool that sums every JSONL row, expect this dashboard's numbers to be lower — and closer to reality.

## Privacy

Nothing leaves your machine. No telemetry. No remote calls for your data. The only outbound request the dashboard ever makes is the browser fetching its own JSON from `127.0.0.1`. If you want to verify: `grep -r "https://" token_dashboard/` — you'll find nothing.

## Tech stack

Python 3 (stdlib only) for the CLI, scanner, and HTTP server. SQLite for the local cache. Vanilla JS + ECharts for the UI, no build step. Dark theme, hash-based router, server-sent events for live refresh.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the full component map.

## Documentation

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — data flow and components
- [`docs/CUSTOMIZING.md`](docs/CUSTOMIZING.md) — env vars, `pricing.json`, adding a new route
- [`docs/GLOSSARY.md`](docs/GLOSSARY.md) — terms used in the UI
- [`docs/EXAMPLE_WALKTHROUGH.md`](docs/EXAMPLE_WALKTHROUGH.md) — your first five minutes
- [`docs/VERIFICATION.md`](docs/VERIFICATION.md) — what we checked before shipping
- [`docs/KNOWN_LIMITATIONS.md`](docs/KNOWN_LIMITATIONS.md) — rough edges

## Contributing

See [`CONTRIBUTING.md`](CONTRIBUTING.md). Short version: fork, `python3 -m unittest discover tests` before opening a PR, keep it stdlib-only.

## License

[MIT](LICENSE).
````

- [ ] **Step 2: Sanity-check the content**

```bash
grep "<your-handle>" README.md    # expect exactly one line
wc -w README.md                    # expect 700-1100
grep -c "^##" README.md            # expect at least 10 sections
```

All links in the README should point to files that will exist after this plan runs. Do not add links to files not in this plan.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: rewrite README for beginners with agent-parseable install"
```

---

## Task 16: Write `docs/GLOSSARY.md`

**Files:**
- Create: `docs/GLOSSARY.md`

- [ ] **Step 1: Write the file**

```markdown
# Glossary

Plain-English definitions for the terms the dashboard uses. If a number on a chart confuses you, start here.

## Token

The unit Claude bills in. Roughly 4 characters of English = 1 token, but code and punctuation skew that ratio. When you see "10k tokens," think "about 40KB of text."

## Input token

Tokens Claude reads — your prompt, conversation history, system prompt, tool results from earlier turns. Also called "prompt tokens" in other tools.

## Output token

Tokens Claude writes — the assistant's reply, including tool calls. Output tokens are more expensive than input tokens (typically 5×).

## Cache read

An input token that came from Claude's prompt cache instead of being re-processed from scratch. Ten times cheaper than a fresh input token. Claude Code uses the cache aggressively — over a long session, most of your input is cache reads.

## Cache create

An input token being *written* into the prompt cache for the first time. Slightly more expensive than a plain input token (you pay a write premium), but subsequent reads are 10× cheaper, so it pays off after two or three reads.

## Session

One conversation with Claude Code, bounded by when you start it and when you exit. Each session gets its own JSONL file in `~/.claude/projects/<project-slug>/<session-id>.jsonl`.

## Turn

One exchange inside a session: you say something (user turn), Claude replies (assistant turn). The dashboard counts user turns on the Overview page — a 100-turn session is a long conversation.

## Project slug

The per-project directory name Claude Code uses under `~/.claude/projects/`. It's the project's absolute path with special characters (`/`, `\`, `:`, spaces) replaced by `-`. The dashboard tries to recover a pretty name from the `cwd` field in the JSONL; if that fails, the slug itself is used.

## Subagent

A fresh Claude instance that the main Claude dispatches to do a focused task — explore a codebase, draft a plan, review code. Runs in its own context, returns a single message. Appears in the dashboard as a `Task` tool call. The `subagent_type` field identifies which kind (e.g. `general-purpose`, `Explore`).

## Tool call

When Claude invokes a tool — `Read`, `Edit`, `Bash`, `Grep`, etc. Each tool call is two parts: the invocation (`tool_use` in the JSONL) and the result (`tool_result`). The Overview page has a per-tool breakdown chart; the Prompts route lets you drill into the results per turn.

## Skill

A bundle of Markdown instructions Claude loads on demand — think of it as a subroutine for common workflows (brainstorming, debugging, writing plans). The Skills route shows how often you've invoked each one.

## Pricing plan

Your billing relationship with Anthropic:
- **API** — pay per token at published rates. The Overview cost figure is literally what you'll be billed.
- **Pro ($20/mo)** / **Max ($100/mo)** / **Max 20x ($200/mo)** — flat subscription with generous per-interval limits. The Overview still shows the *API-equivalent* cost (what this usage would cost on pay-per-token), not what you actually pay. See [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) for why.

## Streaming snapshot

Claude Code writes an assistant response multiple times to disk as the response streams — once after the first sentence, again after the fifth, finally at end-of-response. All three rows have the same `message.id` but different top-level `uuid`s. Summing all three would triple-count. The dashboard dedupes by `message.id`, keeping only the last (final) snapshot.
```

- [ ] **Step 2: Verify sections present**

Run: `grep -c "^##" docs/GLOSSARY.md`
Expected: at least 11 (one per term).

- [ ] **Step 3: Commit**

```bash
git add docs/GLOSSARY.md
git commit -m "docs: add GLOSSARY.md with plain-English term definitions"
```

---

## Task 17: Write `docs/EXAMPLE_WALKTHROUGH.md`

**Files:**
- Create: `docs/EXAMPLE_WALKTHROUGH.md`

- [ ] **Step 1: Write the file**

```markdown
# Your first five minutes

You've run `python3 cli.py dashboard`, the browser opened at http://localhost:8080, and now you're staring at a dark page with some numbers. Here's where to look, in the order that'll build your intuition fastest.

## Minute 1 — Overview: do the numbers look sane?

The Overview page shows all-time totals:

- **Sessions** — how many distinct Claude Code sessions you've run.
- **Turns** — how many times you've prompted Claude. A "session" of back-and-forth chatter can easily rack up 100+ turns.
- **Input / Output / Cache tokens** — the four flavors of token Claude bills in. If you've been using Claude Code for a few weeks, expect "Cache read" to dwarf everything else — that's the prompt cache doing its job.
- **Cost** — API-equivalent dollars. If you're on Pro or Max, this is what you'd pay if you were on API rates, not what you actually pay.

Glance at this and ask: does it roughly match how much I've used Claude Code? If you've been on it for two months and the number says 3 sessions, something is wrong — check that `~/.claude/projects/` actually has your transcripts, and re-run `python3 cli.py scan`.

## Minute 2 — Prompts: what's costing you money?

Click **Prompts** in the sidebar. You see your user prompts sorted by billable tokens descending.

The expensive prompts are almost never long prompts — they're the ones that triggered huge tool results. A `Read` on a 200KB file, a `Grep` with no filters, a `Bash` that dumped the whole `node_modules/` directory listing. Click into the top three; you'll see the assistant response, the tool calls it made, and the size of each result.

This view is usually where people first notice: "oh, I've been asking Claude to read the same config file twenty times in a session." (See Tips — the dashboard will flag that for you.)

## Minute 3 — Tips: rule-based suggestions

Click **Tips**. The dashboard runs a handful of rules against your data:

- Files you re-read too many times in a session (hint: Claude caches your conversation, so a repeated Read costs cache-creation tokens).
- Tool results over some threshold (hint: ask Claude to grep for the specific part you need instead of dumping everything).
- Subagent tool calls with outlier token counts (n ≥ 10, 6× the mean, 50k-token floor).

Tips are not commandments — they're observations. Dismiss anything that doesn't apply. The dismissed tips persist across restarts so you don't have to re-dismiss them every time.

## Minute 4 — Skills: what have you been invoking?

Click **Skills**. If you use Superpowers or other skill plugins, this view shows every skill Claude invoked, how many times, across how many sessions, and when you last used it.

Some rows show a `tokens/call` number; some are blank. Blank rows aren't errors — see [`KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md#skills-token-counts-are-partial) for why. The invocation counts are always accurate.

Look for skills you invoke constantly (they're probably worth keeping sharp) versus skills you invoked once and never again (worth evaluating whether they earned their place).

## Minute 5 — Settings: set your plan

Click **Settings**. Pick the pricing plan you're actually on:

- **API** — pay-per-token. Overview cost = what you pay.
- **Pro ($20/mo)**, **Max ($100/mo)**, **Max 20x ($200/mo)** — flat subscription. Overview cost = API-equivalent.

Your choice persists in the local SQLite cache. Changing it doesn't alter the stored data — only how cost is surfaced.

## What to do next

- Browse **Projects** to see which of your projects have eaten the most tokens.
- Open **Sessions** and click your most recent one to see a turn-by-turn replay.
- Leave the dashboard running while you work — it refreshes every 30 seconds, so you can watch the cost tick up in near-real-time.

If something looks wrong or surprising, [`docs/KNOWN_LIMITATIONS.md`](KNOWN_LIMITATIONS.md) probably has a note. If something looks wrong *and* isn't listed there, it might be a real bug — file an issue.
```

- [ ] **Step 2: Verify it reads as a five-minute tour**

`grep -c "^## Minute " docs/EXAMPLE_WALKTHROUGH.md`
Expected: 5.

- [ ] **Step 3: Commit**

```bash
git add docs/EXAMPLE_WALKTHROUGH.md
git commit -m "docs: add EXAMPLE_WALKTHROUGH.md first-five-minutes tour"
```

---

## Task 18: Delete `docs/customizations.md`

**Files:**
- Delete: `docs/customizations.md`

- [ ] **Step 1: Confirm no other file links to it**

Run (via Grep tool):
Pattern: `customizations\.md`
Path: `.`

Expected: zero hits outside `docs/customizations.md` itself and this spec/plan. (The original `CLAUDE.md` referenced it but Task 9 rewrote `CLAUDE.md`; the original `README.md` did not reference it.)

If anything still links to it, fix the link first.

- [ ] **Step 2: Delete the file**

```bash
git rm docs/customizations.md
```

- [ ] **Step 3: Commit**

```bash
git commit -m "docs: remove customizations.md — superseded by CUSTOMIZING.md"
```

---

## Task 19: Create `LICENSE` (MIT)

**Files:**
- Create: `LICENSE`

- [ ] **Step 1: Write the file**

Standard MIT license text. Exact content:

```
MIT License

Copyright (c) 2026 Nathan Herkelman

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 2: Sanity-check**

```bash
grep -c "Nathan Herkelman" LICENSE    # expect 1
grep -c "2026" LICENSE                # expect 1
wc -l LICENSE                         # expect ~21
```

- [ ] **Step 3: Commit**

```bash
git add LICENSE
git commit -m "chore: add MIT LICENSE (Nathan Herkelman, 2026)"
```

---

## Task 20: Create `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

- [ ] **Step 1: Write the file**

```markdown
# Contributing

Thanks for considering a contribution! This is a small, stdlib-only Python project — easy to run, easy to change.

## Running the tests

```bash
python3 -m unittest discover tests
```

That's it. No `pip install`, no fixtures to download. All tests run in under 5 seconds.

If you're fixing a bug, add a failing test first. If you're adding a feature, add a test that exercises the happy path.

## Running the dashboard locally

```bash
python3 cli.py dashboard --no-open
```

Open http://127.0.0.1:8080 in your browser. The server re-scans every 30 seconds and pushes updates over Server-Sent Events, so you'll see changes without a hard refresh.

## Code style

- **Stdlib only.** No `pip install`. If you think a feature genuinely needs a third-party dependency, open an issue first to discuss — we weigh "is this worth the install friction" heavily.
- **SQL: parameter binding always.** Any f-string in a SQL statement interpolates only internal values (hardcoded column names, placeholder lists built from internal UUIDs). User-reachable values go through `?`.
- **Small focused files.** If a file is creeping past ~400 lines and accreting distinct concerns, split it.
- **Type hints where they aid readability.** Not a hard requirement, but helpful on function signatures.
- **Docstrings explain *why*, not *what*.** The code already shows what.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the component layout and [`docs/CUSTOMIZING.md`](docs/CUSTOMIZING.md) for a walkthrough of adding a new API route.

## Opening a pull request

1. Fork the repo.
2. Create a branch: `git checkout -b feat/<short-description>` or `fix/<short-description>`.
3. Make the change. Add or update tests.
4. Run `python3 -m unittest discover tests` — must be green.
5. Commit with a conventional-commit-style message: `feat: add X`, `fix: handle Y`, `docs: update Z`.
6. Push and open a PR against `main`. Describe the user-visible change and link to any relevant issue.

## Ideas that would genuinely help

- Broadening the Skills catalog scan to cover project-local `.claude/skills/` directories (closes the known limitation).
- A CSV or JSON export of any route.
- A session-filter UI (currently everything is all-time or implicit-"recent").
- A GitHub Actions workflow that runs the tests on push.

## What we're not looking for

- Adding a frontend framework. Vanilla JS is a feature.
- Adding telemetry, analytics, or any outbound HTTP for user data. This dashboard is local-only and will stay that way.

## License

By contributing, you agree your contribution is licensed under the [MIT License](LICENSE).
```

- [ ] **Step 2: Verify sections**

Run: `grep -c "^##" CONTRIBUTING.md`
Expected: at least 6.

- [ ] **Step 3: Commit**

```bash
git add CONTRIBUTING.md
git commit -m "docs: add CONTRIBUTING.md with test/PR guidance"
```

---

## Task 21: Cross-link check and synthesis reconciliation

**Files:** (read-only unless a link is broken — then patch whichever file is wrong)

- [ ] **Step 1: List all new docs**

Expected set:
- `LICENSE`
- `CONTRIBUTING.md`
- `README.md` (rewritten)
- `CLAUDE.md` (rewritten)
- `docs/ARCHITECTURE.md`
- `docs/CUSTOMIZING.md`
- `docs/GLOSSARY.md`
- `docs/EXAMPLE_WALKTHROUGH.md`
- `docs/VERIFICATION.md`
- `docs/KNOWN_LIMITATIONS.md`
- `docs/inspiration.md` (kept)

- [ ] **Step 2: Confirm every new doc is referenced at least once from somewhere else**

Run (via Grep, one by one):
Pattern: `ARCHITECTURE\.md`  → expect hits in `README.md` and `CLAUDE.md`
Pattern: `CUSTOMIZING\.md`   → expect hits in `README.md`, `CLAUDE.md`, and `CONTRIBUTING.md`
Pattern: `GLOSSARY\.md`      → expect hits in `README.md` and `EXAMPLE_WALKTHROUGH.md`
Pattern: `EXAMPLE_WALKTHROUGH\.md` → expect hits in `README.md`
Pattern: `VERIFICATION\.md`  → expect hits in `README.md` and `CLAUDE.md`
Pattern: `KNOWN_LIMITATIONS\.md` → expect hits in `README.md`, `CLAUDE.md`, `EXAMPLE_WALKTHROUGH.md`
Pattern: `CONTRIBUTING\.md`  → expect hits in `README.md`
Pattern: `LICENSE`           → expect hits in `README.md` and `CONTRIBUTING.md`

For any orphan: add a link from `README.md`'s Documentation section.

- [ ] **Step 3: Check every markdown link resolves to a file that exists**

Run (via Bash):

```bash
python3 -c "
import re, os, sys
bad = []
for root, _, files in os.walk('.'):
    if '.git' in root.split(os.sep): continue
    for f in files:
        if not f.endswith('.md'): continue
        path = os.path.join(root, f)
        text = open(path, encoding='utf-8').read()
        for m in re.finditer(r'\]\(([^)]+)\)', text):
            target = m.group(1).split('#')[0]
            if target.startswith(('http://','https://','mailto:')) or not target: continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
            if not os.path.exists(resolved):
                bad.append((path, m.group(1), resolved))
if bad:
    for p, link, r in bad: print(f'{p}: broken link -> {link} (would be {r})')
    sys.exit(1)
print('all markdown links resolve')
"
```

Expected: `all markdown links resolve`.

If any link is broken: fix it, re-run the check, then proceed.

- [ ] **Step 4: Reconcile overlapping claims**

- If `ARCHITECTURE.md`'s component description contradicts the `README.md`'s tech-stack section, side with the code — read the relevant module, make both docs match reality.
- If `VERIFICATION.md`'s endpoint list doesn't match `ARCHITECTURE.md`'s endpoint list, make them consistent.
- If `README.md` lists an env var that `CUSTOMIZING.md` doesn't document (or vice versa), add it to whichever is missing.

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "docs: reconcile cross-links and fix broken references"
```

(If no fixes were needed, skip the commit.)

---

## Task 22: Final end-to-end verification

**Files:** (read-only / execution only)

- [ ] **Step 1: Run the spec's definition-of-done checklist verbatim**

```bash
# 1. Tests
python3 -m unittest discover tests
# Expected: OK, 68 tests

# 2 + 3. Dashboard starts and HEAD returns 200
python3 cli.py dashboard --no-open --no-scan &
DASH_PID=$!
sleep 2
curl -sI http://127.0.0.1:8080/ | head -1
# Expected: HTTP/1.x 200 OK

# The 7 UI-backing /api/* endpoints
for ep in overview prompts sessions projects skills tips plan; do
  code=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8080/api/$ep)
  echo "$ep: $code"
done
# Expected: every line ends in 200
kill $DASH_PID

# 6. customizations.md gone
test ! -f docs/customizations.md && echo "customizations.md: deleted OK"

# 7. .gitignore has .claude/
grep -q '^\.claude/$' .gitignore && echo ".gitignore: .claude/ present"

# 8. LICENSE
grep -q "MIT License" LICENSE && grep -q "2026" LICENSE && grep -q "Nathan Herkelman" LICENSE && echo "LICENSE: OK"

# 9. No broken markdown links — rerun Task 21 step 3
python3 -c "
import re, os, sys
bad = []
for root, _, files in os.walk('.'):
    if '.git' in root.split(os.sep): continue
    for f in files:
        if not f.endswith('.md'): continue
        path = os.path.join(root, f)
        text = open(path, encoding='utf-8').read()
        for m in re.finditer(r'\]\(([^)]+)\)', text):
            target = m.group(1).split('#')[0]
            if target.startswith(('http://','https://','mailto:')) or not target: continue
            resolved = os.path.normpath(os.path.join(os.path.dirname(path), target))
            if not os.path.exists(resolved): bad.append((path, m.group(1), resolved))
if bad:
    for p, link, r in bad: print(f'{p}: broken link -> {link} (would be {r})')
    sys.exit(1)
print('all markdown links resolve')
"

# 10. Clean git status
git status --short
# Expected: empty output (all committed)
```

- [ ] **Step 2: Manually spot-check the UI**

```bash
python3 cli.py dashboard --no-scan
```

Click through every route. None should show a JS console error or a red/blank panel.

- [ ] **Step 3: Record definition-of-done completion**

If every check passes, the pass is done. No further commit needed — `VERIFICATION.md` is already up to date.

If any check fails: stop, fix the specific issue, and re-run this task from Step 1.

---

## Findings

(This section is populated as Tasks 1, 3, 4, 5, 6 execute. Each of those tasks appends one entry here. Do not delete this section — it's the in-plan findings bundle the spec references.)

### 1. Skills scanned roots — confirmed

`token_dashboard/skills.py:19-23` scans exactly three roots:
- `~/.claude/skills/`
- `~/.claude/scheduled-tasks/`
- `~/.claude/plugins/` (and its nested `marketplaces/…/plugins/<plugin>/skills/` tree)

Skills whose `SKILL.md` lives outside those roots (project-local `.claude/skills/`, or subagent dispatches via `Task` tool with a skill-shaped `subagent_type`) are invoked correctly by Claude Code but have no entry in the catalog. The `/api/skills` route (`server.py:105-111`) still returns invocation counts for those skills — only `tokens_per_call` is null.

**Impact:** documented as a known limitation; no code change this pass.

### 3. Scanner completeness — confirmed

Every `message.usage` field Claude Code emits is captured: input, output, cache-read, cache-create-5m, cache-create-1h. Top-level fields captured: `uuid`, `parentUuid`, `sessionId`, `cwd`, `gitBranch`, `version` (→ `cc_version`), `entrypoint`, `type`, `isSidechain`, `agentId`, `timestamp`, `promptId`. Nested `message.*` captured: `model`, `stop_reason`, `id` (→ `message_id` for streaming-snapshot dedup).

Also captured from `user`-type records: `prompt_text` (the concatenated text blocks from `message.content`, stored in the `messages.prompt_text` column — this is the raw human turn content and is the highest-sensitivity field in the schema) and `prompt_chars` (character count). For assistant turns with tool calls, a denormalized `tool_calls_json` column stores `[{name, target}]` for non-`_tool_result` blocks on the message row.

Tool calls: `tool_use` blocks are captured with `name` + the whitelisted primary-input field (see `scanner._TARGET_FIELDS`). Other input fields (e.g. Edit's `old_string`/`new_string`) are intentionally dropped — the dashboard only needs the identifier/target, not the body. `tool_result` blocks are captured as synthetic `_tool_result` rows with `result_tokens = chars // 4` (approximate).

**Intentionally not captured:** per-block tool-call timings, tool-call argument bodies beyond the primary target, any field outside `message.usage` and `message.content`. This matches the spec intent ("aggregate analytics, not a replay of every byte").

### 4. Pricing freshness — confirmed (no changes)

`pricing.json` contains current entries for `claude-opus-4-7`, `claude-sonnet-4-6`, `claude-haiku-4-5` matching Anthropic's public per-million-token rates as of 2026-04-19. `claude-opus-4-6` is kept as a fallback for older transcripts. The `tier_fallback` object covers unknown model names by family (opus / sonnet / haiku).

### 5. SQL injection surface — clean

All f-string SQL in `token_dashboard/` interpolates only internal values: hardcoded column names (`timestamp`), fixed sort directions, and `?`-placeholder lists built from internal UUIDs. Every user-reachable value (since/until query strings, plan name, tip key, session id) is passed via sqlite3 parameter binding.

Spot-checked:
- `db.py:127-129` (`_range_clause`) — column name is literal, values parameterized.
- `db.py:191-362` — every `f"""..."""` query uses `?` for user-supplied values.
- `scanner.py:183-184` (`_evict_prior_snapshots`) — `placeholders` is `?,?,?`, uuids bound via sqlite3.
- `server.py` — no SQL strings; all queries go through `db.py` helpers.

**Verdict:** no action required.
### 6. Path-write safety — clean

Writes outside process memory are limited to:
1. The SQLite DB path (default `~/.claude/token-dashboard.db`, overridable via `--db` flag or `TOKEN_DASHBOARD_DB` env var — both user-supplied).
2. No other filesystem writes.

Reads:
- `scanner` reads `*.jsonl` under `projects_dir` (default `~/.claude/projects/`, overridable via `--projects-dir` / `CLAUDE_PROJECTS_DIR`) — read-only.
- `_serve_static` (`server.py:40-46`) resolves the candidate path and verifies `startswith(WEB_ROOT)` before reading — blocks `../` traversal.

**Verdict:** no code path writes outside user-supplied locations; no read path escapes `WEB_ROOT`.
