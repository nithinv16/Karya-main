"""Iteration 24: Telegram voice-in -> voice-out (OpenAI TTS) + regressions."""
import os
import sys
import asyncio
import io
import pytest
import requests

# --- Ensure backend package importable for direct function tests -------------
BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "").rstrip("/")
if not BASE_URL:
    # Fallback to the URL in frontend/.env (tests run from repo)
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
TIMEOUT = 60


# =============================================================================
# Unit tests — importing backend.server directly
# =============================================================================
import server  # noqa: E402


# ---- Test 1: _for_tts strips HTML but preserves currency & advance ---------
def test_for_tts_strips_html_and_markdown():
    out = server._for_tts("<b>Logged</b> — advance of <code>₹5,000</code>")
    assert "<" not in out and ">" not in out, f"HTML tag chars leaked: {out!r}"
    assert "₹5,000" in out, f"Currency lost: {out!r}"
    assert "advance" in out.lower(), f"'advance' word lost: {out!r}"
    # em-dash should be replaced with something readable (comma-space)
    assert "—" not in out


# ---- Test 2: _TG_SPEAK ContextVar default + set/reset -----------------------
def test_tg_speak_contextvar_default_and_reset():
    assert server._TG_SPEAK.get() is False, "ContextVar default should be False"
    token = server._TG_SPEAK.set(True)
    assert server._TG_SPEAK.get() is True
    server._TG_SPEAK.reset(token)
    assert server._TG_SPEAK.get() is False


# ---- Test 3: Live OpenAI TTS generates valid OGG opus -----------------------
def test_openai_tts_generates_ogg_bytes():
    from emergentintegrations.llm.openai import OpenAITextToSpeech
    tts = OpenAITextToSpeech(api_key=server.EMERGENT_LLM_KEY)

    async def _go():
        return await tts.generate_speech(
            text="Recorded advance of 5000 rupees for Ramesh.",
            model="tts-1", voice="nova", response_format="opus",
        )

    audio = asyncio.get_event_loop().run_until_complete(_go()) if False else asyncio.run(_go())
    assert isinstance(audio, (bytes, bytearray)), f"expected bytes, got {type(audio)}"
    assert len(audio) >= 5 * 1024, f"audio too small ({len(audio)} bytes)"
    assert len(audio) <= 200 * 1024, f"audio too large ({len(audio)} bytes)"
    # OGG magic 'OggS' = 0x4f676753
    assert audio[:4] == b"OggS", f"missing OggS magic; head={audio[:8]!r}"


# ---- Test 3b: tg_speak with fake chat_id — TTS succeeds, sendVoice fails silently
def test_tg_speak_fake_chat_id_does_not_raise():
    async def _go():
        # chat_id=1 is a fake — Telegram sendVoice will return an error, but tg_speak swallows it
        await server.tg_speak(chat_id=1, text="Recorded advance of 5000 rupees for Ramesh.")
    asyncio.run(_go())  # should not raise


# ---- Test 4: tg_send also speaks when _TG_SPEAK is True --------------------
def test_tg_send_also_speaks_when_flag_true(monkeypatch):
    api_calls = []
    speak_calls = []

    async def fake_api(method, payload):
        api_calls.append((method, payload))
        return {"ok": True}

    async def fake_speak(chat_id, text, lang="en"):
        speak_calls.append((chat_id, text))

    monkeypatch.setattr(server, "tg_api", fake_api)
    monkeypatch.setattr(server, "tg_speak", fake_speak)

    async def _go_true():
        token = server._TG_SPEAK.set(True)
        try:
            await server.tg_send(1, "hello")
        finally:
            server._TG_SPEAK.reset(token)

    asyncio.run(_go_true())
    assert len(api_calls) == 1 and api_calls[0][0] == "sendMessage"
    assert api_calls[0][1]["chat_id"] == 1 and api_calls[0][1]["text"] == "hello"
    assert speak_calls == [(1, "hello")], f"tg_speak not called: {speak_calls!r}"


def test_tg_send_does_not_speak_when_flag_false(monkeypatch):
    api_calls = []
    speak_calls = []

    async def fake_api(method, payload):
        api_calls.append((method, payload))
        return {"ok": True}

    async def fake_speak(chat_id, text, lang="en"):
        speak_calls.append((chat_id, text))

    monkeypatch.setattr(server, "tg_api", fake_api)
    monkeypatch.setattr(server, "tg_speak", fake_speak)

    async def _go_false():
        # default False
        await server.tg_send(1, "hello")

    asyncio.run(_go_false())
    assert len(api_calls) == 1
    assert speak_calls == [], f"tg_speak should NOT have been called: {speak_calls!r}"


# ---- Test 5: _handle_tg_voice sets flag then resets ------------------------
def test_handle_tg_voice_sets_and_resets_flag(monkeypatch):
    seen_flag = {"inside": None}

    async def fake_get_file_bytes(file_id):
        return (b"FAKE_BYTES", "voice.ogg")

    class _FakeResp:
        text = "Test transcript"

    class FakeSTT:
        def __init__(self, api_key):
            pass

        async def transcribe(self, file, model="whisper-1", response_format="json"):
            return _FakeResp()

    async def fake_handle_text(chat_id, text, user):
        seen_flag["inside"] = server._TG_SPEAK.get()
        seen_flag["text"] = text

    async def fake_tg_send(chat_id, text, reply_markup=None):
        # avoid real Telegram + avoid the also-speak side effect chain (tg_speak needs TTS)
        return {"ok": True}

    monkeypatch.setattr(server, "tg_get_file_bytes", fake_get_file_bytes)
    monkeypatch.setattr(server, "OpenAISpeechToText", FakeSTT)
    monkeypatch.setattr(server, "_handle_tg_text", fake_handle_text)
    monkeypatch.setattr(server, "tg_send", fake_tg_send)

    async def _go():
        await server._handle_tg_voice(999000111, "fake_file_id", {"user_id": "u1"})

    asyncio.run(_go())
    assert seen_flag["inside"] is True, f"Flag inside handler was {seen_flag['inside']!r}"
    assert seen_flag.get("text") == "Test transcript"
    # After handler returns, flag must be back to default False
    assert server._TG_SPEAK.get() is False


# ---- Test 6: tg_speak failure resilience — TTS raise must NOT propagate ----
def test_tg_speak_swallows_tts_errors(monkeypatch):
    class BoomTTS:
        def __init__(self, api_key):
            pass

        async def generate_speech(self, text, model, voice, response_format):
            raise RuntimeError("quota")

    monkeypatch.setattr(server, "OpenAITextToSpeech", BoomTTS)

    async def _go():
        # must NOT raise
        await server.tg_speak(chat_id=1, text="anything")

    asyncio.run(_go())  # no exception expected


# =============================================================================
# Regression tests — HTTP against live backend
# =============================================================================

# ---- Test 7: /start CODE flow (iteration_21) still links ------------------
def test_regression_telegram_start_code_links_user():
    # 1) Get a fresh code
    r = requests.post(f"{BASE_URL}/api/telegram/link/code", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200, f"link/code failed: {r.status_code} {r.text}"
    code = r.json().get("code")
    assert code and len(code) == 6, f"bad code: {code!r}"

    # 2) POST /start with that code to webhook (with secret header)
    webhook_headers = {
        "Content-Type": "application/json",
        "X-Telegram-Bot-Api-Secret-Token": "karya-tg-hook-7f3a9c2e",
    }
    payload = {
        "update_id": 999888777,
        "message": {
            "message_id": 1,
            "date": 1700000000,
            "chat": {"id": 999000111, "type": "private"},
            "from": {"id": 999000111, "is_bot": False, "first_name": "QA", "username": "qa_karya"},
            "text": f"/start {code}",
        },
    }
    r2 = requests.post(f"{BASE_URL}/api/telegram/webhook", json=payload, headers=webhook_headers, timeout=TIMEOUT)
    assert r2.status_code in (200, 204), f"webhook returned {r2.status_code}: {r2.text}"

    # 3) status should now show linked with chat_id=999000111
    r3 = requests.get(f"{BASE_URL}/api/telegram/status", headers=AUTH, timeout=TIMEOUT)
    assert r3.status_code == 200
    body = r3.json()
    assert body.get("linked") is True, f"not linked: {body}"
    assert body.get("chat_id") == 999000111, f"chat_id mismatch: {body}"


# ---- Test 8: /api/translate + /api/help/ask (iteration_23) -----------------
def test_regression_translate_returns_hindi():
    r = requests.post(
        f"{BASE_URL}/api/translate",
        json={"text": "Hello, please come to site tomorrow.", "target_lang": "hi"},
        headers=AUTH, timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    body = r.json()
    translated = body.get("translated_text") or body.get("translated") or body.get("text") or ""
    import re as _re
    assert _re.search(r"[\u0900-\u097F]", translated), f"no Devanagari in translation: {translated!r}"


def test_regression_help_ask_returns_answer():
    r = requests.post(
        f"{BASE_URL}/api/help/ask",
        json={"question": "How do I log an advance?"},
        headers=AUTH, timeout=TIMEOUT,
    )
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    body = r.json()
    answer = body.get("answer") or body.get("text") or ""
    assert isinstance(answer, str) and len(answer) > 20, f"empty/short answer: {answer!r}"


# ---- Test 9: /api/insights has_data (iteration_22) ------------------------
def test_regression_insights_has_data_field():
    r = requests.get(f"{BASE_URL}/api/insights", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200, f"{r.status_code}: {r.text}"
    body = r.json()
    assert "has_data" in body, f"has_data missing: keys={list(body.keys())}"
    assert isinstance(body["has_data"], bool)


# =============================================================================
# Teardown — restore QA chat_id to 999000111 (idempotent, already set by test 7)
# =============================================================================
def teardown_module(module):
    # The regression /start test above ends with chat_id=999000111 which matches
    # the pre-test state, so nothing extra to do. Kept as a safety hook.
    pass
