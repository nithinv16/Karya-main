"""Iteration 13 tests: signed file URLs, reports router extraction, quick WhatsApp send."""
import io
import os
import sys
import time

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fall back to frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

TOKEN = "test_session_karya1"
HDR = {"Authorization": f"Bearer {TOKEN}"}


sys.path.insert(0, "/app/backend")
from server import build_signed_file_url, sign_file_path, BACKEND_PUBLIC_URL  # noqa: E402


# ---- helpers ----
def _upload_file(name="sig-test.txt", content=b"hello karya signed url"):
    files = {"file": (name, io.BytesIO(content), "text/plain")}
    r = requests.post(f"{BASE_URL}/api/files/upload", headers=HDR, files=files, timeout=30)
    assert r.status_code == 200, r.text
    return r.json(), content


# ---- Signed URLs ----
class TestSignedFileURLs:
    def test_signed_url_no_auth_returns_bytes(self):
        rec, content = _upload_file()
        url = build_signed_file_url(rec["path"], BACKEND_PUBLIC_URL or BASE_URL)
        # bare requests -- no auth header
        r = requests.get(url, timeout=15)
        assert r.status_code == 200, r.text
        assert r.content == content

    def test_tampered_signature_403(self):
        rec, _ = _upload_file()
        url = build_signed_file_url(rec["path"], BACKEND_PUBLIC_URL or BASE_URL)
        # flip last char of sig
        parts = url.split("sig=")
        sig, rest = parts[1].split("&", 1)
        bad = sig[:-1] + ("0" if sig[-1] != "0" else "1")
        tampered = f"{parts[0]}sig={bad}&{rest}"
        r = requests.get(tampered, timeout=15)
        assert r.status_code == 403
        assert "Invalid or expired signature" in r.text

    def test_expired_signature_403(self):
        rec, _ = _upload_file()
        exp = int(time.time()) - 60
        sig = sign_file_path(rec["path"], exp)
        base = (BACKEND_PUBLIC_URL or BASE_URL).rstrip("/")
        r = requests.get(f"{base}/api/files/{rec['path']}?sig={sig}&exp={exp}", timeout=15)
        assert r.status_code == 403

    def test_bearer_still_works_for_owner(self):
        rec, content = _upload_file()
        base = (BACKEND_PUBLIC_URL or BASE_URL).rstrip("/")
        r = requests.get(f"{base}/api/files/{rec['path']}", headers=HDR, timeout=15)
        assert r.status_code == 200
        assert r.content == content


# ---- Reports router regressions ----
class TestReportsRouter:
    @classmethod
    def setup_class(cls):
        # Create a report to work with (minimal notes-only, no photos)
        body = {
            "project_id": "proj-quick-1",
            "location": "MG Road",
            "notes_text": "Foundation work continued; 8 workers on site; slab curing ongoing.",
            "photo_ids": [],
            "whatsapp_send": False,
        }
        r = requests.post(f"{BASE_URL}/api/reports/generate", headers=HDR, json=body, timeout=60)
        assert r.status_code == 200, r.text
        cls.report = r.json()
        assert "id" in cls.report
        assert "content" in cls.report
        assert cls.report["project_id"] == "proj-quick-1"

    def test_list_reports_contains_new(self):
        r = requests.get(f"{BASE_URL}/api/reports", headers=HDR, timeout=15)
        assert r.status_code == 200
        ids = [x["id"] for x in r.json()]
        assert self.report["id"] in ids

    def test_get_report_by_id(self):
        r = requests.get(f"{BASE_URL}/api/reports/{self.report['id']}", headers=HDR, timeout=15)
        assert r.status_code == 200
        assert r.json()["id"] == self.report["id"]

    def test_whatsapp_send_no_recipients_400(self):
        # audience empty + no extras => no recipients => 400
        r = requests.post(
            f"{BASE_URL}/api/reports/{self.report['id']}/whatsapp",
            headers=HDR, json={"audience": {}, "extra_numbers": []}, timeout=15,
        )
        assert r.status_code == 400

    def test_whatsapp_send_client_twilio_not_configured(self):
        r = requests.post(
            f"{BASE_URL}/api/reports/{self.report['id']}/whatsapp",
            headers=HDR, json={"audience": {"client": True}, "extra_numbers": []}, timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["sent"] == 0 and data["failed"] == 0
        assert any("Twilio not configured" in e for e in data["errors"])
        assert data["recipients"] and data["recipients"][0].startswith("whatsapp:")

    def test_quick_send_endpoint(self):
        r = requests.post(
            f"{BASE_URL}/api/reports/{self.report['id']}/whatsapp/quick",
            headers=HDR, timeout=20,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["sent"] == 0 and data["failed"] == 0
        assert any("Twilio not configured" in e for e in data["errors"])
        # should dedupe: project client_phone + user default_client_phone (both distinct)
        assert len(data["recipients"]) >= 1
        for n in data["recipients"]:
            assert n.startswith("whatsapp:+")

    def test_quick_send_no_numbers_400(self):
        # Create a report with no project (so no client_phone) — but the test user has default_client_phone
        # so we temporarily unset it via a separate report path: use a project without client_phone
        # Insert a bare project
        import pymongo
        import os as _os
        mongo = pymongo.MongoClient(_os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
        db = mongo[_os.environ.get("DB_NAME", "test_database")]
        db.projects.update_one(
            {"id": "proj-nophone-1"},
            {"$set": {"id": "proj-nophone-1", "owner_id": "test-user-karya1",
                      "name": "NoPhone", "client": "X", "location": "L",
                      "budget": 0, "created_at": "2026-01-01T00:00:00Z"}},
            upsert=True,
        )
        # Temporarily clear default_client_phone
        db.users.update_one({"user_id": "test-user-karya1"}, {"$unset": {"default_client_phone": ""}})
        try:
            body = {"project_id": "proj-nophone-1", "location": "L",
                    "notes_text": "test", "photo_ids": [], "whatsapp_send": False}
            r = requests.post(f"{BASE_URL}/api/reports/generate", headers=HDR, json=body, timeout=60)
            assert r.status_code == 200
            rid = r.json()["id"]
            r2 = requests.post(f"{BASE_URL}/api/reports/{rid}/whatsapp/quick", headers=HDR, timeout=15)
            assert r2.status_code == 400
            assert "Set a client WhatsApp" in r2.text
        finally:
            # restore
            db.users.update_one({"user_id": "test-user-karya1"},
                                {"$set": {"default_client_phone": "+919888812345"}})

    def test_delete_report(self):
        r = requests.delete(f"{BASE_URL}/api/reports/{self.report['id']}", headers=HDR, timeout=15)
        assert r.status_code == 200
        r2 = requests.get(f"{BASE_URL}/api/reports/{self.report['id']}", headers=HDR, timeout=15)
        assert r2.status_code == 404


# ---- Basic auth regression ----
def test_auth_me():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=HDR, timeout=10)
    assert r.status_code == 200
    assert r.json()["user_id"] == "test-user-karya1"
