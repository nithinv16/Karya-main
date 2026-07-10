"""Iteration 14: Profile page + PUT /api/auth/profile regression."""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://voice-to-docs-6.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_karya1"
HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


def _get_me():
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=HEADERS, timeout=15)
    assert r.status_code == 200, r.text
    return r.json()


def test_auth_me_ok():
    u = _get_me()
    assert u["user_id"] == "test-user-karya1"
    assert u["email"]


def test_profile_route_unauthenticated_401():
    r = requests.put(f"{BASE_URL}/api/auth/profile", json={"name": "x", "phone": "y"}, timeout=15)
    assert r.status_code in (401, 403)


def test_profile_update_sets_complete_true():
    payload = {
        "name": "QA Karya",
        "phone": "+919999912345",
        "company_name": "Karya QA Co",
        "role": "Contractor",
        "default_client_phone": "+919888812345",
        "address": "Mumbai, MH",
    }
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["name"] == "QA Karya"
    assert data["phone"] == "+919999912345"
    assert data["company_name"] == "Karya QA Co"
    assert data["role"] == "Contractor"
    assert data["default_client_phone"] == "+919888812345"
    assert data["address"] == "Mumbai, MH"
    assert data["profile_complete"] is True
    # GET /auth/me must reflect changes (persistence)
    me = _get_me()
    assert me["name"] == "QA Karya"
    assert me["profile_complete"] is True


def test_profile_update_missing_phone_marks_incomplete():
    payload = {"name": "QA Karya", "phone": "", "company_name": "Karya QA Co",
               "role": "Contractor", "default_client_phone": "", "address": ""}
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=payload, timeout=15)
    assert r.status_code == 200, r.text
    assert r.json()["profile_complete"] is False
    # reset to complete for downstream/UI tests
    reset = {"name": "QA Karya", "phone": "+919999912345",
             "company_name": "Karya QA Co", "role": "Contractor",
             "default_client_phone": "+919888812345", "address": "Mumbai, MH"}
    r2 = requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS, json=reset, timeout=15)
    assert r2.status_code == 200
    assert r2.json()["profile_complete"] is True


def test_profile_response_no_mongo_id():
    r = requests.put(f"{BASE_URL}/api/auth/profile", headers=HEADERS,
                     json={"name": "QA Karya", "phone": "+919999912345",
                           "company_name": "Karya QA Co", "role": "Contractor",
                           "default_client_phone": "+919888812345", "address": "Mumbai, MH"},
                     timeout=15)
    assert "_id" not in r.json()


# Regression - previously-passing endpoints
@pytest.mark.parametrize("path", [
    "/api/auth/me",
    "/api/projects",
    "/api/workers",
    "/api/reports",
    "/api/subcontractors",
])
def test_regression_endpoints(path):
    r = requests.get(f"{BASE_URL}{path}", headers=HEADERS, timeout=20)
    assert r.status_code == 200, f"{path} -> {r.status_code} {r.text[:200]}"
