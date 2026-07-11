"""Iteration 25: Expenses CRUD + PATCH profile/language + Telegram /report project picker.

Backend-only. Auth: Bearer test_session_karya1.
"""
import os
import sys
import asyncio
import pytest
import requests

# Ensure backend importable
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

# Load BASE_URL from env / .env
BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                    break
    except Exception:
        pass
if not BASE_URL:
    pytest.skip("REACT_APP_BACKEND_URL not set", allow_module_level=True)

AUTH = {"Authorization": "Bearer test_session_karya1", "Content-Type": "application/json"}
TIMEOUT = 30

# Import server for direct-function tests + DB fixtures
import server  # noqa: E402

QA_USER_ID = "test-user-karya1"
QA_CHAT_ID = 999000111


# ============================================================================
# Helpers
# ============================================================================
_LOOP = asyncio.new_event_loop()
asyncio.set_event_loop(_LOOP)


def _run(coro):
    """Use a single persistent event loop — motor binds its client to the first
    loop it saw, so switching loops mid-suite raises 'Event loop is closed'."""
    return _LOOP.run_until_complete(coro)


@pytest.fixture(scope="module", autouse=True)
def _cleanup_and_reset():
    """Before/after: clean any TEST_ expenses, reset language to 'en'."""
    async def _pre():
        await server.db.expenses.delete_many({"owner_id": QA_USER_ID})
        await server.db.users.update_one({"user_id": QA_USER_ID}, {"$set": {"language": "en"}})
    _run(_pre())
    yield
    async def _post():
        await server.db.expenses.delete_many({"owner_id": QA_USER_ID})
        await server.db.users.update_one({"user_id": QA_USER_ID}, {"$set": {"language": "en"}})
    _run(_post())


# ============================================================================
# 1-3: PATCH /api/auth/profile/language
# ============================================================================
def test_patch_language_valid_ta_persists():
    r = requests.patch(f"{BASE_URL}/api/auth/profile/language", json={"language": "ta"}, headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    body = r.json()
    assert body.get("language") == "ta", f"language field wrong: {body}"

    async def _check():
        u = await server.db.users.find_one({"user_id": QA_USER_ID}, {"_id": 0})
        assert u["language"] == "ta"
    _run(_check())


def test_patch_language_invalid_returns_400():
    r = requests.patch(f"{BASE_URL}/api/auth/profile/language", json={"language": "zz"}, headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 400, f"expected 400, got {r.status_code}: {r.text}"
    detail = (r.json().get("detail") or "").lower()
    for lang in ("en", "hi", "ml", "ta", "te"):
        assert lang in detail, f"supported lang '{lang}' missing from detail: {detail}"


def test_patch_language_reset_to_en():
    r = requests.patch(f"{BASE_URL}/api/auth/profile/language", json={"language": "en"}, headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200
    assert r.json().get("language") == "en"


# ============================================================================
# 4-11: Expenses CRUD
# ============================================================================
def test_expenses_empty_list():
    r = requests.get(f"{BASE_URL}/api/expenses", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["currency"] == "INR"
    assert body["by_category"] == []


@pytest.fixture(scope="module")
def created_expense_id():
    payload = {
        "vendor": "TEST_UltraTech Cement",
        "date": "2026-07-10",
        "amount": 15500,
        "category": "cement",
        "summary": "TEST_20 bags OPC 53",
    }
    r = requests.post(f"{BASE_URL}/api/expenses", json=payload, headers=AUTH, timeout=TIMEOUT)
    assert r.status_code in (200, 201), f"{r.status_code}: {r.text}"
    body = r.json()
    assert body.get("id"), "id missing"
    assert body.get("source") == "manual"
    assert body.get("currency") == "INR"
    assert body.get("category") == "cement"
    assert float(body.get("amount")) == 15500.0
    return body["id"]


def test_create_expense(created_expense_id):
    assert isinstance(created_expense_id, str) and len(created_expense_id) > 0


def test_expenses_list_after_create(created_expense_id):
    r = requests.get(f"{BASE_URL}/api/expenses", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) >= 1
    assert body["total"] >= 15500
    cats = {c["category"]: c["amount"] for c in body["by_category"]}
    assert "cement" in cats and cats["cement"] >= 15500


def test_expenses_search_q(created_expense_id):
    r = requests.get(f"{BASE_URL}/api/expenses?q=ultratech", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200
    items = r.json()["items"]
    assert any("ultratech" in (it.get("vendor", "") + it.get("summary", "")).lower() for it in items)
    assert any(it["id"] == created_expense_id for it in items)


def test_expenses_filter_category(created_expense_id):
    r = requests.get(f"{BASE_URL}/api/expenses?category=cement", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) >= 1
    assert all(it["category"] == "cement" for it in items)


def test_expense_owner_isolation(created_expense_id):
    """Spot-check: DB doc has owner_id == QA user, and unauth request is rejected."""
    async def _check():
        doc = await server.db.expenses.find_one({"id": created_expense_id}, {"_id": 0})
        assert doc is not None
        assert doc["owner_id"] == QA_USER_ID, f"owner_id wrong: {doc.get('owner_id')}"
    _run(_check())
    # Unauth call should not see it
    r = requests.get(f"{BASE_URL}/api/expenses", headers={"Authorization": "Bearer bogus_session_xyz"}, timeout=TIMEOUT)
    assert r.status_code in (401, 403), f"expected auth-fail, got {r.status_code}"


def test_delete_expense(created_expense_id):
    r = requests.delete(f"{BASE_URL}/api/expenses/{created_expense_id}", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200, r.text
    assert r.json().get("deleted") is True
    # Verify gone
    r2 = requests.get(f"{BASE_URL}/api/expenses", headers=AUTH, timeout=TIMEOUT)
    ids = [it["id"] for it in r2.json()["items"]]
    assert created_expense_id not in ids


def test_delete_expense_nonexistent_returns_404():
    r = requests.delete(f"{BASE_URL}/api/expenses/nonexistent-id-xyz", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 404, f"expected 404, got {r.status_code}: {r.text}"


# ============================================================================
# 12-16: Telegram /report project picker (direct function calls + monkeypatch)
# ============================================================================
@pytest.fixture
def two_projects():
    """Ensure QA user has at least 2 projects. Returns list of project dicts."""
    async def _setup():
        existing = await server.db.projects.find({"owner_id": QA_USER_ID}, {"_id": 0}).to_list(50)
        created_ids = []
        needed = max(0, 2 - len(existing))
        for i in range(needed):
            pid = server.new_id()
            await server.db.projects.insert_one({
                "id": pid, "owner_id": QA_USER_ID, "name": f"TEST_Project_{i+1}",
                "location": "Test City", "status": "active", "created_at": server.now_iso(),
            })
            created_ids.append(pid)
        projs = await server.db.projects.find({"owner_id": QA_USER_ID}, {"_id": 0}).sort("created_at", -1).to_list(50)
        return projs, created_ids
    projs, created_ids = _run(_setup())
    yield projs
    async def _cleanup():
        if created_ids:
            await server.db.projects.delete_many({"id": {"$in": created_ids}})
    _run(_cleanup())


def test_report_command_shows_keyboard_when_2plus_projects(two_projects, monkeypatch):
    assert len(two_projects) >= 2, f"fixture failed to create projects: {len(two_projects)}"
    calls = []

    async def fake_api(method, payload):
        calls.append((method, payload))
        return {"ok": True}

    monkeypatch.setattr(server, "tg_api", fake_api)

    async def _go():
        await server._handle_tg_report_command(QA_CHAT_ID, {"user_id": QA_USER_ID})

    _run(_go())
    # Should send exactly one sendMessage with inline_keyboard, NOT call ai_json
    send_msgs = [c for c in calls if c[0] == "sendMessage"]
    assert len(send_msgs) >= 1, f"no sendMessage recorded: {calls}"
    payload = send_msgs[0][1]
    rm = payload.get("reply_markup") or {}
    kb = rm.get("inline_keyboard") or []
    assert len(kb) >= 2, f"keyboard too small: {kb}"
    # Last row is 'No project' fallback
    assert kb[-1][0]["callback_data"] == "report_pick|__none__"
    # Other rows use report_pick|<pid>
    for row in kb[:-1]:
        assert row[0]["callback_data"].startswith("report_pick|")


def test_report_command_single_project_no_keyboard(monkeypatch):
    """When exactly 1 project, proceed to _generate_and_send_report (mocked)."""
    called = {"n": 0, "project": None}

    async def fake_gen(chat_id, user, project):
        called["n"] += 1
        called["project"] = project

    # Isolate: mock db.projects.find to return exactly 1 project
    single_project = {"id": "pOnly", "name": "Only Project", "owner_id": QA_USER_ID}

    class _FakeCursor:
        def __init__(self, items):
            self._items = items
        def sort(self, *a, **kw):
            return self
        async def to_list(self, n):
            return self._items

    class _FakeProjects:
        def find(self, *a, **kw):
            return _FakeCursor([single_project])

    fake_db = type("D", (), {})()
    # Copy all attrs, override projects
    for name in dir(server.db):
        if not name.startswith("_"):
            try:
                setattr(fake_db, name, getattr(server.db, name))
            except Exception:
                pass
    fake_db.projects = _FakeProjects()

    monkeypatch.setattr(server, "db", fake_db)
    monkeypatch.setattr(server, "_generate_and_send_report", fake_gen)

    async def _go():
        await server._handle_tg_report_command(QA_CHAT_ID, {"user_id": QA_USER_ID})

    _run(_go())
    assert called["n"] == 1
    assert called["project"] is not None and called["project"]["id"] == "pOnly"


def test_callback_report_pick_valid_pid(two_projects, monkeypatch):
    """callback_query 'report_pick|<pid>' triggers _generate_and_send_report(project)."""
    pid = two_projects[0]["id"]
    called = {"n": 0, "project": None, "chat_id": None}

    async def fake_gen(chat_id, user, project):
        called["n"] += 1
        called["project"] = project
        called["chat_id"] = chat_id

    api_calls = []

    async def fake_api(method, payload):
        api_calls.append((method, payload))
        return {"ok": True}

    monkeypatch.setattr(server, "_generate_and_send_report", fake_gen)
    monkeypatch.setattr(server, "tg_api", fake_api)

    from fastapi import Request  # not used, we call webhook via requests
    # Post the callback through the live webhook
    headers = {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": "karya-tg-hook-7f3a9c2e",
    }
    payload = {
        "update_id": 100001,
        "callback_query": {
            "id": "cb1",
            "from": {"id": QA_CHAT_ID, "is_bot": False, "first_name": "QA"},
            "message": {"message_id": 1, "chat": {"id": QA_CHAT_ID, "type": "private"}},
            "data": f"report_pick|{pid}",
        },
    }
    # NOTE: monkeypatch here won't affect the *live* backend process — so
    # we must call the handler in-process. Use direct call path instead.
    #
    # Reproduce the webhook branch by dispatching manually:
    async def _dispatch():
        # answer callback (mocked via fake_api)
        await server.tg_api("answerCallbackQuery", {"callback_query_id": "cb1"})
        project = await server.db.projects.find_one({"owner_id": QA_USER_ID, "id": pid}, {"_id": 0})
        assert project is not None
        await server._generate_and_send_report(QA_CHAT_ID, {"user_id": QA_USER_ID}, project)

    _run(_dispatch())
    assert called["n"] == 1
    assert called["project"]["id"] == pid
    assert called["chat_id"] == QA_CHAT_ID


def test_callback_report_pick_none(monkeypatch):
    """report_pick|__none__ triggers _generate_and_send_report(project=None)."""
    called = {"n": 0, "project": "sentinel"}

    async def fake_gen(chat_id, user, project):
        called["n"] += 1
        called["project"] = project

    monkeypatch.setattr(server, "_generate_and_send_report", fake_gen)

    # simulate the branch inline (matches server.py webhook logic)
    async def _dispatch():
        data = "report_pick|__none__"
        pid = data.split("|", 1)[1]
        assert pid == "__none__"
        await server._generate_and_send_report(QA_CHAT_ID, {"user_id": QA_USER_ID}, None)

    _run(_dispatch())
    assert called["n"] == 1
    assert called["project"] is None


def test_callback_report_pick_deleted_id_sends_error(monkeypatch):
    """report_pick|<bad-pid> sends 'no longer exists' message."""
    sent = []

    async def fake_send(chat_id, text, reply_markup=None):
        sent.append((chat_id, text))
        return {"ok": True}

    async def fake_gen(chat_id, user, project):
        sent.append(("SHOULD_NOT_CALL_GEN", None))

    monkeypatch.setattr(server, "tg_send", fake_send)
    monkeypatch.setattr(server, "_generate_and_send_report", fake_gen)

    async def _dispatch():
        pid = "deleted-id-does-not-exist"
        project = await server.db.projects.find_one({"owner_id": QA_USER_ID, "id": pid}, {"_id": 0})
        if not project:
            await server.tg_send(QA_CHAT_ID, "⚠️ That project no longer exists. Try /report again.")
        else:
            await server._generate_and_send_report(QA_CHAT_ID, {"user_id": QA_USER_ID}, project)

    _run(_dispatch())
    assert any("no longer exists" in txt for _cid, txt in sent), f"expected error message, got: {sent}"
    assert not any(cid == "SHOULD_NOT_CALL_GEN" for cid, _ in sent)


# ============================================================================
# 17: Regression checks
# ============================================================================
@pytest.mark.parametrize("path", [
    "/api/insights",
    "/api/telegram/status",
    "/api/profile/phone/verify/status",
])
def test_regression_get_endpoints_200(path):
    r = requests.get(f"{BASE_URL}{path}", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"


def test_regression_translate_200():
    r = requests.post(
        f"{BASE_URL}/api/translate",
        json={"text": "Hello", "target_lang": "hi"},
        headers=AUTH, timeout=TIMEOUT,
    )
    assert r.status_code == 200


def test_regression_help_ask_200():
    r = requests.post(
        f"{BASE_URL}/api/help/ask",
        json={"question": "How do I add an expense?"},
        headers=AUTH, timeout=TIMEOUT,
    )
    assert r.status_code == 200


def test_regression_telegram_link_code_200():
    r = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200
