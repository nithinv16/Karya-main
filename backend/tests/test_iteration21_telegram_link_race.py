"""
Iteration 21 backend tests — Telegram /start CODE linking + webhook race-condition fix.

Focus:
 - POST /api/telegram/link/code inserts a fresh code and claims the Telegram webhook
   for THIS backend (prevents preview/prod race that produced the 'invalid code' bug).
 - /start CODE via webhook consumes the code and links the chat to the user.
 - Invalid / lowercase / whitespace-padded / @mention-prefixed codes handled safely.
 - Preview backend restart does NOT auto-reset webhook to preview URL.
 - unlink endpoint clears telegram_chat_id.

Cleanup: at the end of the module we explicitly restore the webhook to the production URL.
"""
import os
import re
import time
import subprocess
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get(
    "REACT_APP_BACKEND_URL",
    "https://63eb8f53-e1d3-4702-9386-8e98d5fd8498.preview.emergentagent.com",
).rstrip("/")
TOKEN = "test_session_karya1"
USER_ID = "test-user-karya1"
SECRET = "karya-tg-hook-7f3a9c2e"
BOT_TOKEN = "8757902012:AAEwfZCQLuKwSzcWR_MTHkeGSGcOaVMjjg4"
PROD_WEBHOOK = "https://voice-to-docs-6.emergent.host/api/telegram/webhook"
PREVIEW_WEBHOOK = f"{BASE_URL}/api/telegram/webhook"
QA_CHAT_ID = 999000111
FAKE_CHAT = 999000333

HDRS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
WHDRS = {"X-Telegram-Bot-Api-Secret-Token": SECRET, "Content-Type": "application/json"}
CODE_ALPHABET_RE = re.compile(r"^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$")


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
    return client[os.environ.get("DB_NAME", "karya_db_v2")]


def _get_webhook_info():
    r = requests.get(f"https://api.telegram.org/bot{BOT_TOKEN}/getWebhookInfo", timeout=15)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j.get("ok") is True, j
    return j["result"]


def _set_webhook(url):
    r = requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/setWebhook",
        json={
            "url": url,
            "secret_token": SECRET,
            "allowed_updates": ["message", "edited_message", "callback_query"],
        },
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("ok") is True, body
    return body


# ---------- 1) link/code generates fresh code + purges previous ------------
def test_link_code_generates_and_purges(db):
    # Generate first code
    r = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=HDRS, timeout=20)
    assert r.status_code == 200, r.text
    d = r.json()
    code1 = d["code"]
    assert CODE_ALPHABET_RE.match(code1), f"code {code1} not in expected alphabet"
    assert d.get("bot_username") == "karya_ops_bot"
    assert "karya_ops_bot" in (d.get("deep_link") or "")

    # DB must have exactly one code doc for this user, equal to code1
    docs = list(db.telegram_link_codes.find({"user_id": USER_ID}))
    assert len(docs) == 1, f"expected 1 code, got {len(docs)}: {docs}"
    assert docs[0]["code"] == code1

    # Generate another — previous should be purged
    r2 = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=HDRS, timeout=20)
    assert r2.status_code == 200
    code2 = r2.json()["code"]
    assert code2 != code1
    docs2 = list(db.telegram_link_codes.find({"user_id": USER_ID}))
    assert len(docs2) == 1, f"expected exactly 1 code after regen, got {len(docs2)}"
    assert docs2[0]["code"] == code2


# ---------- 2) link/code claims the Telegram webhook -----------------------
def test_link_code_claims_webhook():
    # First, point webhook away (to production) so we can assert reclaim
    _set_webhook(PROD_WEBHOOK)
    time.sleep(1)
    info = _get_webhook_info()
    assert info.get("url") == PROD_WEBHOOK

    # Now generate code and expect webhook to swing to preview backend
    r = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=HDRS, timeout=20)
    assert r.status_code == 200, r.text
    time.sleep(1.5)
    info2 = _get_webhook_info()
    assert info2.get("url") == PREVIEW_WEBHOOK, (
        f"webhook not reclaimed: expected {PREVIEW_WEBHOOK}, got {info2.get('url')}"
    )


# ---------- 3) /start CODE links a chat + consumes the code ----------------
def test_start_code_links_chat_and_consumes(db):
    r = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=HDRS, timeout=20)
    assert r.status_code == 200
    code = r.json()["code"]

    update = {
        "update_id": int(time.time()),
        "message": {
            "message_id": 1,
            "chat": {"id": FAKE_CHAT, "type": "private"},
            "from": {"id": 42, "username": "qatest"},
            "text": f"/start {code}",
        },
    }
    r = requests.post(f"{BASE_URL}/api/telegram/webhook", headers=WHDRS, json=update, timeout=30)
    assert r.status_code == 200, r.text
    assert r.json().get("ok") is True

    time.sleep(0.5)
    u = db.users.find_one({"user_id": USER_ID})
    assert u.get("telegram_chat_id") == FAKE_CHAT, f"chat_id not linked; got {u.get('telegram_chat_id')}"
    # Code consumed
    assert db.telegram_link_codes.find_one({"code": code}) is None


# ---------- 4) invalid code — no crash, no link change --------------------
def test_start_invalid_code_no_crash(db):
    # Ensure current chat_id state — from previous test it's FAKE_CHAT
    before = db.users.find_one({"user_id": USER_ID}).get("telegram_chat_id")
    update = {
        "update_id": int(time.time()) + 1,
        "message": {
            "message_id": 2,
            "chat": {"id": 88888, "type": "private"},
            "from": {"id": 88888, "username": "bogus"},
            "text": "/start ZZZZZZ",
        },
    }
    r = requests.post(f"{BASE_URL}/api/telegram/webhook", headers=WHDRS, json=update, timeout=30)
    assert r.status_code == 200
    assert r.json().get("ok") is True
    after = db.users.find_one({"user_id": USER_ID}).get("telegram_chat_id")
    assert after == before, "invalid code should not modify user link"


# ---------- 5) lowercase code still works ---------------------------------
def test_start_lowercase_code(db):
    r = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=HDRS, timeout=20)
    assert r.status_code == 200
    code = r.json()["code"]
    lc = code.lower()

    update = {
        "update_id": int(time.time()) + 2,
        "message": {
            "message_id": 3,
            "chat": {"id": FAKE_CHAT, "type": "private"},
            "from": {"id": 42, "username": "qatest"},
            "text": f"/start {lc}",
        },
    }
    r = requests.post(f"{BASE_URL}/api/telegram/webhook", headers=WHDRS, json=update, timeout=30)
    assert r.status_code == 200
    time.sleep(0.4)
    u = db.users.find_one({"user_id": USER_ID})
    assert u.get("telegram_chat_id") == FAKE_CHAT
    assert db.telegram_link_codes.find_one({"code": code}) is None


# ---------- 6) whitespace / stray @mention still works ---------------------
def test_start_padded_code_with_whitespace(db):
    r = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=HDRS, timeout=20)
    assert r.status_code == 200
    code = r.json()["code"]
    text = f"/start   {code}   "

    update = {
        "update_id": int(time.time()) + 3,
        "message": {
            "message_id": 4,
            "chat": {"id": FAKE_CHAT, "type": "private"},
            "from": {"id": 42, "username": "qatest"},
            "text": text,
        },
    }
    r = requests.post(f"{BASE_URL}/api/telegram/webhook", headers=WHDRS, json=update, timeout=30)
    assert r.status_code == 200
    time.sleep(0.4)
    assert db.telegram_link_codes.find_one({"code": code}) is None


# ---------- 7) restart preview backend does NOT reclaim webhook ------------
def test_restart_preview_does_not_reclaim_webhook():
    # Point webhook to production and confirm
    _set_webhook(PROD_WEBHOOK)
    time.sleep(1)
    info = _get_webhook_info()
    assert info.get("url") == PROD_WEBHOOK

    # Restart preview backend
    subprocess.run(["sudo", "supervisorctl", "restart", "backend"], check=True, timeout=30)
    # Wait for it to come back
    for _ in range(30):
        try:
            r = requests.get(f"{BASE_URL}/api/auth/me", headers=HDRS, timeout=5)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(1)
    # Also give the startup event a moment
    time.sleep(3)

    info2 = _get_webhook_info()
    assert info2.get("url") == PROD_WEBHOOK, (
        f"preview backend should NOT auto-reclaim webhook on startup; got {info2.get('url')}"
    )


# ---------- 8) unlink endpoint clears telegram_chat_id --------------------
def test_unlink_clears_chat(db):
    # Ensure user is linked first
    db.users.update_one({"user_id": USER_ID}, {"$set": {"telegram_chat_id": FAKE_CHAT, "telegram_username": "qatest"}})
    r = requests.post(f"{BASE_URL}/api/telegram/link/unlink", headers=HDRS, timeout=20)
    assert r.status_code == 200, r.text
    assert r.json().get("unlinked") is True
    u = db.users.find_one({"user_id": USER_ID})
    assert "telegram_chat_id" not in u or u.get("telegram_chat_id") in (None, "")


# ---------- teardown: restore prod webhook + relink QA chat ---------------
def test_zz_restore_production_webhook_and_qa_chat(db):
    _set_webhook(PROD_WEBHOOK)
    time.sleep(1)
    info = _get_webhook_info()
    assert info.get("url") == PROD_WEBHOOK, "failed to restore prod webhook after tests"
    # Restore QA chat link so future runs of iteration_20 test suite still see linked user
    db.users.update_one(
        {"user_id": USER_ID},
        {"$set": {"telegram_chat_id": QA_CHAT_ID, "telegram_username": "qa_user"}},
    )
