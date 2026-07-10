"""Iteration 16 - Phase 1 bug fixes verification:
  (a) Projects CRUD (GET-one/PUT/DELETE) with worker unassign cascade.
  (b) Worker ledger split 'paid' out of 'earned' - includes new key 'paid'.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
TOKEN = "test_session_karya1"
H = {"Authorization": f"Bearer {TOKEN}"}
JH = {**H, "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def ctx():
    return {}


# ==================== PROJECTS CRUD ====================
class TestProjectsCRUD:
    def test_create_project(self, ctx):
        payload = {
            "name": "TEST_ProjectCRUD_16",
            "location": "Bengaluru",
            "client": "ACME Realty",
            "client_phone": "+919000012345",
            "budget": 2500000,
        }
        r = requests.post(f"{BASE_URL}/api/projects", headers=JH, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["name"] == payload["name"]
        assert p["client"] == "ACME Realty"
        assert p["budget"] == 2500000
        assert "id" in p
        ctx["pid"] = p["id"]

    def test_list_sorted_newest_first(self, ctx):
        # create a second project to check sort order
        r = requests.post(f"{BASE_URL}/api/projects", headers=JH,
                          json={"name": "TEST_ProjectCRUD_16_second", "location": "Chennai"}, timeout=15)
        assert r.status_code == 200
        ctx["pid2"] = r.json()["id"]

        r = requests.get(f"{BASE_URL}/api/projects", headers=H, timeout=15)
        assert r.status_code == 200
        projects = r.json()
        # find both test projects and check order
        ids_in_order = [p["id"] for p in projects if p["name"].startswith("TEST_ProjectCRUD_16")]
        # second (newer) should appear before first
        assert ids_in_order.index(ctx["pid2"]) < ids_in_order.index(ctx["pid"])

    def test_get_one_with_worker_count(self, ctx):
        # attach 2 workers to pid
        wids = []
        for name in ("TEST_Wrk1_16", "TEST_Wrk2_16"):
            r = requests.post(f"{BASE_URL}/api/workers", headers=JH,
                              json={"name": name, "role": "Mason", "rate": 800,
                                    "rate_type": "daily", "project_id": ctx["pid"]}, timeout=15)
            assert r.status_code == 200
            wids.append(r.json()["id"])
        ctx["worker_ids"] = wids

        r = requests.get(f"{BASE_URL}/api/projects/{ctx['pid']}", headers=H, timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["id"] == ctx["pid"]
        assert p["worker_count"] == 2, f"expected 2 workers, got {p.get('worker_count')}"
        assert p["name"] == "TEST_ProjectCRUD_16"

    def test_get_one_wrong_id_404(self):
        r = requests.get(f"{BASE_URL}/api/projects/not-a-real-id", headers=H, timeout=15)
        assert r.status_code == 404

    def test_update_project(self, ctx):
        payload = {
            "name": "TEST_ProjectCRUD_16_UPDATED",
            "location": "Bengaluru North",
            "client": "ACME Realty Ltd",
            "client_phone": "+919000099999",
            "budget": 3000000,
        }
        r = requests.put(f"{BASE_URL}/api/projects/{ctx['pid']}", headers=JH, json=payload, timeout=15)
        assert r.status_code == 200, r.text
        p = r.json()
        assert p["name"] == payload["name"]
        assert p["budget"] == 3000000
        assert p["client_phone"] == "+919000099999"

        # GET should reflect update
        r2 = requests.get(f"{BASE_URL}/api/projects/{ctx['pid']}", headers=H, timeout=15)
        assert r2.json()["name"] == payload["name"]
        assert r2.json()["budget"] == 3000000

    def test_update_wrong_id_404(self):
        r = requests.put(f"{BASE_URL}/api/projects/wrong-id", headers=JH,
                         json={"name": "x"}, timeout=15)
        assert r.status_code == 404

    def test_delete_unassigns_workers_but_keeps_them(self, ctx):
        r = requests.delete(f"{BASE_URL}/api/projects/{ctx['pid']}", headers=H, timeout=15)
        assert r.status_code == 200
        assert r.json().get("deleted") is True

        # project gone
        r2 = requests.get(f"{BASE_URL}/api/projects/{ctx['pid']}", headers=H, timeout=15)
        assert r2.status_code == 404

        # workers still exist but have project_id = null
        r3 = requests.get(f"{BASE_URL}/api/workers", headers=H, timeout=15)
        assert r3.status_code == 200
        all_workers = r3.json()
        for wid in ctx["worker_ids"]:
            w = next((x for x in all_workers if x["id"] == wid), None)
            assert w is not None, f"worker {wid} was deleted along with project (should NOT be)"
            assert w["project_id"] is None, f"worker {wid} still assigned to deleted project"

    def test_delete_wrong_id_404(self):
        r = requests.delete(f"{BASE_URL}/api/projects/does-not-exist", headers=H, timeout=15)
        assert r.status_code == 404


# ==================== LEDGER CALC ====================
class TestLedgerCalc:
    def test_ledger_paid_split_and_balance(self, ctx):
        # Create fresh worker
        r = requests.post(f"{BASE_URL}/api/workers", headers=JH,
                          json={"name": "TEST_LedgerWkr_16", "role": "Mason",
                                "rate": 1000, "rate_type": "daily"}, timeout=15)
        assert r.status_code == 200
        wid = r.json()["id"]
        ctx["ledger_wid"] = wid

        # transactions as per spec
        for typ, amt in [("wage", 10000), ("advance", 2000), ("payment", 5000),
                         ("deduction", 500), ("bonus", 1000), ("food", 200)]:
            r = requests.post(f"{BASE_URL}/api/transactions", headers=JH,
                              json={"worker_id": wid, "type": typ, "amount": amt}, timeout=15)
            assert r.status_code == 200, f"{typ}: {r.text}"

        r = requests.get(f"{BASE_URL}/api/workers/{wid}/ledger", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()

        # 'paid' must be in response (new key)
        assert "paid" in d, f"'paid' missing from ledger response. keys={list(d.keys())}"

        # earned = wage + bonus = 11000 (payment must NOT be here)
        assert d["earned"] == 11000, f"earned={d['earned']} (expected 11000; payment leak?)"
        assert d["advances"] == 2000
        assert d["paid"] == 5000
        assert d["deductions"] == 700  # 500 + 200 food
        assert d["balance"] == 3300  # 11000 - 2000 - 700 - 5000

    def test_cleanup_ledger_worker(self, ctx):
        if "ledger_wid" in ctx:
            requests.delete(f"{BASE_URL}/api/workers/{ctx['ledger_wid']}", headers=H, timeout=15)


# ==================== CLEANUP ====================
@pytest.fixture(scope="module", autouse=True)
def cleanup(ctx):
    yield
    # cleanup unassigned workers left after project delete cascade
    for wid in ctx.get("worker_ids", []):
        requests.delete(f"{BASE_URL}/api/workers/{wid}", headers=H, timeout=15)
    # cleanup second project (never deleted in tests)
    if "pid2" in ctx:
        requests.delete(f"{BASE_URL}/api/projects/{ctx['pid2']}", headers=H, timeout=15)
