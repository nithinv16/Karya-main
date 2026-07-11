"""Iteration 23: /api/translate + /api/help/ask + regressions."""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or pytest.skip(
    "REACT_APP_BACKEND_URL not set", allow_module_level=True
)
AUTH = {"Authorization": "Bearer test_session_karya1", "Content-Type": "application/json"}
TIMEOUT = 60

DEVANAGARI = re.compile(r"[\u0900-\u097F]")
MALAYALAM = re.compile(r"[\u0D00-\u0D7F]")
TAMIL = re.compile(r"[\u0B80-\u0BFF]")
TELUGU = re.compile(r"[\u0C00-\u0C7F]")


def _translate(text, lang):
    return requests.post(
        f"{BASE_URL}/api/translate",
        json={"text": text, "target_lang": lang},
        headers=AUTH,
        timeout=TIMEOUT,
    )


# ---- Reset user language to en at module start & teardown -------------------
def _get_me():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=AUTH, timeout=TIMEOUT)
    if r.status_code == 200:
        body = r.json()
        return body.get("user") if isinstance(body, dict) and "user" in body else body
    return {}


def _put_profile(patch):
    me = _get_me()
    payload = {
        "name": me.get("name") or "Test User",
        "phone": me.get("phone", "") or "",
        "address": me.get("address", "") or "",
        "company_name": me.get("company_name", "") or "",
        "role": me.get("role", "") or "",
        "default_client_phone": me.get("default_client_phone", "") or "",
        "country": me.get("country", "IN") or "IN",
        "language": me.get("language", "en") or "en",
        "ramadan_mode": bool(me.get("ramadan_mode", False)),
    }
    payload.update(patch)
    return requests.put(f"{BASE_URL}/api/auth/profile", json=payload, headers=AUTH, timeout=TIMEOUT)


@pytest.fixture(scope="module", autouse=True)
def _reset_language():
    _put_profile({"language": "en"})
    yield
    _put_profile({"language": "en"})


# 1) Translate to Hindi — real translation, no English "Send"/"photo" words
def test_translate_hindi_real_translation():
    text = "Send a photo of the worker ID to Telegram — the bot will file it under the correct worker."
    # clean cache first: try a slightly different text so we're sure cached=false path runs
    # But since translations cache is global, first call may be cached from previous runs.
    # We just need to confirm it's a real Hindi translation.
    r = _translate(text, "hi")
    assert r.status_code == 200, r.text
    data = r.json()
    out = data.get("translated", "")
    assert out, "empty translation"
    assert DEVANAGARI.search(out), f"no Devanagari in: {out!r}"
    # Not answering — no standalone English 'Send' or 'photo'
    assert not re.search(r"\bSend\b", out), f"leaked English 'Send': {out!r}"
    assert not re.search(r"\bphoto\b", out, re.IGNORECASE), f"leaked English 'photo': {out!r}"


# 2) target_lang=en short-circuits
def test_translate_en_short_circuit():
    text = "Hello world"
    r = _translate(text, "en")
    assert r.status_code == 200
    data = r.json()
    assert data["translated"] == text
    assert data["cached"] is False


# 3) unsupported lang -> 400
def test_translate_unsupported_lang():
    r = _translate("hello", "zz")
    assert r.status_code == 400


# 4) empty text -> 400
def test_translate_empty_text():
    r = _translate("   ", "hi")
    assert r.status_code == 400


# 5) Cache behaviour
def test_translate_cache():
    import uuid
    unique = f"Cache probe {uuid.uuid4().hex[:12]}"
    r1 = _translate(unique, "hi")
    assert r1.status_code == 200
    assert r1.json().get("cached") is False
    assert r1.json().get("translated")
    r2 = _translate(unique, "hi")
    assert r2.status_code == 200
    assert r2.json().get("cached") is True
    assert r2.json().get("translated") == r1.json().get("translated")


# 6) Do NOT answer questions — translate the question
def test_translate_does_not_answer_question():
    r = _translate("How do I add a worker?", "ml")
    assert r.status_code == 200
    out = r.json().get("translated", "")
    assert out
    assert MALAYALAM.search(out), f"no Malayalam: {out!r}"
    assert len(out) < 300, f"looks like an answer/tutorial ({len(out)} chars): {out!r}"


# 7) Supported languages
@pytest.mark.parametrize("lang,pattern", [
    ("hi", DEVANAGARI),
    ("ml", MALAYALAM),
    ("ta", TAMIL),
    ("te", TELUGU),
])
def test_translate_supported_languages(lang, pattern):
    r = _translate("Daily Reports", lang)
    assert r.status_code == 200, r.text
    out = r.json().get("translated", "")
    if not out:
        # retry once
        r = _translate("Daily Reports", lang)
        out = r.json().get("translated", "")
    assert out, f"empty translation for {lang}"
    assert pattern.search(out), f"no {lang} script in: {out!r}"


# 8) help/ask returns grounded answer in English
def test_help_ask_telegram_link():
    _put_profile({"language": "en"})
    r = requests.post(
        f"{BASE_URL}/api/help/ask",
        json={"question": "How do I link Telegram to my account?"},
        headers=AUTH,
        timeout=TIMEOUT,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("lang") == "en"
    ans = data.get("answer", "")
    assert ans, "empty answer"
    lower = ans.lower()
    has_profile = "profile" in lower
    has_grounding = ("connect telegram" in lower) or ("6-character" in lower) or ("6-char" in lower) or ("code" in lower)
    assert has_profile and has_grounding, f"answer not grounded: {ans!r}"


# 9) empty question -> 400
def test_help_ask_empty():
    r = requests.post(f"{BASE_URL}/api/help/ask", json={"question": "  "}, headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 400


# 10) help/ask honors user language (hi)
def test_help_ask_uses_user_language_hindi():
    put = _put_profile({"language": "hi"})
    assert put.status_code == 200, put.text
    try:
        r = requests.post(
            f"{BASE_URL}/api/help/ask",
            json={"question": "How do I link Telegram to my account?"},
            headers=AUTH,
            timeout=TIMEOUT,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("lang") == "hi"
        ans = data.get("answer", "")
        if not DEVANAGARI.search(ans):
            r = requests.post(
                f"{BASE_URL}/api/help/ask",
                json={"question": "How do I link Telegram to my account?"},
                headers=AUTH,
                timeout=TIMEOUT,
            )
            ans = r.json().get("answer", "")
        assert DEVANAGARI.search(ans), f"expected Hindi answer, got: {ans!r}"
    finally:
        _put_profile({"language": "en"})


# 11) PUT /api/auth/profile with language='ml'
def test_profile_language_ml():
    r = _put_profile({"language": "ml"})
    assert r.status_code == 200, r.text
    body = r.json()
    user = body.get("user") if isinstance(body, dict) and "user" in body else body
    assert user.get("language") == "ml", f"got {user}"
    _put_profile({"language": "en"})


# 12) Regression: telegram/status
def test_regression_telegram_status():
    r = requests.get(f"{BASE_URL}/api/telegram/status", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200


# 13) Regression: dashboard/stats
def test_regression_dashboard_stats():
    r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200


# 14) Regression: insights has has_data
def test_regression_insights_has_data():
    r = requests.get(f"{BASE_URL}/api/insights", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200
    assert "has_data" in r.json()


# 15) Regression: profile/phone/verify/status has verify_available
def test_regression_phone_verify_status():
    r = requests.get(f"{BASE_URL}/api/profile/phone/verify/status", headers=AUTH, timeout=TIMEOUT)
    assert r.status_code == 200
    assert "verify_available" in r.json()
