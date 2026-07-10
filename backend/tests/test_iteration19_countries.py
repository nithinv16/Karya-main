"""
Iteration 19 — Phase 4: UAE (AE) support + India (IN) parity.

Covers:
- GET /api/config/countries (IN + AE keys, currency, categories, rate types)
- PUT /api/auth/profile country handling + first-time compliance seeding
- Country-aware AI penalty (INR + Indian statute for IN; AED + MOHRE/WPS for AE)
- POST /api/feed/fetch tags region per country (network-tolerant)
- Regression: /workers/{id}/ledger 5-field summary
"""
import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timedelta, timezone
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://karya-setup.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "karya_database")


# -------------------- helpers / fixtures --------------------

@pytest.fixture(scope="module")
def mongo():
    client = MongoClient(MONGO_URL)
    db = client[DB_NAME]
    yield db
    client.close()


def _make_test_user(mongo, country_hint: str) -> tuple[str, str]:
    """Insert an incomplete-profile user + session directly into Mongo.
    Returns (user_id, session_token)."""
    uid = f"TEST19_user_{country_hint}_{uuid.uuid4().hex[:8]}"
    token = f"TEST19_tok_{uuid.uuid4().hex[:16]}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": f"{uid}@example.com",
        "name": "",
        "phone": "",
        "picture": "",
        "company_name": "",
        "address": "",
        "role": "",
        "default_client_phone": "",
        "profile_complete": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    mongo.user_sessions.insert_one({
        "user_id": uid,
        "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return uid, token


def _cleanup_user(mongo, uid: str):
    mongo.users.delete_many({"user_id": uid})
    mongo.user_sessions.delete_many({"user_id": uid})
    mongo.compliance.delete_many({"owner_id": uid})
    mongo.workers.delete_many({"owner_id": uid})
    mongo.transactions.delete_many({"owner_id": uid})
    mongo.reg_feed.delete_many({"owner_id": uid})


def _hdrs(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# -------------------- 1) countries config --------------------

def test_countries_config_shape():
    r = requests.get(f"{API}/config/countries", timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert set(data.keys()) == {"IN", "AE"}, f"expected exactly IN+AE, got {list(data.keys())}"

    for code, expected_curr in [("IN", "INR"), ("AE", "AED")]:
        m = data[code]
        assert m["name"], f"{code} missing name"
        assert m["currency_code"] == expected_curr
        assert m["currency_symbol"]
        assert m["locale"].startswith("en-")
        assert isinstance(m["rate_types"], list) and len(m["rate_types"]) >= 5
        assert isinstance(m["compliance_categories"], list) and len(m["compliance_categories"]) >= 6

    # UAE must expose hourly + WPS-adjacent categories
    ae = data["AE"]
    assert "hourly" in ae["rate_types"], "AE must include hourly rate type"
    for cat in ("trade_license", "labour_card", "emirates_id", "visa", "wps"):
        assert cat in ae["compliance_categories"], f"AE compliance_categories missing {cat}"
    # AE must have 12 categories per spec
    assert len(ae["compliance_categories"]) == 12, f"AE should have 12 categories, got {len(ae['compliance_categories'])}"

    # IN must have 10 categories per spec
    ind = data["IN"]
    assert len(ind["compliance_categories"]) == 10, f"IN should have 10 categories, got {len(ind['compliance_categories'])}"
    for cat in ("permit", "license", "gst", "labour"):
        assert cat in ind["compliance_categories"]


# -------------------- 2) Profile + first-time compliance seed --------------------

def test_profile_ae_seeds_8_compliance_items(mongo):
    uid, token = _make_test_user(mongo, "AE")
    try:
        r = requests.put(
            f"{API}/auth/profile",
            headers=_hdrs(token),
            json={
                "name": "TEST19 AE Ops",
                "phone": "+971 50 111 2222",
                "address": "PO Box 123, Dubai",
                "company_name": "TEST19 UAE Contracting LLC",
                "role": "Contractor",
                "default_client_phone": "",
                "country": "AE",
                "language": "en",
                "ramadan_mode": True,
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["country"] == "AE"
        assert u["ramadan_mode"] is True
        assert u["profile_complete"] is True

        items = list(mongo.compliance.find({"owner_id": uid}, {"_id": 0}))
        assert len(items) == 8, f"expected 8 AE seed items, got {len(items)}: {[i['title'] for i in items]}"

        titles = [i["title"] for i in items]
        # Spot-check some critical UAE items
        assert any("DED Trade License" in t for t in titles), titles
        assert any("MOHRE" in t and "Labour" in t for t in titles), titles
        assert any("WPS" in t for t in titles), titles
        assert any("Emirates ID" in t for t in titles), titles
        assert any("Civil Defense" in t for t in titles), titles

        cats = {i["category"] for i in items}
        for expected in ("trade_license", "labour_card", "emirates_id", "visa", "wps", "civil_defense"):
            assert expected in cats, f"missing category {expected} in AE seed; got {cats}"
    finally:
        _cleanup_user(mongo, uid)


def test_profile_in_seeds_6_compliance_items(mongo):
    uid, token = _make_test_user(mongo, "IN")
    try:
        r = requests.put(
            f"{API}/auth/profile",
            headers=_hdrs(token),
            json={
                "name": "TEST19 IN Ops",
                "phone": "+91 98765 43210",
                "address": "Bangalore, KA",
                "company_name": "TEST19 India Constructions",
                "role": "Contractor",
                "default_client_phone": "",
                "country": "IN",
                "language": "en",
                "ramadan_mode": False,
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        u = r.json()
        assert u["country"] == "IN"

        items = list(mongo.compliance.find({"owner_id": uid}, {"_id": 0}))
        assert len(items) == 6, f"expected 6 IN seed items, got {len(items)}"
        titles = [i["title"] for i in items]
        assert any("BOCW" in t for t in titles)
        assert any("GST" in t for t in titles)
        assert any("Labour License" in t for t in titles)
    finally:
        _cleanup_user(mongo, uid)


def test_invalid_country_falls_back_to_IN(mongo):
    uid, token = _make_test_user(mongo, "XX")
    try:
        r = requests.put(
            f"{API}/auth/profile",
            headers=_hdrs(token),
            json={
                "name": "TEST19 Fallback",
                "phone": "+91 90000 00000",
                "address": "",
                "company_name": "",
                "role": "",
                "default_client_phone": "",
                "country": "XX",
                "language": "en",
                "ramadan_mode": False,
            },
            timeout=20,
        )
        assert r.status_code == 200, r.text
        assert r.json()["country"] == "IN"
        # Should have seeded IN default (6 items)
        assert mongo.compliance.count_documents({"owner_id": uid}) == 6
    finally:
        _cleanup_user(mongo, uid)


def test_seed_only_runs_once(mongo):
    """Second PUT to /auth/profile must NOT re-seed."""
    uid, token = _make_test_user(mongo, "AE2")
    try:
        base_payload = {
            "name": "TEST19 Reseed",
            "phone": "+971 50 222 3333",
            "address": "Abu Dhabi",
            "company_name": "TEST19 Re-Seed LLC",
            "role": "Contractor",
            "default_client_phone": "",
            "country": "AE",
            "language": "en",
            "ramadan_mode": False,
        }
        r = requests.put(f"{API}/auth/profile", headers=_hdrs(token), json=base_payload, timeout=20)
        assert r.status_code == 200
        count_after_first = mongo.compliance.count_documents({"owner_id": uid})
        assert count_after_first == 8

        # Delete one item so we can detect re-seeding
        one = mongo.compliance.find_one({"owner_id": uid}, {"_id": 1})
        mongo.compliance.delete_one({"_id": one["_id"]})
        assert mongo.compliance.count_documents({"owner_id": uid}) == 7

        # Second PUT — profile_complete already true so it should NOT re-seed
        base_payload["company_name"] = "TEST19 Re-Seed LLC (edited)"
        r2 = requests.put(f"{API}/auth/profile", headers=_hdrs(token), json=base_payload, timeout=20)
        assert r2.status_code == 200
        assert mongo.compliance.count_documents({"owner_id": uid}) == 7, "second PUT must not re-seed"
    finally:
        _cleanup_user(mongo, uid)


# -------------------- 3) AI penalty is country-aware --------------------

def _create_overdue_item(token: str, title: str, category: str, note: str = "") -> str:
    """Create a compliance item and mark it overdue (due_date in past)."""
    past = (datetime.now(timezone.utc) - timedelta(days=10)).date().isoformat()
    r = requests.post(
        f"{API}/compliance",
        headers=_hdrs(token),
        json={
            "title": title,
            "category": category,
            "due_date": past,
            "expiry_date": past,
            "notes": note,
            "project_ids": [],
        },
        timeout=20,
    )
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def test_ae_penalty_uses_AED_and_MOHRE_or_WPS(mongo):
    uid, token = _make_test_user(mongo, "AEpen")
    try:
        # Complete profile as AE (also seeds)
        requests.put(f"{API}/auth/profile", headers=_hdrs(token), json={
            "name": "TEST19 AE Penalty", "phone": "+971 50 000 0000",
            "address": "Dubai", "company_name": "TEST19", "role": "Contractor",
            "default_client_phone": "", "country": "AE", "language": "en", "ramadan_mode": False,
        }, timeout=20)

        cid = _create_overdue_item(
            token,
            "TEST19_UAE WPS overdue",
            "wps",
            "Wage Protection System monthly salary transfer overdue for 40 workers",
        )
        r = requests.post(f"{API}/compliance/{cid}/penalty", headers=_hdrs(token), timeout=90)
        assert r.status_code == 200, r.text
        est = r.json()
        pe = est.get("penalty_estimate") or est
        # Response wraps penalty_estimate on the item — accept either flat or wrapped
        text_blob = str(pe).lower()
        currency = pe.get("currency") if isinstance(pe, dict) else None
        # If wrapped inside the item document:
        if not currency and isinstance(est, dict) and isinstance(est.get("penalty_estimate"), dict):
            pe = est["penalty_estimate"]
            currency = pe.get("currency")
            text_blob = str(pe).lower()

        assert currency == "AED", f"expected AED currency for AE user, got {currency} in {pe}"
        # Basis or breakdown should reference MOHRE or WPS
        assert ("mohre" in text_blob) or ("wps" in text_blob), f"AE penalty should cite MOHRE/WPS, got: {text_blob[:400]}"
        # Amount range should be AED-scale (WPS is thousands, not lakhs). Just sanity check numeric fields exist.
        amt_max = pe.get("amount_max") or pe.get("max") or 0
        assert amt_max > 0, f"expected non-zero penalty amount, got {pe}"
    finally:
        _cleanup_user(mongo, uid)


def test_in_penalty_uses_INR_and_indian_statute(mongo):
    uid, token = _make_test_user(mongo, "INpen")
    try:
        requests.put(f"{API}/auth/profile", headers=_hdrs(token), json={
            "name": "TEST19 IN Penalty", "phone": "+91 90000 00000",
            "address": "Bangalore", "company_name": "TEST19", "role": "Contractor",
            "default_client_phone": "", "country": "IN", "language": "en", "ramadan_mode": False,
        }, timeout=20)

        cid = _create_overdue_item(
            token,
            "TEST19_IN Labour Registration overdue",
            "labour",
            "Contract Labour Registration renewal pending for 45 contract workers",
        )
        r = requests.post(f"{API}/compliance/{cid}/penalty", headers=_hdrs(token), timeout=90)
        assert r.status_code == 200, r.text
        est = r.json()
        pe = est.get("penalty_estimate") if isinstance(est.get("penalty_estimate"), dict) else est
        if not pe.get("currency") and isinstance(est.get("penalty_estimate"), dict):
            pe = est["penalty_estimate"]
        assert pe.get("currency") == "INR", f"expected INR for IN user, got {pe.get('currency')}"
        text_blob = str(pe).lower()
        # Should reference an Indian statute or authority
        indian_terms = ["bocw", "contract labour", "gst", "epf", "esi", "rera", "factories act", "labour ministry", "india"]
        assert any(term in text_blob for term in indian_terms), f"IN penalty should cite an Indian statute; got: {text_blob[:400]}"
    finally:
        _cleanup_user(mongo, uid)


# -------------------- 4) Feed fetch region tagging (network-tolerant) --------------------

def test_feed_fetch_ae_uses_uae_region(mongo):
    uid, token = _make_test_user(mongo, "AEfeed")
    try:
        requests.put(f"{API}/auth/profile", headers=_hdrs(token), json={
            "name": "TEST19 AE Feed", "phone": "+971 50 000 1111",
            "address": "Dubai", "company_name": "TEST19", "role": "Contractor",
            "default_client_phone": "", "country": "AE", "language": "en", "ramadan_mode": False,
        }, timeout=20)

        r = requests.post(f"{API}/feed/fetch", headers=_hdrs(token), timeout=120)
        assert r.status_code == 200, r.text
        added = r.json().get("added", 0)
        if added == 0:
            pytest.skip("Feed fetch returned 0 (network / Google News rate limit) — skipping region assertion")

        # Inspect docs — all TEST19 items must have region == 'United Arab Emirates'
        rows = list(mongo.reg_feed.find({"owner_id": uid}, {"_id": 0, "region": 1, "source": 1}))
        assert rows, "expected feed rows for AE user"
        regions = {row.get("region") for row in rows}
        assert "United Arab Emirates" in regions, f"AE feed region should be 'United Arab Emirates', got {regions}"
    finally:
        _cleanup_user(mongo, uid)


def test_feed_fetch_in_uses_india_region(mongo):
    uid, token = _make_test_user(mongo, "INfeed")
    try:
        requests.put(f"{API}/auth/profile", headers=_hdrs(token), json={
            "name": "TEST19 IN Feed", "phone": "+91 90000 11111",
            "address": "Bangalore", "company_name": "TEST19", "role": "Contractor",
            "default_client_phone": "", "country": "IN", "language": "en", "ramadan_mode": False,
        }, timeout=20)

        r = requests.post(f"{API}/feed/fetch", headers=_hdrs(token), timeout=120)
        assert r.status_code == 200, r.text
        added = r.json().get("added", 0)
        if added == 0:
            pytest.skip("Feed fetch returned 0 — skipping region assertion")

        rows = list(mongo.reg_feed.find({"owner_id": uid}, {"_id": 0, "region": 1}))
        assert rows
        regions = {row.get("region") for row in rows}
        assert "India" in regions, f"IN feed region should be 'India', got {regions}"
    finally:
        _cleanup_user(mongo, uid)


# -------------------- 5) Regression: ledger 5-field summary --------------------

def test_regression_ledger_five_fields(mongo):
    """Use existing seeded qa user."""
    token = "test_session_karya1"
    # Confirm session is live
    r = requests.get(f"{API}/auth/me", headers=_hdrs(token), timeout=15)
    if r.status_code != 200:
        pytest.skip("qa.karya session unavailable")

    # Create a worker + a payment, then check ledger
    rw = requests.post(f"{API}/workers", headers=_hdrs(token), json={
        "name": "TEST19_ledger_worker", "role": "Labour", "phone": "+919000000000",
    }, timeout=15)
    assert rw.status_code in (200, 201), rw.text
    wid = rw.json()["id"]
    try:
        rt = requests.post(f"{API}/transactions", headers=_hdrs(token), json={
            "worker_id": wid, "type": "wage", "amount": 1000, "note": "test"
        }, timeout=15)
        assert rt.status_code in (200, 201), rt.text

        rl = requests.get(f"{API}/workers/{wid}/ledger", headers=_hdrs(token), timeout=15)
        assert rl.status_code == 200, rl.text
        led = rl.json()
        for key in ("earned", "advances", "deductions", "paid", "balance"):
            assert key in led, f"ledger missing '{key}' field: {list(led.keys())}"
        assert led["earned"] >= 1000
    finally:
        # cleanup
        requests.delete(f"{API}/workers/{wid}", headers=_hdrs(token), timeout=15)


def test_regression_compliance_dashboard_shape():
    token = "test_session_karya1"
    r = requests.get(f"{API}/auth/me", headers=_hdrs(token), timeout=15)
    if r.status_code != 200:
        pytest.skip("qa.karya session unavailable")

    r = requests.get(f"{API}/compliance/dashboard", headers=_hdrs(token), timeout=15)
    assert r.status_code == 200, r.text
    d = r.json()
    for key in ("score", "counts", "totals", "penalty_exposure"):
        assert key in d, f"dashboard missing {key}: {d}"
    assert isinstance(d["score"], (int, float))
    assert 0 <= d["score"] <= 100
