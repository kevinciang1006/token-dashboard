import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from token_dashboard.db import init_db, connect

PRICING = {
    "models": {
        "claude-opus-4-7": {
            "input": 15.0, "output": 75.0, "cache_read": 1.5,
            "cache_create_5m": 18.75, "cache_create_1h": 75.0,
        }
    },
    "tier_fallback": {},
    "plans": {"api": {"label": "API", "monthly": 0}},
}


def _insert(conn, uuid, session_id, ts, msg_type="assistant",
            model="claude-opus-4-7", input_tokens=10, output_tokens=5):
    conn.execute(
        """INSERT INTO messages
               (uuid, session_id, project_slug, type, timestamp, model,
                input_tokens, output_tokens, cache_read_tokens,
                cache_create_5m_tokens, cache_create_1h_tokens)
           VALUES (?, ?, 'proj', ?, ?, ?, ?, ?, 0, 0, 0)""",
        (uuid, session_id, msg_type, ts, model, input_tokens, output_tokens),
    )


class LoadAccountsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def test_returns_empty_when_file_absent(self):
        from token_dashboard.accounts import load_accounts
        path = os.path.join(self.tmp, "nonexistent.json")
        self.assertEqual(load_accounts(path), [])

    def test_loads_valid_config(self):
        from token_dashboard.accounts import load_accounts
        path = os.path.join(self.tmp, "accounts.json")
        data = [{"name": "A", "projects_dir": "/pa", "db": "/da"}]
        with open(path, "w") as f:
            json.dump(data, f)
        result = load_accounts(path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "A")
        self.assertEqual(result[0]["projects_dir"], "/pa")
        self.assertEqual(result[0]["db"], "/da")

    def test_skips_incomplete_entries(self):
        from token_dashboard.accounts import load_accounts
        path = os.path.join(self.tmp, "accounts.json")
        data = [
            {"name": "A", "projects_dir": "/pa", "db": "/da"},
            {"name": "B"},
        ]
        with open(path, "w") as f:
            json.dump(data, f)
        result = load_accounts(path)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "A")

    def test_returns_empty_for_invalid_json(self):
        from token_dashboard.accounts import load_accounts
        path = os.path.join(self.tmp, "accounts.json")
        with open(path, "w") as f:
            f.write("not json {{{")
        self.assertEqual(load_accounts(path), [])

    def test_returns_empty_for_non_list_json(self):
        from token_dashboard.accounts import load_accounts
        path = os.path.join(self.tmp, "accounts.json")
        with open(path, "w") as f:
            json.dump({"name": "oops"}, f)
        self.assertEqual(load_accounts(path), [])


class WeekStartTests(unittest.TestCase):
    def test_returns_a_monday(self):
        from token_dashboard.accounts import _week_start_iso
        iso = _week_start_iso()
        dt = datetime.fromisoformat(iso)
        self.assertEqual(dt.weekday(), 0)

    def test_returns_midnight(self):
        from token_dashboard.accounts import _week_start_iso
        iso = _week_start_iso()
        dt = datetime.fromisoformat(iso)
        self.assertEqual(dt.hour, 0)
        self.assertEqual(dt.minute, 0)
        self.assertEqual(dt.second, 0)


class AccountSummariesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "test.db")
        init_db(self.db)

    def _accounts(self):
        return [{"name": "Test", "projects_dir": "/p", "db": self.db}]

    def test_current_session_none_for_empty_db(self):
        from token_dashboard.accounts import account_summaries
        result = account_summaries(self._accounts(), PRICING)
        self.assertIsNone(result[0]["current_session"])

    def test_current_session_none_when_last_session_over_24h_old(self):
        from token_dashboard.accounts import account_summaries
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        with connect(self.db) as conn:
            _insert(conn, "u1", "s1", old_ts, "user", input_tokens=0, output_tokens=0)
            _insert(conn, "a1", "s1", old_ts, "assistant", input_tokens=10, output_tokens=5)
            conn.commit()
        result = account_summaries(self._accounts(), PRICING)
        self.assertIsNone(result[0]["current_session"])

    def test_current_session_present_when_recent(self):
        from token_dashboard.accounts import account_summaries
        recent_ts = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        with connect(self.db) as conn:
            _insert(conn, "u1", "s1", recent_ts, "user", input_tokens=0, output_tokens=0)
            _insert(conn, "a1", "s1", recent_ts, "assistant", input_tokens=10, output_tokens=5)
            conn.commit()
        result = account_summaries(self._accounts(), PRICING)
        sess = result[0]["current_session"]
        self.assertIsNotNone(sess)
        self.assertEqual(sess["session_id"], "s1")
        self.assertEqual(sess["input_tokens"], 10)
        self.assertEqual(sess["output_tokens"], 5)
        self.assertIsInstance(sess["cost_usd"], float)

    def test_this_week_excludes_old_messages(self):
        from token_dashboard.accounts import account_summaries
        recent_ts = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        old_ts = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
        with connect(self.db) as conn:
            _insert(conn, "a1", "s1", recent_ts, "assistant", input_tokens=100, output_tokens=50)
            _insert(conn, "a2", "s2", old_ts, "assistant", input_tokens=999, output_tokens=999)
            conn.commit()
        result = account_summaries(self._accounts(), PRICING)
        week = result[0]["this_week"]
        self.assertEqual(week["input_tokens"], 100)
        self.assertEqual(week["output_tokens"], 50)
        self.assertIn("week_start", week)
        self.assertIsInstance(week["cost_usd"], float)

    def test_this_week_zero_for_empty_db(self):
        from token_dashboard.accounts import account_summaries
        result = account_summaries(self._accounts(), PRICING)
        week = result[0]["this_week"]
        self.assertEqual(week["input_tokens"], 0)
        self.assertEqual(week["output_tokens"], 0)


if __name__ == "__main__":
    unittest.main()
