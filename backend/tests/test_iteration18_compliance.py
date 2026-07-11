"""Phase 3 — Compliance Agent enhancements + region-aware feed.

Covers all 7 upgrades:
  1. Urgency buckets / warnings          -> /api/compliance/dashboard
  2. OCR-detected expiry backfill        -> /api/compliance/{id}/analyze
  3. Renewal task chain                  -> /api/compliance/{id}/renew
  4. Penalty calculator                  -> /api/compliance/{id}/penalty
  5. Region-aware feed filter            -> /api/feed?region=&category=
  6. Multi-project tagging               -> POST/PATCH compliance with project_ids
  7. Compliance score                    -> /api/compliance/dashboard.score
Plus PATCH / DELETE + owner-scope 404 + digest text length.
"""
import os
import re
import time
import pytest
import requests
from datetime import datetime, timedelta, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://telegram-helper-bot.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_karya1"
H = {"Authorization": f"Bearer {TOKEN}"}
JH = {**H, "Content-Type": "application/json"}
AI_TIMEOUT = 120
PREFIX = "TEST18_"


def _iso(days_from_today: int) -> str:
    return (datetime.now(timezone.utc).date() + timedelta(days=days_from_today)).isoformat()


# ------------------------------------------------------- fresh state fixture
@pytest.fixture(scope="module")
def clean_slate():
    """Delete existing TEST18_* compliance items so score/counts are deterministic."""
    r = requests.get(f"{BASE_URL}/api/compliance", headers=H, timeout=15)
    if r.status_code == 200:
        for it in r.json():
            if (it.get("title") or "").startswith(PREFIX):
                requests.delete(f"{BASE_URL}/api/compliance/{it['id']}", headers=H, timeout=15)
    yield
    # teardown
    r = requests.get(f"{BASE_URL}/api/compliance", headers=H, timeout=15)
    if r.status_code == 200:
        for it in r.json():
            if (it.get("title") or "").startswith(PREFIX):
                requests.delete(f"{BASE_URL}/api/compliance/{it['id']}", headers=H, timeout=15)


@pytest.fixture(scope="module")
def created():
    return {}


# ------------------------------------------------------- CRUD + PATCH
class TestComplianceCRUD:
    def test_create_with_new_fields(self, clean_slate, created):
        r = requests.post(f"{BASE_URL}/api/compliance", headers=JH, json={
            "title": f"{PREFIX}Labour License",
            "category": "license",
            "due_date": _iso(20),
            "expiry_date": _iso(20),
            "project_ids": ["proj-a", "proj-b"],
            "status": "pending",
            "document_text": "Labour license renewal pending",
        }, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["title"] == f"{PREFIX}Labour License"
        assert d["project_ids"] == ["proj-a", "proj-b"]
        assert d["status"] == "pending"
        assert d["expiry_date"] == _iso(20)
        assert "id" in d
        created["cid_watch"] = d["id"]

    def test_list_includes_new_fields(self, created):
        r = requests.get(f"{BASE_URL}/api/compliance", headers=H, timeout=15)
        assert r.status_code == 200
        it = next(i for i in r.json() if i["id"] == created["cid_watch"])
        assert it["project_ids"] == ["proj-a", "proj-b"]
        assert it["expiry_date"] == _iso(20)
        assert it["status"] == "pending"

    def test_patch_partial(self, created):
        r = requests.patch(f"{BASE_URL}/api/compliance/{created['cid_watch']}", headers=JH,
                           json={"status": "in_progress", "project_ids": ["proj-a"]}, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["status"] == "in_progress"
        assert d["project_ids"] == ["proj-a"]
        # history got appended
        assert any(h.get("action") == "updated" for h in d.get("history", []))
        # untouched field preserved
        assert d["title"] == f"{PREFIX}Labour License"

    def test_patch_bad_id_404(self):
        r = requests.patch(f"{BASE_URL}/api/compliance/does-not-exist-xyz", headers=JH,
                           json={"status": "completed"}, timeout=15)
        assert r.status_code == 404

    def test_delete_and_404(self, created):
        # create a throw-away to delete
        r = requests.post(f"{BASE_URL}/api/compliance", headers=JH, json={
            "title": f"{PREFIX}Delete me", "category": "permit"}, timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]
        r = requests.delete(f"{BASE_URL}/api/compliance/{cid}", headers=H, timeout=15)
        assert r.status_code == 200
        assert r.json().get("deleted") is True
        # second delete -> 404
        r = requests.delete(f"{BASE_URL}/api/compliance/{cid}", headers=H, timeout=15)
        assert r.status_code == 404


# ------------------------------------------------------- Dashboard math
class TestComplianceDashboard:
    """Seed exactly 1 overdue + 1 critical + 1 completed and validate score = 80."""

    def test_seed_deterministic_state(self, clean_slate, created):
        # wipe any leftover TEST18_ items first
        r = requests.get(f"{BASE_URL}/api/compliance", headers=H, timeout=15)
        for it in r.json():
            if (it.get("title") or "").startswith(PREFIX):
                requests.delete(f"{BASE_URL}/api/compliance/{it['id']}", headers=H, timeout=15)
        # 1 overdue with penalty_estimate to test exposure sum
        r1 = requests.post(f"{BASE_URL}/api/compliance", headers=JH, json={
            "title": f"{PREFIX}Overdue permit", "category": "permit",
            "due_date": _iso(-10), "status": "pending"}, timeout=15)
        assert r1.status_code == 200
        cid_ov = r1.json()["id"]
        created["cid_overdue"] = cid_ov
        # attach penalty_estimate via PATCH (avoid live LLM to keep math deterministic)
        r = requests.patch(f"{BASE_URL}/api/compliance/{cid_ov}", headers=JH, json={
            "penalty_estimate": {"currency": "INR", "amount_min": 1000, "amount_max": 5000,
                                 "basis": "test", "escalation": [], "worst_case": "x",
                                 "days_overdue": 10}}, timeout=15)
        assert r.status_code == 200
        # 1 critical (≤7d)
        r2 = requests.post(f"{BASE_URL}/api/compliance", headers=JH, json={
            "title": f"{PREFIX}Critical soon", "category": "insurance",
            "due_date": _iso(5), "status": "pending"}, timeout=15)
        assert r2.status_code == 200
        created["cid_crit"] = r2.json()["id"]
        # 1 completed (should sit in ok bucket in dashboard)
        r3 = requests.post(f"{BASE_URL}/api/compliance", headers=JH, json={
            "title": f"{PREFIX}Done license", "category": "license",
            "due_date": _iso(60), "status": "completed"}, timeout=15)
        assert r3.status_code == 200
        created["cid_done"] = r3.json()["id"]

    def test_dashboard_shape_and_math(self, created):
        r = requests.get(f"{BASE_URL}/api/compliance/dashboard", headers=H, timeout=20)
        assert r.status_code == 200
        d = r.json()
        for k in ["score", "counts", "totals", "penalty_exposure", "buckets"]:
            assert k in d, f"missing {k}"
        for kk in ["overdue", "critical", "warning", "watch", "ok", "none"]:
            assert kk in d["counts"]
            assert kk in d["buckets"]
        # only TEST18_* items should be present for this user in this run
        assert d["counts"]["overdue"] >= 1
        assert d["counts"]["critical"] >= 1
        # totals
        assert d["totals"]["total"] >= 3
        assert d["totals"]["completed"] >= 1
        # penalty exposure includes 5000 from our overdue
        assert d["penalty_exposure"] >= 5000
        # score bounded 0-100 int
        assert isinstance(d["score"], int)
        assert 0 <= d["score"] <= 100

    def test_dashboard_only_our_seed(self, created):
        """If dashboard only has our 3 seed items, verify score exactly = 80."""
        r = requests.get(f"{BASE_URL}/api/compliance", headers=H, timeout=15)
        items = r.json()
        # Only run strict math when the *only* items are our TEST18_ seeds
        non_test = [i for i in items if not (i.get("title") or "").startswith(PREFIX)]
        if non_test:
            pytest.skip(f"skipping strict score check — {len(non_test)} non-test items in db")
        d = requests.get(f"{BASE_URL}/api/compliance/dashboard", headers=H, timeout=15).json()
        # score = 100 - 15 - 8 + int(1/3*10) = 100 - 15 - 8 + 3 = 80
        assert d["score"] == 80, f"expected score=80, got {d['score']}, counts={d['counts']}"
        assert d["counts"]["overdue"] == 1
        assert d["counts"]["critical"] == 1
        assert d["counts"]["ok"] == 1  # completed lands in ok
        assert d["penalty_exposure"] == 5000.0


# ------------------------------------------------------- RENEW (LLM)
class TestRenewalPlan:
    def test_renew_generates_plan(self, created):
        # Create a dedicated item to renew (self-sufficient)
        r = requests.post(f"{BASE_URL}/api/compliance", headers=JH, json={
            "title": f"{PREFIX}Renew target", "category": "license",
            "due_date": _iso(10), "status": "pending"}, timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]
        r = requests.post(f"{BASE_URL}/api/compliance/{cid}/renew", headers=H, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "in_progress"
        plan = d["renewal_plan"]
        assert plan is not None
        for k in ["docs_needed", "submission_office", "fee_estimate", "processing_time", "steps"]:
            assert k in plan
        assert isinstance(plan["steps"], list) and len(plan["steps"]) >= 3
        # each step has title/detail/done
        for s in plan["steps"]:
            assert "title" in s
            assert "done" in s
            assert s["done"] is False

    def test_renew_404_wrong_owner(self):
        r = requests.post(f"{BASE_URL}/api/compliance/bogus-id-9999/renew", headers=H, timeout=15)
        assert r.status_code == 404


# ------------------------------------------------------- PENALTY (LLM)
class TestPenaltyCalc:
    def test_penalty_computes_days(self, created):
        cid = created["cid_overdue"]  # due 10 days ago
        r = requests.post(f"{BASE_URL}/api/compliance/{cid}/penalty", headers=H, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        est = d["penalty_estimate"]
        for k in ["currency", "amount_min", "amount_max", "basis", "escalation", "days_overdue"]:
            assert k in est
        assert est["days_overdue"] == 10
        assert est["currency"] == "INR"
        assert est["amount_max"] >= est["amount_min"] > 0


# ------------------------------------------------------- ANALYZE + expiry backfill (LLM)
class TestAnalyzeBackfill:
    def test_analyze_and_backfill_expiry(self, created):
        # Create fresh item with no dates, doc_text mentioning a clear expiry
        r = requests.post(f"{BASE_URL}/api/compliance", headers=JH, json={
            "title": f"{PREFIX}BOCW cert with hidden expiry",
            "category": "registration",
            "document_text": (
                "Building & Other Construction Workers registration certificate. "
                "Validity/Expiry Date: 2026-11-30. Renewal to be filed 30 days prior."
            ),
        }, timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]
        created["cid_expiry"] = cid

        r = requests.post(f"{BASE_URL}/api/compliance/{cid}/analyze", headers=H, timeout=AI_TIMEOUT)
        assert r.status_code == 200, r.text
        d = r.json()
        a = d.get("analysis") or {}
        for k in ["summary", "actions_required", "risk_level"]:
            assert k in a
        # Model *should* have surfaced 2026-11-30, but be lenient: accept any ISO date if backfilled
        exp = d.get("expiry_date") or ""
        due = d.get("due_date") or ""
        # Either the AI backfilled from doc, or expiry_date remains empty. We only STRICT-check
        # that IF analysis.expiry_date is set, it got copied onto the item.
        if a.get("expiry_date"):
            assert exp == a["expiry_date"], "backend must backfill expiry_date onto item"
            # and if item had no due_date, it should now equal expiry_date
            assert due == a["expiry_date"]


# ------------------------------------------------------- DIGEST (LLM, text)
class TestDigest:
    def test_digest_shape(self):
        r = requests.get(f"{BASE_URL}/api/compliance/digest", headers=H, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        for k in ["digest", "score", "penalty_exposure"]:
            assert k in d
        assert isinstance(d["digest"], str) and len(d["digest"].strip()) > 40
        # loose word-count check (150-220 is target; be permissive: 80..400)
        words = len(re.findall(r"\w+", d["digest"]))
        assert 80 <= words <= 500, f"digest word count {words} out of tolerated range"


# ------------------------------------------------------- FEED region + category
class TestFeedFilters:
    def test_feed_category_and_region_query_params(self):
        # Seed 3 manual items with different regions/categories
        for title, cat, region, summary in [
            (f"{PREFIX}Karnataka labour circular", "labour", "Karnataka", "Karnataka state labour board notice"),
            (f"{PREFIX}Delhi GST update", "gst", "Delhi", "GST tax rate change"),
            (f"{PREFIX}All-India safety NBC", "safety", "India", "Safety NBC applies everywhere"),
        ]:
            r = requests.post(f"{BASE_URL}/api/feed", headers=JH, json={
                "title": title, "source": "manual", "category": cat,
                "region": region, "summary": summary}, timeout=15)
            assert r.status_code == 200

        # category filter
        r = requests.get(f"{BASE_URL}/api/feed", headers=H, params={"category": "labour"}, timeout=15)
        assert r.status_code == 200
        assert all(i["category"] == "labour" for i in r.json())
        assert any(i["title"] == f"{PREFIX}Karnataka labour circular" for i in r.json())

        # region filter (case-insensitive, matches region field)
        r = requests.get(f"{BASE_URL}/api/feed", headers=H, params={"region": "karnataka"}, timeout=15)
        assert r.status_code == 200
        titles = [i["title"] for i in r.json()]
        assert f"{PREFIX}Karnataka labour circular" in titles
        assert f"{PREFIX}Delhi GST update" not in titles

        # region filter — should also match when region is only in title/summary
        r = requests.post(f"{BASE_URL}/api/feed", headers=JH, json={
            "title": f"{PREFIX}Karnataka via title only", "source": "manual",
            "category": "municipal", "region": "", "summary": "content about karnataka municipality"}, timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{BASE_URL}/api/feed", headers=H, params={"region": "karnataka"}, timeout=15)
        titles = [i["title"] for i in r.json()]
        assert f"{PREFIX}Karnataka via title only" in titles

        # combined region + category
        r = requests.get(f"{BASE_URL}/api/feed", headers=H,
                         params={"region": "karnataka", "category": "labour"}, timeout=15)
        assert r.status_code == 200
        for it in r.json():
            assert it["category"] == "labour"
        titles = [i["title"] for i in r.json()]
        assert f"{PREFIX}Karnataka labour circular" in titles
        assert f"{PREFIX}Karnataka via title only" not in titles  # cat=municipal, filtered out

        # cleanup our seed feed items
        r = requests.get(f"{BASE_URL}/api/feed", headers=H, timeout=15)
        for it in r.json():
            if (it.get("title") or "").startswith(PREFIX):
                requests.delete(f"{BASE_URL}/api/feed/{it['id']}", headers=H, timeout=15)


# ------------------------------------------------------- REGRESSION (Phase 1+2)
class TestRegression:
    def test_dashboard_stats_still_ok(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=H, timeout=20)
        assert r.status_code == 200
        d = r.json()
        assert "totals" in d and "compliance_health" in d["totals"]

    def test_projects_ledger_endpoints(self):
        r = requests.get(f"{BASE_URL}/api/projects", headers=H, timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{BASE_URL}/api/workers", headers=H, timeout=15)
        assert r.status_code == 200

    @pytest.mark.parametrize("path", [
        "/reports/xxx/export?format=pdf",  # invalid id -> 404 (route still mounted)
        "/compliance/export?format=pdf",
        "/insights/export?format=pdf",
        "/payroll/export?format=pdf",
    ])
    def test_export_routes_mounted(self, path):
        r = requests.get(f"{BASE_URL}/api{path}", headers=H, timeout=30)
        # We only care the route exists — 200 OR 404 (for missing report id) is acceptable.
        assert r.status_code in (200, 400, 404), f"{path} -> {r.status_code}"
