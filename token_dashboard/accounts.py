"""Multi-account config loader and per-account summary queries."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import List, Optional, Union

from .db import connect, init_db
from .pricing import cost_for

ACCOUNTS_JSON = Path(__file__).resolve().parent.parent / "accounts.json"


def load_accounts(config_path: Union[str, Path, None] = None) -> List[dict]:
    """Load accounts.json. Returns empty list if absent or malformed."""
    path = Path(config_path) if config_path else ACCOUNTS_JSON
    if not path.is_file():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    if not isinstance(data, list):
        return []
    result = []
    for entry in data:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name", "")
        projects_dir = entry.get("projects_dir", "")
        db = entry.get("db", "")
        if name and projects_dir and db:
            result.append({"name": name, "projects_dir": projects_dir, "db": db})
    return result


def _week_start_iso() -> str:
    """ISO string for the most recent Monday 00:00 UTC."""
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()


def _current_session(conn, pricing: dict) -> Optional[dict]:
    """Return the most recently active session's summary, or None if >24h old."""
    row = conn.execute(
        "SELECT session_id, MAX(timestamp) AS last_ts FROM messages"
    ).fetchone()
    if not row or not row["session_id"]:
        return None
    last_ts = row["last_ts"]
    if not last_ts:
        return None
    try:
        ts = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
    except ValueError:
        return None
    if (datetime.now(timezone.utc) - ts).total_seconds() > 86400:
        return None
    session_id = row["session_id"]
    totals = dict(conn.execute(
        """SELECT MIN(timestamp) AS started_at,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                  COALESCE(SUM(cache_create_5m_tokens), 0) AS cache_create_5m_tokens,
                  COALESCE(SUM(cache_create_1h_tokens), 0) AS cache_create_1h_tokens
             FROM messages WHERE session_id = ?""",
        (session_id,),
    ).fetchone())
    model_rows = [dict(r) for r in conn.execute(
        """SELECT COALESCE(model, 'unknown') AS model,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                  COALESCE(SUM(cache_create_5m_tokens), 0) AS cache_create_5m_tokens,
                  COALESCE(SUM(cache_create_1h_tokens), 0) AS cache_create_1h_tokens
             FROM messages WHERE session_id = ? AND type = 'assistant'
             GROUP BY model""",
        (session_id,),
    )]
    cost_usd = 0.0
    for m in model_rows:
        c = cost_for(m["model"], m, pricing)
        if c["usd"] is not None:
            cost_usd += c["usd"]
    return {
        "session_id":             session_id,
        "started_at":             totals["started_at"],
        "input_tokens":           totals["input_tokens"],
        "output_tokens":          totals["output_tokens"],
        "cache_read_tokens":      totals["cache_read_tokens"],
        "cache_create_5m_tokens": totals["cache_create_5m_tokens"],
        "cache_create_1h_tokens": totals["cache_create_1h_tokens"],
        "cost_usd":               round(cost_usd, 4),
    }


def _this_week(conn, pricing: dict) -> dict:
    """Return token totals and cost since the most recent Monday 00:00 UTC."""
    week_start = _week_start_iso()
    totals = dict(conn.execute(
        """SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                  COALESCE(SUM(cache_create_5m_tokens), 0) AS cache_create_5m_tokens,
                  COALESCE(SUM(cache_create_1h_tokens), 0) AS cache_create_1h_tokens
             FROM messages WHERE timestamp >= ?""",
        (week_start,),
    ).fetchone())
    model_rows = [dict(r) for r in conn.execute(
        """SELECT COALESCE(model, 'unknown') AS model,
                  COALESCE(SUM(input_tokens), 0) AS input_tokens,
                  COALESCE(SUM(output_tokens), 0) AS output_tokens,
                  COALESCE(SUM(cache_read_tokens), 0) AS cache_read_tokens,
                  COALESCE(SUM(cache_create_5m_tokens), 0) AS cache_create_5m_tokens,
                  COALESCE(SUM(cache_create_1h_tokens), 0) AS cache_create_1h_tokens
             FROM messages WHERE type = 'assistant' AND timestamp >= ?
             GROUP BY model""",
        (week_start,),
    )]
    cost_usd = 0.0
    for m in model_rows:
        c = cost_for(m["model"], m, pricing)
        if c["usd"] is not None:
            cost_usd += c["usd"]
    return {
        "week_start":             week_start,
        "input_tokens":           totals["input_tokens"],
        "output_tokens":          totals["output_tokens"],
        "cache_read_tokens":      totals["cache_read_tokens"],
        "cache_create_5m_tokens": totals["cache_create_5m_tokens"],
        "cache_create_1h_tokens": totals["cache_create_1h_tokens"],
        "cost_usd":               round(cost_usd, 4),
    }


def account_summaries(accounts: List[dict], pricing: dict) -> List[dict]:
    """Fan out to each account's DB and return per-account summary data."""
    results = []
    for acc in accounts:
        db_path = acc["db"]
        try:
            init_db(db_path)
            with connect(db_path) as conn:
                results.append({
                    "name":            acc["name"],
                    "current_session": _current_session(conn, pricing),
                    "this_week":       _this_week(conn, pricing),
                })
        except Exception as e:
            results.append({
                "name":            acc["name"],
                "error":           str(e),
                "current_session": None,
                "this_week":       None,
            })
    return results
