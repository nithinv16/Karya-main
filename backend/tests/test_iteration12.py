"""Iteration 12 backend tests: profile onboarding, project client_phone, WhatsApp code paths.

Twilio creds are intentionally empty; we test that the code path executes and returns a
well-shaped failure object with 'Twilio not configured' error.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://karya-setup.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_karya1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# ---------------- auth regression -----------------

def test_session_bogus_returns_401_emergent_404():
    r = requests.post(f"{BASE_URL}/api/auth/session", json={"session_id": "bogus_session_id_zzz"})
    assert r.status_code == 401, r.text
    detail = r.json().get("detail", "")
    assert detail.startswith("emergent_404:"), detail


def test_me_with_bearer():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=HEADERS)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["user_id"] == "test-user-karya1"


# ---------------- profile onboarding -----------------

def test_profile_update_sets_complete_true():
    body = {
        "name": "QA Karya",
        "phone": "+919999912345",
        "address": "1 Test Rd",
        "company_name": "Karya QA",
        "role": "PM",
        "default_client_phone": "+919999900001",
    }
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=body)
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["profile_complete"] is True
    assert j["name"] == "QA Karya"
    assert j["phone"] == "+919999912345"
    assert j["company_name"] == "Karya QA"
    assert j["default_client_phone"] == "+919999900001"

    # GET /me should reflect
    me = requests.get(f"{BASE_URL}/api/auth/me", headers=HEADERS).json()
    assert me["profile_complete"] is True
    assert me["name"] == "QA Karya"
    assert me["default_client_phone"] == "+919999900001"


def test_profile_missing_phone_sets_incomplete():
    body = {"name": "QA Karya", "phone": "", "company_name": "X"}
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=body)
    assert r.status_code == 200
    assert r.json()["profile_complete"] is False
    # restore
    restore = {"name": "QA Karya", "phone": "+919999912345", "company_name": "Karya QA",
               "address": "1 Test Rd", "role": "PM", "default_client_phone": "+919999900001"}
    requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=restore)


def test_profile_missing_name_sets_incomplete():
    body = {"name": "  ", "phone": "+919999912345"}
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=body)
    assert r.status_code == 200
    assert r.json()["profile_complete"] is False
    restore = {"name": "QA Karya", "phone": "+919999912345", "company_name": "Karya QA",
               "address": "1 Test Rd", "role": "PM", "default_client_phone": "+919999900001"}
    requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=restore)


# ---------------- project client_phone -----------------

@pytest.fixture(scope="module")
def project_with_client_phone():
    body = {"name": "TEST_WA_Proj", "client": "TEST Client", "client_phone": "+919812345678",
            "location": "Test Site"}
    r = requests.post(f"{BASE_URL}/api/projects", headers=HEADERS, json=body)
    assert r.status_code in (200, 201), r.text
    proj = r.json()
    assert proj.get("client_phone") == "+919812345678"
    yield proj
    # cleanup
    try:
        requests.delete(f"{BASE_URL}/api/projects/{proj['id']}", headers=HEADERS)
    except Exception:
        pass


def test_project_client_phone_persists(project_with_client_phone):
    r = requests.get(f"{BASE_URL}/api/projects", headers=HEADERS)
    assert r.status_code == 200
    found = [p for p in r.json() if p["id"] == project_with_client_phone["id"]]
    assert found and found[0]["client_phone"] == "+919812345678"


# ---------------- whatsapp code path -----------------

def test_reports_generate_whatsapp_shape():
    body = {
        "project_id": None,
        "notes_text": "Poured slab on level 2. 12 workers on site.",
        "photo_ids": [],
        "whatsapp_send": True,
        "whatsapp_audience": {},
        "whatsapp_extra_numbers": ["+919999912345"],
    }
    r = requests.post(f"{BASE_URL}/api/reports/generate", headers=HEADERS, json=body, timeout=120)
    assert r.status_code == 200, r.text
    doc = r.json()
    wa = doc.get("whatsapp") or {}
    assert wa.get("sent") == 0
    assert wa.get("failed") == 0
    assert "whatsapp:+919999912345" in (wa.get("recipients") or [])
    errs = wa.get("errors") or []
    assert any("Twilio not configured" in e for e in errs), errs


def test_reports_generate_phone_normalizes_10_digit():
    body = {
        "notes_text": "Site cleanup.",
        "photo_ids": [],
        "whatsapp_send": True,
        "whatsapp_extra_numbers": ["9999912345"],
    }
    r = requests.post(f"{BASE_URL}/api/reports/generate", headers=HEADERS, json=body, timeout=120)
    assert r.status_code == 200, r.text
    recipients = r.json().get("whatsapp", {}).get("recipients", [])
    assert "whatsapp:+919999912345" in recipients


def test_send_whatsapp_endpoint_with_project_client(project_with_client_phone):
    # First create a report tied to the project
    body = {
        "project_id": project_with_client_phone["id"],
        "notes_text": "Report for whatsapp test",
        "photo_ids": [],
        "whatsapp_send": False,
    }
    r = requests.post(f"{BASE_URL}/api/reports/generate", headers=HEADERS, json=body, timeout=120)
    assert r.status_code == 200, r.text
    report_id = r.json()["id"]

    send_body = {"audience": {"client": True}, "extra_numbers": ["+919999999999"]}
    r2 = requests.post(f"{BASE_URL}/api/reports/{report_id}/whatsapp", headers=HEADERS, json=send_body)
    assert r2.status_code == 200, r2.text
    j = r2.json()
    assert j["sent"] == 0 and j["failed"] == 0
    recips = j.get("recipients", [])
    assert "whatsapp:+919812345678" in recips
    assert "whatsapp:+919999999999" in recips
    assert any("Twilio not configured" in e for e in j.get("errors", []))


def test_send_whatsapp_no_recipients_returns_400():
    # Generate a report with no project + no audience/extras
    r = requests.post(f"{BASE_URL}/api/reports/generate", headers=HEADERS, json={
        "notes_text": "Empty audience test",
        "photo_ids": [],
        "whatsapp_send": False,
    }, timeout=120)
    assert r.status_code == 200
    report_id = r.json()["id"]
    r2 = requests.post(f"{BASE_URL}/api/reports/{report_id}/whatsapp", headers=HEADERS,
                       json={"audience": {}, "extra_numbers": []})
    assert r2.status_code == 400
    assert "No valid recipient numbers resolved" in r2.text
