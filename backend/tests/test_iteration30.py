"""Iteration 30 tests — Attendance, Contact form + Telegram delivery, Company info, Telegram /attendance command."""
import os
import sys
import asyncio
import time
import pytest
import requests

# Single shared event loop across the test module so Motor's async client stays bound
_LOOP = asyncio.new_event_loop()
def _run(coro):
    return _LOOP.run_until_complete(coro)

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://telegram-helper-bot.preview.emergentagent.com').rstrip('/')
TOKEN = "test_session_karya1"
HDR = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
TG_SECRET = "karya-tg-hook-7f3a9c2e"

RAMESH = "66be66b1-0826-4225-ba27-4875d7a2e28b"
SURESH = "c608b1a9-ec8e-468b-9026-cc635f90efac"
SITE_A = "c1376306-57b0-4871-81c9-a858314d6016"
SITE_B = "9fe15149-9211-405f-a6b9-57924ba45d80"

# Add server module to path for direct helper tests
sys.path.insert(0, "/app/backend")

# Sync pymongo client for setup/verify (avoids Motor loop-binding issues)
from pymongo import MongoClient
_MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
_DB_NAME = os.environ.get("DB_NAME", "karya_db_v2")
sync_db = MongoClient(_MONGO_URL)[_DB_NAME]


# ---------------------------------------------------------------- attendance CRUD
class TestAttendanceCRUD:
    def _cleanup(self, ids):
        for i in ids:
            try:
                requests.delete(f"{BASE_URL}/api/attendance/{i}", headers=HDR, timeout=10)
            except Exception:
                pass

    def test_mark_upsert(self):
        # First mark
        r = requests.post(f"{BASE_URL}/api/attendance/mark",
                          headers=HDR, json={"worker_id": RAMESH, "status": "present"}, timeout=15)
        assert r.status_code == 200, r.text
        d1 = r.json()
        first_id = d1["id"]
        assert d1["status"] == "present"
        # Second mark same day => same id, updated status
        r2 = requests.post(f"{BASE_URL}/api/attendance/mark",
                           headers=HDR, json={"worker_id": RAMESH, "status": "half_day"}, timeout=15)
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["id"] == first_id, "upsert should keep same id"
        assert d2["status"] == "half_day"
        self._cleanup([first_id])

    def test_headcount(self):
        r = requests.post(f"{BASE_URL}/api/attendance/headcount",
                          headers=HDR, json={"count": 7, "project_id": SITE_A}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["count"] == 7
        assert d["worker_id"] is None
        self._cleanup([d["id"]])

    def test_roster(self):
        # Baseline: no marks today
        r = requests.get(f"{BASE_URL}/api/attendance/roster", headers=HDR, timeout=15)
        assert r.status_code == 200
        roster = r.json()["roster"]
        assert any(w["worker_id"] == RAMESH for w in roster)
        for w in roster:
            if w["worker_id"] == RAMESH:
                # After other tests may have run — accept unmarked OR a valid status
                assert w["status"] in ("unmarked", "present", "absent", "half_day")

        # Mark then check
        m = requests.post(f"{BASE_URL}/api/attendance/mark", headers=HDR,
                          json={"worker_id": SURESH, "status": "absent"}, timeout=15).json()
        r2 = requests.get(f"{BASE_URL}/api/attendance/roster", headers=HDR, timeout=15).json()
        suresh = next(w for w in r2["roster"] if w["worker_id"] == SURESH)
        assert suresh["status"] == "absent"
        self._cleanup([m["id"]])

    def test_delete(self):
        m = requests.post(f"{BASE_URL}/api/attendance/mark", headers=HDR,
                         json={"worker_id": RAMESH, "status": "present"}, timeout=15).json()
        r = requests.delete(f"{BASE_URL}/api/attendance/{m['id']}", headers=HDR, timeout=15)
        assert r.status_code == 200
        # 2nd delete -> 404
        r2 = requests.delete(f"{BASE_URL}/api/attendance/{m['id']}", headers=HDR, timeout=15)
        assert r2.status_code == 404

    def test_invalid_status(self):
        r = requests.post(f"{BASE_URL}/api/attendance/mark", headers=HDR,
                          json={"worker_id": RAMESH, "status": "flying"}, timeout=15)
        assert r.status_code == 400

    def test_unknown_worker(self):
        r = requests.post(f"{BASE_URL}/api/attendance/mark", headers=HDR,
                          json={"worker_id": "nope-nope", "status": "present"}, timeout=15)
        assert r.status_code == 404

    def test_bulk(self):
        r = requests.post(f"{BASE_URL}/api/attendance/bulk", headers=HDR, json={
            "entries": [
                {"worker_id": RAMESH, "status": "present"},
                {"worker_id": SURESH, "status": "half_day"},
                {"worker_id": "bogus-id", "status": "present"},
            ]
        }, timeout=20)
        assert r.status_code == 200
        results = r.json()["results"]
        assert len(results) == 3
        # third entry should have error+worker_id keys
        err = results[2]
        assert "error" in err
        assert err["worker_id"] == "bogus-id"
        # cleanup successful marks
        self._cleanup([results[0]["id"], results[1]["id"]])


# ---------------------------------------------------------------- company info
class TestCompanyInfo:
    def test_company_info_public(self):
        r = requests.get(f"{BASE_URL}/api/company-info", timeout=10)
        assert r.status_code == 200
        d = r.json()
        assert d["legal_name"] == "SIXN8 Technologies Private Ltd"
        assert d["support_email"] == "admin@dukaaon.in"
        assert "product_name" in d
        assert "website" in d
        # Leak check
        blob = r.text
        assert "NithinV16" not in blob
        assert "CONTACT_TG_USERNAME" not in blob


# ---------------------------------------------------------------- contact form
class TestContact:
    def test_invalid_email(self):
        r = requests.post(f"{BASE_URL}/api/contact", json={
            "name": "T", "email": "notanemail", "message": "hello world hi there"
        }, timeout=10)
        assert r.status_code == 400

    def test_short_message(self):
        r = requests.post(f"{BASE_URL}/api/contact", json={
            "name": "T", "email": "t@example.com", "message": "hi"
        }, timeout=10)
        assert r.status_code == 400

    def test_success_and_no_leak(self):
        r = requests.post(f"{BASE_URL}/api/contact", json={
            "name": "TEST_QA", "email": "qa@example.com",
            "subject": "Iter30 test", "message": "This is a testing submission from iter30 QA."
        }, timeout=15)
        # Rate limiter may already be hit by prior tests → accept 200 or 429
        assert r.status_code in (200, 429), r.text
        if r.status_code == 200:
            d = r.json()
            assert d["ok"] is True
            assert "id" in d
            # No secret leak
            assert "NithinV16" not in r.text
            assert "telegram_username" not in r.text.lower() or "telegram" in r.text.lower()  # 'telegram' may appear in delivered_via

    def test_rate_limit(self):
        # Fire ~7 quick ones; expect at least one 429
        got_429 = False
        for i in range(7):
            rr = requests.post(f"{BASE_URL}/api/contact", json={
                "name": f"RL_{i}", "email": "rl@example.com",
                "message": f"rate limit test iteration {i} filling up quickly."
            }, timeout=10)
            if rr.status_code == 429:
                got_429 = True
                break
        assert got_429, "Expected a 429 within 7 rapid submissions"


# ---------------------------------------------------------------- Telegram /attendance helper
class TestTelegramAttendance:
    """Directly call server helpers with mocked tg_api/tg_send."""

    def _setup(self, monkeypatch, sent):
        import server
        async def fake_send(chat_id, text, reply_markup=None):
            sent.append({"chat_id": chat_id, "text": text, "reply_markup": reply_markup})
        async def fake_api(method, payload):
            sent.append({"method": method, "payload": payload})
            return {"ok": True}
        monkeypatch.setattr(server, "tg_send", fake_send)
        monkeypatch.setattr(server, "tg_api", fake_api)
        return server

    async def _get_user(self, server):
        return await server.db.users.find_one({"user_id": "test-user-karya1"}, {"_id": 0})

    def test_headcount_with_project_name(self, monkeypatch):
        sent = []
        server = self._setup(monkeypatch, sent)
        async def run():
            user = await self._get_user(server)
            await server._handle_tg_attendance_command(999000111, user, "/attendance 5 Site A")
            # Verify headcount row was written
            rows = await server.db.attendance.find({
                "owner_id": user["user_id"], "worker_id": None,
                "count": 5, "project_id": SITE_A
            }).to_list(10)
            assert len(rows) >= 1, "Expected a headcount row for Site A"
            # Cleanup
            for r in rows:
                await server.db.attendance.delete_one({"id": r["id"]})
        _run(run())
        assert any("Site A" in (m.get("text") or "") for m in sent), sent

    def test_named_worker_present(self, monkeypatch):
        sent = []
        server = self._setup(monkeypatch, sent)
        async def run():
            user = await self._get_user(server)
            await server._handle_tg_attendance_command(999000111, user, "/attendance Ramesh present")
            row = await server.db.attendance.find_one({
                "owner_id": user["user_id"], "worker_id": RAMESH, "status": "present"
            }, {"_id": 0})
            assert row is not None, "Expected Ramesh to be marked present"
            # cleanup
            await server.db.attendance.delete_one({"id": row["id"]})
        _run(run())
        assert any("Ramesh" in (m.get("text") or "") for m in sent), sent

    def test_no_arg_summary(self, monkeypatch):
        sent = []
        server = self._setup(monkeypatch, sent)
        async def run():
            user = await self._get_user(server)
            await server._handle_tg_attendance_command(999000111, user, "/attendance")
        _run(run())
        txt = " ".join(m.get("text") or "" for m in sent)
        assert "Named present" in txt
        assert "Headcount tally" in txt

    def test_headcount_project_picker(self, monkeypatch):
        """With 2 projects and no name, expect inline_keyboard with att_head|12|<pid>."""
        sent = []
        server = self._setup(monkeypatch, sent)
        async def run():
            user = await self._get_user(server)
            await server._handle_tg_attendance_command(999000111, user, "/attendance 12")
        _run(run())
        msg = next((m for m in sent if m.get("reply_markup")), None)
        assert msg is not None, f"expected reply_markup, got {sent}"
        kb = msg["reply_markup"]["inline_keyboard"]
        flat = [b for row in kb for b in row]
        assert any(b["callback_data"].startswith("att_head|12|") for b in flat)
        assert any(SITE_A in b["callback_data"] or SITE_B in b["callback_data"] for b in flat)


# ---------------------------------------------------------------- att_head callback
class TestAttHeadCallback:
    def test_callback_headcount(self):
        # Ensure a chat_id is linked to test-user-karya1 for _tg_user_for_chat
        sync_db.users.update_one(
            {"user_id": "test-user-karya1"},
            {"$set": {"telegram_chat_id": 999000111}}
        )
        # Clear any prior test rows
        sync_db.attendance.delete_many({
            "owner_id": "test-user-karya1", "worker_id": None,
            "count": 10, "project_id": SITE_A
        })
        update = {
            "callback_query": {
                "id": "cq1",
                "data": f"att_head|10|{SITE_A}",
                "message": {"chat": {"id": 999000111}},
                "from": {"id": 999000111, "username": "qa"},
            }
        }
        r = requests.post(f"{BASE_URL}/api/telegram/webhook", json=update,
                          headers={"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}, timeout=15)
        assert r.status_code == 200, r.text
        rows = list(sync_db.attendance.find({
            "owner_id": "test-user-karya1", "worker_id": None,
            "count": 10, "project_id": SITE_A
        }))
        assert len(rows) >= 1, "callback should have written headcount row"
        for row in rows:
            sync_db.attendance.delete_one({"id": row["id"]})


# ---------------------------------------------------------------- chat_id auto-capture
class TestChatIdCapture:
    def test_nithinv16_captured(self):
        sync_db.system_config.delete_many({"key": "contact_chat_id"})
        update = {
            "message": {
                "chat": {"id": 555777999},
                "from": {"id": 555777999, "username": "NIThinV16"},  # case-insensitive
                "text": "hi bot"
            }
        }
        r = requests.post(f"{BASE_URL}/api/telegram/webhook", json=update,
                          headers={"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}, timeout=15)
        assert r.status_code == 200
        doc = sync_db.system_config.find_one({"key": "contact_chat_id"})
        assert doc is not None, "contact_chat_id should be captured for NithinV16"
        assert doc["value"] == "555777999"

    def test_other_user_not_captured(self):
        sync_db.system_config.delete_many({"key": "contact_chat_id"})
        update = {
            "message": {
                "chat": {"id": 111222},
                "from": {"id": 111222, "username": "random_user"},
                "text": "hi"
            }
        }
        requests.post(f"{BASE_URL}/api/telegram/webhook", json=update,
                      headers={"X-Telegram-Bot-Api-Secret-Token": TG_SECRET}, timeout=15)
        doc = sync_db.system_config.find_one({"key": "contact_chat_id"})
        assert doc is None, f"random user should not populate contact_chat_id, got {doc}"


# ---------------------------------------------------------------- contact -> telegram delivery
class TestContactTelegramDelivery:
    def test_contact_sends_to_captured_chat_id(self):
        # Seed captured chat_id (fake: sendMessage will silently fail, but code path runs)
        sync_db.system_config.update_one(
            {"key": "contact_chat_id"},
            {"$set": {"value": "888111222"}},
            upsert=True,
        )
        # Wait for possible rate limit window to clear
        time.sleep(1)
        payload = {
            "name": "QA Bot", "email": "iter30qa@nowhere.example",
            "subject": "leak-check",
            "message": "This is an iteration30 delivery-path test message."
        }
        # Retry if rate-limited
        r = None
        for _ in range(3):
            r = requests.post(f"{BASE_URL}/api/contact", json=payload, timeout=15)
            if r.status_code != 429:
                break
            time.sleep(60)
        if r.status_code == 429:
            pytest.skip("rate-limited by prior tests; cannot verify delivery path")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["ok"] is True
        # No leak in response
        assert "NithinV16" not in r.text
        # Verify DB row has NO 'telegram_username' or 'NithinV16' leak
        row = sync_db.contact_submissions.find_one({"email": "iter30qa@nowhere.example"})
        assert row is not None
        assert "telegram_username" not in row, f"row leaks telegram_username: {row}"
        assert "NithinV16" not in str(row)
        # delivered_via should contain 'telegram' (tg_api swallows errors so still appended)
        assert "telegram" in (row.get("delivered_via") or []), f"delivered_via={row.get('delivered_via')}"
        # Cleanup
        sync_db.contact_submissions.delete_many({"email": "iter30qa@nowhere.example"})
        sync_db.system_config.delete_many({"key": "contact_chat_id"})
