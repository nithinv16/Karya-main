"""Iteration 32 tests — refactor smoke + N+1 fix verification.

- Server imports cleanly (route modules load without errors).
- /api/subcontractors uses ONE db.sub_transactions.find call regardless of N subs (N+1 fix).
  Verified two ways:
  (a) source-level assertion — server.py uses {"$in": sub_ids} pattern in list_subs and _assistant_answer.
  (b) HTTP-level correctness — endpoint returns correct summaries for N subs.
- Reports/expenses/cost_trends/telegram-prefs/contact/attendance endpoints still respond OK (smoke).
"""
import os
import re
import sys
import asyncio
import pytest
import requests

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://telegram-helper-bot.preview.emergentagent.com').rstrip('/')
TOKEN = "test_session_karya1"
HDR = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
TG_SECRET = "karya-tg-hook-7f3a9c2e"

sys.path.insert(0, "/app/backend")

_LOOP = asyncio.new_event_loop()
def _run(coro):
    return _LOOP.run_until_complete(coro)


# ---------------------------------------------------------------- smoke: import
class TestImports:
    def test_server_imports_cleanly(self):
        import server
        assert hasattr(server, "app")
        # route modules must be importable
        from routes import attendance, contact, cost_trends, expenses, reports, telegram_prefs
        for m in (attendance, contact, cost_trends, expenses, reports, telegram_prefs):
            assert m is not None

    def test_attendance_shims_present(self):
        import server
        assert hasattr(server, "mark_attendance"), "server.mark_attendance shim missing"
        assert hasattr(server, "headcount_attendance"), "server.headcount_attendance shim missing"
        from routes import attendance as rt_att
        assert hasattr(rt_att, "mark_attendance_core")
        assert hasattr(rt_att, "headcount_attendance_core")

    def test_ping_scheduler_function_exists(self):
        """The scheduler task is created at ASGI startup; can't validate
        via a fresh import. Instead assert the startup wiring exists."""
        src = open("/app/backend/server.py").read()
        assert "_PING_TASK" in src
        assert "Telegram ping scheduler started" in src or "ping scheduler" in src.lower()


# ---------------------------------------------------------------- smoke: endpoints respond
class TestSmokeEndpoints:
    def test_company_info(self):
        r = requests.get(f"{BASE_URL}/api/company-info", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["legal_name"] == "SIXN8 Technologies Private Ltd"
        assert "NithinV16" not in r.text

    def test_attendance_roster(self):
        r = requests.get(f"{BASE_URL}/api/attendance/roster", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "roster" in d and "headcounts" in d

    def test_cost_trends_shape(self):
        r = requests.get(f"{BASE_URL}/api/cost-trends", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        for k in ("period", "buckets", "projects", "overall", "currency", "has_data"):
            assert k in d, f"missing key {k}"

    def test_cost_trends_periods(self):
        for period in ("week", "month", "quarter", "year"):
            r = requests.get(f"{BASE_URL}/api/cost-trends?period={period}", headers=HDR, timeout=15)
            assert r.status_code == 200, f"{period}: {r.text}"
            assert r.json()["period"] == period

    def test_expenses_search(self):
        r = requests.get(f"{BASE_URL}/api/expenses?q=STEEL", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "items" in d and isinstance(d["items"], list)

    def test_expenses_limit_clamped_low(self):
        r0 = requests.get(f"{BASE_URL}/api/expenses?limit=0", headers=HDR, timeout=15)
        assert r0.status_code == 200
        d = r0.json()
        assert d["limit"] == 1
        assert len(d["items"]) <= 1

    def test_expenses_limit_clamped_high(self):
        r_big = requests.get(f"{BASE_URL}/api/expenses?limit=99999", headers=HDR, timeout=15)
        assert r_big.status_code == 200
        d = r_big.json()
        assert d["limit"] == 2000

    def test_expenses_regex_escape(self):
        # Should not raise 500 from bad regex chars
        r = requests.get(f"{BASE_URL}/api/expenses?q=.*+", headers=HDR, timeout=15)
        assert r.status_code == 200

    def test_telegram_prefs_get(self):
        r = requests.get(f"{BASE_URL}/api/telegram/notifications", headers=HDR, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "notifications" in d
        assert "telegram_linked" in d

    def test_telegram_prefs_invalid_tz(self):
        r = requests.put(f"{BASE_URL}/api/telegram/notifications", headers=HDR,
                         json={"timezone": "Not/A/Zone"}, timeout=15)
        assert r.status_code == 400

    def test_telegram_prefs_invalid_time(self):
        # Correct schema — nested under a notification block
        r = requests.put(f"{BASE_URL}/api/telegram/notifications", headers=HDR,
                         json={"morning_briefing": {"time": "25:99"}}, timeout=15)
        assert r.status_code == 400

    def test_telegram_prefs_days_cleaned(self):
        r = requests.put(f"{BASE_URL}/api/telegram/notifications", headers=HDR,
                         json={"morning_briefing": {"days": [0, 8, "a", 3, 1]}}, timeout=15)
        assert r.status_code == 200
        # days should be cleaned to [1, 3]
        mb = (r.json().get("notifications") or {}).get("morning_briefing") or {}
        days = mb.get("days") or []
        assert set(days).issubset({1, 2, 3, 4, 5, 6, 7})
        assert 0 not in days and 8 not in days

    def test_subcontractors_list_correct(self):
        r = requests.get(f"{BASE_URL}/api/subcontractors", headers=HDR, timeout=15)
        assert r.status_code == 200
        subs = r.json()
        assert isinstance(subs, list)
        for s in subs:
            assert "summary" in s
            for k in ("gross", "paid", "pending", "retention_held", "material_recovered", "net_payable"):
                assert k in s["summary"], f"summary missing {k}"
            assert s["summary"]["gross"] >= 0


# ---------------------------------------------------------------- N+1 fix verification
class TestN1FixSourceLevel:
    """Verify the bulk $in query pattern is present in the two hot paths."""

    def test_list_subs_uses_bulk_in_query(self):
        src = open("/app/backend/server.py").read()
        # Find the list_subs function body (from def to next def or blank@col0)
        m = re.search(r"async def list_subs\(.*?\n(.*?)\n@api\.", src, re.DOTALL)
        assert m, "could not locate list_subs body"
        body = m.group(1)
        assert '"sub_id": {"$in":' in body, "list_subs should use $in bulk query"
        # Anti-pattern: `for s in subs:` LOOP (with colon) followed by find(). List
        # comprehensions `[... for s in subs]` are fine (they build $in list).
        loop_bug = re.search(r"for\s+\w+\s+in\s+subs\s*:.*?db\.sub_transactions\.find\(", body, re.DOTALL)
        assert not loop_bug, "list_subs still calls sub_transactions.find inside a subs loop (N+1)"

    def test_assistant_answer_uses_bulk_in_query(self):
        src = open("/app/backend/server.py").read()
        m = re.search(r"async def _assistant_answer\(.*?\n(.*?)\nasync def ", src, re.DOTALL)
        assert m, "could not locate _assistant_answer body"
        body = m.group(1)
        assert '"sub_id": {"$in":' in body, "_assistant_answer should use $in bulk query"
        loop_bug = re.search(r"for\s+\w+\s+in\s+subs\s*:.*?db\.sub_transactions\.find\(", body, re.DOTALL)
        assert not loop_bug, "_assistant_answer still N+1"


class TestN1FixHttpCorrectness:
    """After the refactor, endpoint still returns correct summaries for N subs."""

    def test_list_subs_multiple_subs_correct(self):
        # Create 3 test subs + 1 transaction each, verify summaries reflect them.
        created_subs = []
        try:
            for i in range(3):
                r = requests.post(f"{BASE_URL}/api/subcontractors", headers=HDR, json={
                    "name": f"TEST_N1_{i}", "firm": "TF", "trade": "misc",
                    "contract_value": 1000 * (i + 1), "retention_percent": 5,
                }, timeout=15)
                assert r.status_code == 200, r.text
                created_subs.append(r.json()["id"])
                # add a payment txn
                rt = requests.post(f"{BASE_URL}/api/subcontractors/{created_subs[-1]}/transactions",
                                   headers=HDR, json={"type": "payment", "amount": 100 * (i + 1)}, timeout=15)
                assert rt.status_code == 200

            # Fetch the list — should include all 3 with paid=100/200/300
            r = requests.get(f"{BASE_URL}/api/subcontractors", headers=HDR, timeout=15)
            assert r.status_code == 200
            all_subs = {s["id"]: s for s in r.json()}
            for i, sid in enumerate(created_subs):
                assert sid in all_subs
                assert all_subs[sid]["summary"]["paid"] == 100 * (i + 1), \
                    f"summary paid mismatch for sub {i}: {all_subs[sid]['summary']}"
        finally:
            for sid in created_subs:
                requests.delete(f"{BASE_URL}/api/subcontractors/{sid}", headers=HDR, timeout=10)


# ---------------------------------------------------------------- telegram webhook (regression)
class TestTelegramWebhook:
    def test_webhook_200_with_secret(self):
        payload = {
            "message": {
                "chat": {"id": 424242},
                "from": {"id": 424242, "username": "someone"},
                "text": "/help"
            }
        }
        r = requests.post(f"{BASE_URL}/api/telegram/webhook", json=payload,
                          headers={"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}, timeout=15)
        assert r.status_code == 200, r.text

    def test_webhook_nithinv16_capture(self):
        # Also validates chat_id auto-capture path still lives in server.py
        from pymongo import MongoClient
        db = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))[
            os.environ.get("DB_NAME", "karya_db_v2")]
        db.system_config.delete_many({"key": "contact_chat_id"})
        payload = {
            "message": {
                "chat": {"id": 555777998},
                "from": {"id": 555777998, "username": "NIThinV16"},
                "text": "hi bot"
            }
        }
        r = requests.post(f"{BASE_URL}/api/telegram/webhook", json=payload,
                          headers={"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}, timeout=15)
        assert r.status_code == 200
        doc = db.system_config.find_one({"key": "contact_chat_id"})
        assert doc is not None
        assert doc["value"] == "555777998"
        db.system_config.delete_many({"key": "contact_chat_id"})


# ---------------------------------------------------------------- reports smoke
class TestReportsSmoke:
    def test_reports_routes_registered(self):
        import server
        paths = [getattr(r, "path", "") for r in server.app.routes]
        assert any(p.startswith("/api/reports") for p in paths), "reports routes missing"


# ---------------------------------------------------------------- attendance /command helper (regression from iter30)
class TestTelegramAttendanceHelper:
    def test_handle_tg_attendance_headcount(self, monkeypatch):
        """server._handle_tg_attendance_command('/attendance 5 Site A') still writes a headcount row via the delegated core."""
        import server
        sent = []
        async def fake_send(chat_id, text, reply_markup=None):
            sent.append({"chat_id": chat_id, "text": text})
        async def fake_api(method, payload):
            sent.append({"method": method, "payload": payload})
            return {"ok": True}
        monkeypatch.setattr(server, "tg_send", fake_send)
        monkeypatch.setattr(server, "tg_api", fake_api)

        SITE_A = "c1376306-57b0-4871-81c9-a858314d6016"

        async def run():
            user = await server.db.users.find_one({"user_id": "test-user-karya1"}, {"_id": 0})
            assert user is not None
            await server._handle_tg_attendance_command(999000111, user, "/attendance 5 Site A")
            rows = await server.db.attendance.find({
                "owner_id": user["user_id"], "worker_id": None,
                "count": 5, "project_id": SITE_A,
            }).to_list(10)
            try:
                assert len(rows) >= 1, "headcount row not written via shim delegation"
            finally:
                for r in rows:
                    await server.db.attendance.delete_one({"id": r["id"]})
        _run(run())
        assert any("Site A" in (m.get("text") or "") for m in sent), sent
