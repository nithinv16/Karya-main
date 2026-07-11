"""
Iteration 26 — Cost Trends & Budget vs Actual (new /api/cost-trends endpoint
+ project_id on expenses).
"""
import os
import time
import pytest
import requests

BASE = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "http://localhost:8001"
TOKEN = "test_session_karya1"
H = {"Authorization": f"Bearer {TOKEN}"}


# ---- basic auth / shape ----------------------------------------------------

def test_cost_trends_requires_auth():
    r = requests.get(f"{BASE}/api/cost-trends")
    assert r.status_code == 401


def test_cost_trends_default_shape():
    r = requests.get(f"{BASE}/api/cost-trends", headers=H)
    assert r.status_code == 200, r.text
    data = r.json()
    for key in ("period", "project_id", "buckets", "projects", "overall", "currency", "has_data"):
        assert key in data, f"missing {key}"
    assert data["period"] == "month"
    assert data["currency"] == "INR"
    assert isinstance(data["buckets"], list)
    assert isinstance(data["projects"], list)
    overall = data["overall"]
    for k in ("budget", "actual", "unassigned", "percent"):
        assert k in overall


def test_bucket_row_structure():
    r = requests.get(f"{BASE}/api/cost-trends", headers=H).json()
    assert len(r["buckets"]) > 0, "expected seed data"
    b = r["buckets"][0]
    for k in ("key", "label", "expenses", "labour", "subs", "total"):
        assert k in b
    # total should equal sum of streams
    assert abs(b["total"] - (b["expenses"] + b["labour"] + b["subs"])) < 0.01


def test_project_row_structure_and_math():
    r = requests.get(f"{BASE}/api/cost-trends", headers=H).json()
    assert len(r["projects"]) >= 2
    for p in r["projects"]:
        for k in ("id", "name", "budget", "actual", "remaining", "percent",
                  "expenses", "labour", "subs", "status"):
            assert k in p, f"project row missing {k}"
        # actual == expenses + labour + subs
        assert abs(p["actual"] - (p["expenses"] + p["labour"] + p["subs"])) < 0.01
        if p["budget"] > 0:
            # percent math
            assert abs(p["percent"] - round((p["actual"] / p["budget"]) * 100, 1)) < 0.2
            # status thresholds
            if p["percent"] > 100:
                assert p["status"] == "over"
            elif p["percent"] >= 80:
                assert p["status"] == "warn"
            else:
                assert p["status"] == "ok"


# ---- seed values (matches main-agent seed) ---------------------------------

def test_site_a_monthly_seed_values():
    """Per review request: Site A monthly buckets Oct/Nov/Dec 2025."""
    projects = requests.get(f"{BASE}/api/projects", headers=H).json()
    site_a = next(p for p in projects if p["name"].startswith("Site A"))
    r = requests.get(f"{BASE}/api/cost-trends?project_id={site_a['id']}", headers=H).json()
    by_key = {b["key"]: b for b in r["buckets"]}
    # Oct 2025: expenses 12000 + labour 8000
    if "2025-10" in by_key:
        b = by_key["2025-10"]
        assert b["expenses"] == 12000.0
        assert b["labour"] == 8000.0
    # Nov 2025
    if "2025-11" in by_key:
        b = by_key["2025-11"]
        assert b["expenses"] == 30000.0
        assert b["labour"] == 8000.0
        assert b["subs"] == 40000.0


# ---- period selectors ------------------------------------------------------

def test_period_quarter():
    r = requests.get(f"{BASE}/api/cost-trends?period=quarter", headers=H).json()
    assert r["period"] == "quarter"
    for b in r["buckets"]:
        assert "-Q" in b["key"]


def test_period_week():
    r = requests.get(f"{BASE}/api/cost-trends?period=week", headers=H).json()
    assert r["period"] == "week"
    for b in r["buckets"]:
        assert "-W" in b["key"]


def test_period_year():
    r = requests.get(f"{BASE}/api/cost-trends?period=year", headers=H).json()
    assert r["period"] == "year"
    for b in r["buckets"]:
        # e.g. "2025" or "2026"
        assert b["key"].isdigit() and len(b["key"]) == 4


def test_period_invalid_defaults_to_month():
    r = requests.get(f"{BASE}/api/cost-trends?period=garbage", headers=H).json()
    assert r["period"] == "month"


# ---- project filter --------------------------------------------------------

def test_project_id_filter_restricts_buckets():
    projects = requests.get(f"{BASE}/api/projects", headers=H).json()
    site_a = next(p for p in projects if p["name"].startswith("Site A"))
    r_all = requests.get(f"{BASE}/api/cost-trends", headers=H).json()
    r_a = requests.get(f"{BASE}/api/cost-trends?project_id={site_a['id']}", headers=H).json()
    # Filtered totals should be <= unfiltered totals
    total_all = sum(b["total"] for b in r_all["buckets"])
    total_a = sum(b["total"] for b in r_a["buckets"])
    assert total_a <= total_all + 0.01
    # Filtered actual should equal Site A's project row actual
    site_a_row = next(p for p in r_all["projects"] if p["name"].startswith("Site A"))
    assert abs(total_a - site_a_row["actual"]) < 0.01


# ---- unassigned bucket -----------------------------------------------------

def test_unassigned_expense_flows_to_overall_unassigned():
    """Create an expense with no project_id, verify overall.unassigned grows."""
    before = requests.get(f"{BASE}/api/cost-trends", headers=H).json()["overall"]["unassigned"]

    body = {
        "vendor": "TEST_unassigned_vendor",
        "amount": 777.0,
        "category": "other",
        "summary": "TEST unassigned expense",
        "date": "2025-11-15",
    }
    r = requests.post(f"{BASE}/api/expenses", headers=H, json=body)
    assert r.status_code == 200, r.text
    created = r.json()
    assert created.get("project_id") in (None, "")
    exp_id = created["id"]

    after = requests.get(f"{BASE}/api/cost-trends", headers=H).json()["overall"]["unassigned"]
    assert abs((after - before) - 777.0) < 0.01, f"before={before} after={after}"

    # cleanup
    requests.delete(f"{BASE}/api/expenses/{exp_id}", headers=H)


# ---- create expense with project_id ---------------------------------------

def test_create_expense_with_project_id_and_verify_persistence():
    projects = requests.get(f"{BASE}/api/projects", headers=H).json()
    site_b = next(p for p in projects if p["name"].startswith("Site B"))

    body = {
        "vendor": "TEST_project_scoped",
        "amount": 1234.56,
        "category": "materials",
        "summary": "TEST project-scoped expense",
        "date": "2025-11-20",
        "project_id": site_b["id"],
    }
    r = requests.post(f"{BASE}/api/expenses", headers=H, json=body)
    assert r.status_code == 200
    created = r.json()
    assert created["project_id"] == site_b["id"]
    exp_id = created["id"]

    # verify persistence via list
    items = requests.get(f"{BASE}/api/expenses", headers=H).json()["items"]
    assert any(x["id"] == exp_id and x.get("project_id") == site_b["id"] for x in items)

    # verify cost-trends attributes it to Site B
    r_b = requests.get(f"{BASE}/api/cost-trends?project_id={site_b['id']}", headers=H).json()
    site_b_row = next(p for p in r_b["projects"] if p["id"] == site_b["id"])
    assert site_b_row["expenses"] >= 1234.56

    # DELETE still works after project_id set
    d = requests.delete(f"{BASE}/api/expenses/{exp_id}", headers=H)
    assert d.status_code == 200
    # verify removed
    items2 = requests.get(f"{BASE}/api/expenses", headers=H).json()["items"]
    assert not any(x["id"] == exp_id for x in items2)


# ---- warn / over status transitions ---------------------------------------

def test_warn_and_over_status_via_tiny_budget_project():
    """Create a tiny-budget project, seed spend to push it past 100%."""
    # Create tiny-budget project
    pr = requests.post(f"{BASE}/api/projects", headers=H, json={
        "name": "TEST_tiny_budget",
        "location": "TEST",
        "client": "TEST",
        "budget": 1000,
    })
    assert pr.status_code in (200, 201), pr.text
    project = pr.json()
    pid = project["id"]

    exp_ids = []
    try:
        # First push it into 'warn' range (~85%)
        r = requests.post(f"{BASE}/api/expenses", headers=H, json={
            "vendor": "TEST_warn", "amount": 850,
            "category": "materials", "date": "2025-12-05",
            "project_id": pid,
        })
        exp_ids.append(r.json()["id"])

        row = next(p for p in requests.get(
            f"{BASE}/api/cost-trends", headers=H).json()["projects"] if p["id"] == pid)
        assert row["status"] == "warn", f"got status={row['status']} percent={row['percent']}"

        # Push it 'over' (> 100%)
        r = requests.post(f"{BASE}/api/expenses", headers=H, json={
            "vendor": "TEST_over", "amount": 500,
            "category": "materials", "date": "2025-12-06",
            "project_id": pid,
        })
        exp_ids.append(r.json()["id"])

        row = next(p for p in requests.get(
            f"{BASE}/api/cost-trends", headers=H).json()["projects"] if p["id"] == pid)
        assert row["status"] == "over"
        assert row["percent"] > 100

    finally:
        for eid in exp_ids:
            requests.delete(f"{BASE}/api/expenses/{eid}", headers=H)
        requests.delete(f"{BASE}/api/projects/{pid}", headers=H)


# ---- overall totals math --------------------------------------------------

def test_overall_totals_consistency():
    r = requests.get(f"{BASE}/api/cost-trends", headers=H).json()
    sum_projects = sum(p["actual"] for p in r["projects"])
    # overall.actual == sum of project actuals (unassigned is separate)
    assert abs(r["overall"]["actual"] - sum_projects) < 0.01
