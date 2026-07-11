"""
Iteration 29 backend tests.

Coverage:
  1) Telegram notification defaults DISABLED
  2) Twilio Verify auto-provisioning (status endpoint + system_config record)
  3) Voice transcribe error paths (empty audio, rate limit)
  4) Expense create with custom slugified category
  5) Web receipt upload (validation + successful image upload + rate limit)
  6) Security headers + CORS allow-list
  7) Payload size guard (413)
  8) SEO surface (robots.txt, sitemap.xml, JSON-LD in index.html)
  9) Regression: /api/expenses shape + /api/cost-trends
"""
import io
import os
import asyncio
import struct
import wave
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or \
    "https://telegram-helper-bot.preview.emergentagent.com"
TOKEN = "test_session_karya1"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s


# ---------------------------------------------------------------- 1. Notification defaults
class TestNotificationDefaults:
    def _reset_prefs(self):
        """Unset the user's notifications so defaults surface on GET."""
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "karya_db_v2")
        async def _go():
            c = AsyncIOMotorClient(mongo_url)
            await c[db_name].users.update_one(
                {"user_id": "test-user-karya1"},
                {"$unset": {"notifications": ""}},
            )
            c.close()
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError()
            loop.run_until_complete(_go())
        except RuntimeError:
            asyncio.run(_go())

    def test_defaults_all_disabled(self, api):
        self._reset_prefs()
        r = api.get(f"{BASE_URL}/api/telegram/notifications")
        assert r.status_code == 200, r.text
        n = r.json()["notifications"]
        assert n["morning_briefing"]["enabled"] is False
        assert n["compliance_alerts"]["enabled"] is False
        assert n["payroll_reminder"]["enabled"] is False


# ---------------------------------------------------------------- 2. Verify auto-provisioning
class TestVerifyAutoProvision:
    def test_status_available(self, api):
        r = api.get(f"{BASE_URL}/api/profile/phone/verify/status")
        assert r.status_code == 200, r.text
        data = r.json()
        # Twilio creds are set; either the auto-provisioned SID is already
        # cached, or (rare) upstream is unreachable — either outcome is ok
        # for this env per test spec.
        assert "verify_available" in data
        assert isinstance(data["verify_available"], bool)

    def test_system_config_has_sid(self):
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "karya_db_v2")
        async def _go():
            c = AsyncIOMotorClient(mongo_url)
            doc = await c[db_name].system_config.find_one({"key": "twilio_verify_sid"})
            c.close()
            return doc
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError()
            doc = loop.run_until_complete(_go())
        except RuntimeError:
            doc = asyncio.run(_go())
        # If Twilio API was reachable at least once, this doc exists.
        # Not fatal if it doesn't (network-flaky env) — record and skip.
        if not doc:
            pytest.skip("verify SID not yet provisioned (Twilio unreachable in this env)")
        assert doc.get("value", "").startswith("VA")


# ---------------------------------------------------------------- 3. Voice transcribe
class TestVoiceTranscribe:
    def test_empty_audio_returns_400(self, api):
        files = {"file": ("clip.webm", b"", "audio/webm")}
        r = api.post(f"{BASE_URL}/api/voice/transcribe", files=files,
                     data={"language": "auto"})
        assert r.status_code == 400, r.text
        assert "Empty audio" in r.text

    def test_rate_limit_kicks_in(self, api):
        # 30/min limit — issue 31 sequential tiny (empty) posts; the 31st
        # should be a 429, regardless of whether individual calls 400.
        seen_429 = False
        for _ in range(31):
            files = {"file": ("clip.webm", b"", "audio/webm")}
            r = api.post(f"{BASE_URL}/api/voice/transcribe", files=files,
                         data={"language": "auto"})
            if r.status_code == 429:
                seen_429 = True
                break
        assert seen_429, "Expected 429 within 31 sequential requests"


# ---------------------------------------------------------------- 4. Custom expense category slugify
class TestCustomExpenseCategory:
    def test_backend_accepts_slugified_category(self, api):
        # Frontend slugifies; backend just accepts. Simulate the payload the
        # frontend would send.
        payload = {
            "vendor": "TEST_CUSTOM_CAT",
            "amount": 123.45,
            "category": "site_accommodation",  # slugified
            "summary": "iter29 test",
        }
        r = api.post(f"{BASE_URL}/api/expenses", json=payload)
        assert r.status_code == 200, r.text
        exp = r.json()
        assert exp["category"] == "site_accommodation"
        eid = exp["id"]
        # List and verify persistence
        lr = api.get(f"{BASE_URL}/api/expenses",
                     params={"q": "TEST_CUSTOM_CAT"})
        assert lr.status_code == 200
        ids = [e["id"] for e in lr.json()["items"]]
        assert eid in ids
        # Cleanup
        api.delete(f"{BASE_URL}/api/expenses/{eid}")


# ---------------------------------------------------------------- 5. Web receipt upload
def _tiny_png() -> bytes:
    # Minimal 1x1 red PNG — used for validation-only tests.
    import base64
    return base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="
    )


def _receipt_png() -> bytes:
    """Larger PNG with text — OpenAI vision accepts this."""
    try:
        from PIL import Image, ImageDraw
    except Exception:  # pragma: no cover
        return _tiny_png()
    import io as _io
    im = Image.new("RGB", (400, 300), "white")
    d = ImageDraw.Draw(im)
    d.text((20, 20), "TEST_ITER29 Cement Depot", fill="black")
    d.text((20, 60), "Date: 2026-01-10", fill="black")
    d.text((20, 100), "50 bags cement  Rs 22500", fill="black")
    d.text((20, 140), "Total: Rs 22500", fill="black")
    buf = _io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


class TestReceiptUpload:
    def test_empty_file_returns_400(self, api):
        files = {"file": ("receipt.png", b"", "image/png")}
        r = api.post(f"{BASE_URL}/api/expenses/upload-receipt", files=files)
        assert r.status_code == 400, r.text

    def test_unsupported_type_returns_415(self, api):
        files = {"file": ("notes.txt", b"just some text", "text/plain")}
        r = api.post(f"{BASE_URL}/api/expenses/upload-receipt", files=files)
        assert r.status_code == 415, r.text

    def test_valid_png_creates_expense_and_knowledge(self, api):
        files = {"file": ("receipt.png", _receipt_png(), "image/png")}
        r = api.post(f"{BASE_URL}/api/expenses/upload-receipt",
                     files=files, timeout=90)
        assert r.status_code == 200, r.text
        body = r.json()
        exp = body.get("expense")
        assert exp and "id" in exp
        assert exp["source"] == "web_upload"
        assert exp.get("attachment") and exp["attachment"].get("path")
        # Verify knowledge entry
        from motor.motor_asyncio import AsyncIOMotorClient
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        db_name = os.environ.get("DB_NAME", "karya_db_v2")
        async def _go():
            c = AsyncIOMotorClient(mongo_url)
            k = await c[db_name].knowledge.find_one(
                {"owner_id": "test-user-karya1", "tags": "receipt",
                 "attachment.path": exp["attachment"]["path"]}
            )
            c.close()
            return k
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError()
            k = loop.run_until_complete(_go())
        except RuntimeError:
            k = asyncio.run(_go())
        assert k is not None, "Expected knowledge entry created for uploaded receipt"
        # Cleanup expense (leave knowledge; harmless)
        api.delete(f"{BASE_URL}/api/expenses/{exp['id']}")

    def test_upload_rate_limit(self, api):
        """The rate-limit check runs BEFORE reading the file, so we can hit it
        without actually invoking the (slow) AI parse by sending unsupported
        types (415) — rate_limit still increments before the type check.
        Actually rate_limit runs before content-type check, so 21 sequential
        415s will still trip the 20/min limit.
        """
        seen_429 = False
        for _ in range(21):
            files = {"file": ("r.txt", b"tiny", "text/plain")}
            r = api.post(f"{BASE_URL}/api/expenses/upload-receipt",
                         files=files, timeout=30)
            if r.status_code == 429:
                seen_429 = True
                break
        assert seen_429, "Expected 429 within 21 sequential uploads"


# ---------------------------------------------------------------- 6. Security headers + CORS
class TestSecurityHeaders:
    REQUIRED = [
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Strict-Transport-Security",
        "Content-Security-Policy",
    ]

    def test_headers_present(self, api):
        r = api.get(f"{BASE_URL}/api/auth/me")
        assert r.status_code == 200, r.text
        for h in self.REQUIRED:
            assert h in r.headers, f"Missing header: {h}. Got: {dict(r.headers)}"
        assert r.headers["X-Content-Type-Options"].lower() == "nosniff"
        assert r.headers["X-Frame-Options"].upper() == "DENY"
        assert "strict-origin-when-cross-origin" in r.headers["Referrer-Policy"].lower()

    def test_cors_via_asgi_app(self):
        """CORS is enforced at the FastAPI middleware level, but the preview
        ingress overrides access-control-allow-origin to '*' for all
        responses. Test the app-level config directly via the ASGI app.
        """
        import sys
        sys.path.insert(0, "/app/backend")
        from starlette.testclient import TestClient
        from server import app
        c = TestClient(app)
        # Evil origin — should NOT be echoed
        r = c.options(
            "/api/auth/me",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
        aco = r.headers.get("access-control-allow-origin", "")
        assert aco != "https://evil.example.com", f"leaked: {aco}"
        assert aco != "*", "wildcard leaked from app"
        # Allowed origin (regex) — must be echoed
        r2 = c.options(
            "/api/auth/me",
            headers={
                "Origin": "https://karyaai.app",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r2.headers.get("access-control-allow-origin") == "https://karyaai.app"


# ---------------------------------------------------------------- 7. Payload size guard
class TestOversizeGuard:
    def test_middleware_returns_413(self):
        """The preview ingress terminates requests with fake Content-Length
        before they reach the backend. Test the middleware in-process."""
        import sys
        sys.path.insert(0, "/app/backend")
        from starlette.testclient import TestClient
        from server import app
        c = TestClient(app)
        r = c.post(
            "/api/expenses",
            content=b"{}",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
                "Content-Length": "99999999",
            },
        )
        assert r.status_code == 413, f"Expected 413, got {r.status_code}: {r.text[:200]}"
        assert "Request body too large" in r.text


# ---------------------------------------------------------------- 8. SEO surface
class TestSEO:
    def test_robots_txt(self):
        r = requests.get(f"{BASE_URL}/robots.txt")
        assert r.status_code == 200, r.status_code
        body = r.text
        assert "User-agent: *" in body
        assert "Allow: /" in body
        assert "karyaai.app" in body  # our content, not platform default

    def test_sitemap_xml(self):
        r = requests.get(f"{BASE_URL}/sitemap.xml")
        assert r.status_code == 200, r.status_code
        # Count URLs
        assert r.text.count("<loc>") >= 7

    def test_index_html_has_jsonld(self):
        r = requests.get(f"{BASE_URL}/")
        assert r.status_code == 200
        assert 'application/ld+json' in r.text


# ---------------------------------------------------------------- 9. Regression
class TestRegression:
    def test_expenses_shape(self, api):
        r = api.get(f"{BASE_URL}/api/expenses")
        assert r.status_code == 200
        data = r.json()
        for k in ("items", "total", "count", "limit", "offset", "currency", "by_category"):
            assert k in data, f"missing key {k}"

    def test_cost_trends(self, api):
        r = api.get(f"{BASE_URL}/api/cost-trends")
        assert r.status_code == 200, r.text
