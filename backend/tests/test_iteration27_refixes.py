"""
Iteration 27 re-test — focused verification of two fixes:
  (1) GET /api/expenses limit clamping (0 -> 1, 99999 -> 2000, -5 -> 1)
  (2) _send_ping idempotency via _ping_already_sent pre-check
"""
import os
import sys
import asyncio
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
TOKEN = "test_session_karya1"
H = {"Authorization": f"Bearer {TOKEN}"}
UID = "test-user-karya1"

sys.path.insert(0, "/app/backend")
import server  # noqa: E402


# -----------------------------------------------------------------------------
# Fix 1: /api/expenses limit clamping
# -----------------------------------------------------------------------------

def _ensure_at_least_one_expense():
    r = requests.get(f"{BASE}/api/expenses", headers=H)
    assert r.status_code == 200, r.text
    if r.json().get("count", 0) == 0:
        seed = requests.post(
            f"{BASE}/api/expenses",
            headers=H,
            json={"amount": 12.5, "category": "other", "vendor": "TEST_REFIX_seed", "summary": "TEST_REFIX seed"},
        )
        assert seed.status_code in (200, 201), seed.text


def test_expenses_limit_zero_clamps_to_one():
    _ensure_at_least_one_expense()
    r = requests.get(f"{BASE}/api/expenses?limit=0", headers=H)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["limit"] == 1, f"expected limit=1, got {body['limit']}"
    assert len(body["items"]) == 1, f"expected 1 item, got {len(body['items'])}"


def test_expenses_limit_huge_clamps_to_2000():
    r = requests.get(f"{BASE}/api/expenses?limit=99999", headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["limit"] == 2000


def test_expenses_limit_negative_clamps_to_one():
    r = requests.get(f"{BASE}/api/expenses?limit=-5", headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["limit"] == 1


def test_expenses_limit_garbage_defaults():
    r = requests.get(f"{BASE}/api/expenses?limit=abc", headers=H)
    # FastAPI's int query typing will 422 on non-int; that's acceptable behavior.
    assert r.status_code in (200, 422), r.text


# -----------------------------------------------------------------------------
# Fix 2: _send_ping idempotency
# -----------------------------------------------------------------------------

def test_send_ping_is_idempotent_same_dedup_key(monkeypatch):
    calls = []

    async def fake_tg_send(chat_id, text, *args, **kwargs):
        calls.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(server, "tg_send", fake_tg_send)

    user = {"user_id": UID, "telegram_chat_id": 123456789, "language": "en"}
    dedup_key = "TEST_REFIX_DEDUP_2026_01_01"
    ping_type = "morning_briefing"

    async def run():
        await server.db.ping_log.delete_many(
            {"user_id": UID, "type": ping_type, "day": dedup_key}
        )
        try:
            await server._send_ping(user, ping_type, "hello test", dedup_key)
            await server._send_ping(user, ping_type, "hello test", dedup_key)
            log_count = await server.db.ping_log.count_documents(
                {"user_id": UID, "type": ping_type, "day": dedup_key}
            )
            return log_count
        finally:
            await server.db.ping_log.delete_many(
                {"user_id": UID, "type": ping_type, "day": dedup_key}
            )

    log_count = asyncio.get_event_loop().run_until_complete(run())
    assert len(calls) == 1, f"expected exactly 1 tg_send call, got {len(calls)}"
    assert log_count == 1, f"expected 1 ping_log entry, got {log_count}"


def test_send_ping_different_dedup_keys_both_send(monkeypatch):
    calls = []

    async def fake_tg_send(chat_id, text, *args, **kwargs):
        calls.append((chat_id, text))
        return {"ok": True}

    monkeypatch.setattr(server, "tg_send", fake_tg_send)

    user = {"user_id": UID, "telegram_chat_id": 123456789, "language": "en"}
    ping_type = "morning_briefing"
    k1 = "TEST_REFIX_DEDUP_KEY_A"
    k2 = "TEST_REFIX_DEDUP_KEY_B"

    async def run():
        await server.db.ping_log.delete_many(
            {"user_id": UID, "type": ping_type, "day": {"$in": [k1, k2]}}
        )
        try:
            await server._send_ping(user, ping_type, "msg-a", k1)
            await server._send_ping(user, ping_type, "msg-b", k2)
        finally:
            await server.db.ping_log.delete_many(
                {"user_id": UID, "type": ping_type, "day": {"$in": [k1, k2]}}
            )

    asyncio.get_event_loop().run_until_complete(run())
    assert len(calls) == 2, f"expected 2 tg_send calls, got {len(calls)}"
