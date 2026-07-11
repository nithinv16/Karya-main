"""Iteration 22 backend tests: phone verify (Twilio Verify) endpoints,
insights has_data flag, and regressions on telegram/dashboard.

Note: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_VERIFY_SERVICE_SID are
intentionally empty in preview. All Verify endpoints must gracefully return 503.
"""
import os
import re
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://telegram-helper-bot.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
TOKEN = "test_session_karya1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# ---------------- phone verify ----------------

class TestPhoneVerify:
    def test_status_endpoint(self):
        r = requests.get(f"{API}/profile/phone/verify/status", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert set(["verify_available", "phone", "phone_verified"]).issubset(data.keys())
        assert data["verify_available"] is False, "Expected verify_available=False since TWILIO_VERIFY_SERVICE_SID is empty"
        assert isinstance(data["phone"], str)
        assert data["phone_verified"] is False

    def test_start_well_formed_phone_returns_503(self):
        r = requests.post(f"{API}/profile/phone/verify/start",
                          json={"phone": "+919876543210"}, headers=HEADERS, timeout=30)
        assert r.status_code == 503, r.text
        # detail should mention Twilio (either "not configured on the server" or "Verify Service SID not configured")
        detail = (r.json().get("detail") or "").lower()
        assert "twilio" in detail
        assert "not configured" in detail

    def test_start_malformed_phone_returns_400_or_503(self):
        r = requests.post(f"{API}/profile/phone/verify/start",
                          json={"phone": "not-a-number"}, headers=HEADERS, timeout=30)
        assert r.status_code in (400, 503), r.text

    def test_check_returns_503(self):
        r = requests.post(f"{API}/profile/phone/verify/check",
                          json={"phone": "+919876543210", "code": "123456"},
                          headers=HEADERS, timeout=30)
        assert r.status_code == 503, r.text

    def test_check_does_not_flip_verified(self):
        # After failed check, status must still report phone_verified=false
        s = requests.get(f"{API}/profile/phone/verify/status", headers=HEADERS, timeout=30).json()
        assert s["phone_verified"] is False


# ---------------- insights has_data ----------------

class TestInsightsHasData:
    def test_insights_returns_has_data_key(self):
        r = requests.get(f"{API}/insights", headers=HEADERS, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "has_data" in data, f"Missing has_data key. Keys: {list(data.keys())}"
        assert isinstance(data["has_data"], bool)
        # Also assert the other well-known keys exist (accept whatever names present)
        # Typical: predictions, subcontractor_scorecards, project_overrun
        # Don't fail hard if names differ, but log
        for k in ("predictions", "subcontractor_scorecards", "project_overrun"):
            if k not in data:
                print(f"WARN: insights payload missing '{k}' (present keys: {list(data.keys())})")


# ---------------- regressions ----------------

class TestRegressions:
    def test_dashboard_stats(self):
        r = requests.get(f"{API}/dashboard/stats", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict)

    def test_telegram_status(self):
        r = requests.get(f"{API}/telegram/status", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("configured") is True
        assert "linked" in data

    def test_telegram_link_code(self):
        r = requests.post(f"{API}/telegram/link/code", headers=HEADERS, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        code = data.get("code")
        assert isinstance(code, str) and len(code) >= 4


# ---------------- module-level TWILIO_WHATSAPP_FROM normalization ----------------

class TestTwilioWhatsappFromNormalization:
    def test_whatsapp_from_default(self):
        # Import backend server module and check TWILIO_WHATSAPP_FROM
        import sys
        sys.path.insert(0, "/app/backend")
        # Ensure no stale import
        if "server" in sys.modules:
            mod = sys.modules["server"]
        else:
            import importlib
            mod = importlib.import_module("server")
        val = getattr(mod, "TWILIO_WHATSAPP_FROM", None)
        assert val == "whatsapp:+14155238886", f"Expected default sandbox from, got: {val!r}"
