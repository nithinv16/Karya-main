"""Karya backend API tests - all pillars + new Daily Reports feature.

Uses seeded test session (see /app/memory/test_credentials.md).
Runs sequentially so create->update->verify flows share state via module-scope fixtures.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://telegram-helper-bot.preview.emergentagent.com").rstrip("/")
TOKEN = "test_session_karya1"
H = {"Authorization": f"Bearer {TOKEN}"}
JH = {**H, "Content-Type": "application/json"}
AI_TIMEOUT = 90


@pytest.fixture(scope="module")
def created():
    return {}


# ----------------------------------------------------------- auth
class TestAuth:
    def test_me_ok(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["user_id"] == "test-user-karya1"
        assert d["email"] == "qa.karya@example.com"

    def test_me_unauth(self):
        r = requests.get(f"{BASE_URL}/api/auth/me", timeout=15)
        assert r.status_code == 401

    def test_workers_unauth(self):
        r = requests.get(f"{BASE_URL}/api/workers", timeout=15)
        assert r.status_code == 401


# ----------------------------------------------------------- workforce
class TestWorkforce:
    def test_create_project(self, created):
        r = requests.post(f"{BASE_URL}/api/projects", headers=JH,
                          json={"name": "TEST_Site_A", "location": "Kochi", "budget": 500000}, timeout=15)
        assert r.status_code == 200
        p = r.json()
        assert p["name"] == "TEST_Site_A" and "id" in p
        created["project_id"] = p["id"]

    def test_list_projects_includes(self, created):
        r = requests.get(f"{BASE_URL}/api/projects", headers=H, timeout=15)
        assert r.status_code == 200
        assert any(p["id"] == created["project_id"] for p in r.json())

    def test_create_worker(self, created):
        r = requests.post(f"{BASE_URL}/api/workers", headers=JH,
                          json={"name": "TEST_Suresh", "role": "Mason", "rate": 900,
                                "rate_type": "daily", "project_id": created["project_id"]}, timeout=15)
        assert r.status_code == 200
        w = r.json()
        assert w["name"] == "TEST_Suresh" and w["onboarding"]["id_collected"] is False
        created["worker_id"] = w["id"]

    def test_update_onboarding(self, created):
        payload = {"onboarding": {"id_collected": True, "contract_signed": True,
                                  "induction_done": False, "site_access": True,
                                  "insurance": True, "bank_details": False}}
        r = requests.post(f"{BASE_URL}/api/workers/{created['worker_id']}/onboarding",
                          headers=JH, json=payload, timeout=15)
        assert r.status_code == 200
        assert r.json()["onboarding"]["id_collected"] is True

        # verify persistence
        r2 = requests.get(f"{BASE_URL}/api/workers", headers=H, timeout=15)
        w = next(x for x in r2.json() if x["id"] == created["worker_id"])
        assert w["onboarding"]["contract_signed"] is True
        assert w["onboarding"]["induction_done"] is False


# ----------------------------------------------------------- payroll ledger
class TestPayroll:
    def test_txn_and_ledger(self, created):
        wid = created["worker_id"]
        for t, amt in [("wage", 2700), ("advance", 500), ("deduction", 100), ("food", 50)]:
            r = requests.post(f"{BASE_URL}/api/transactions", headers=JH,
                              json={"worker_id": wid, "type": t, "amount": amt}, timeout=15)
            assert r.status_code == 200, f"{t}: {r.text}"

        r = requests.get(f"{BASE_URL}/api/workers/{wid}/ledger", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert d["earned"] == 2700
        assert d["advances"] == 500
        assert d["deductions"] == 150  # 100 + 50 food
        assert d["balance"] == 2050


# ----------------------------------------------------------- NL command
class TestCommand:
    def test_advance_command(self):
        r = requests.post(f"{BASE_URL}/api/command", headers=JH,
                          json={"text": "Rajesh took an advance of 2000"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        d = r.json()
        assert d["applied"] is True
        assert "2,000" in d["summary"] or "2000" in d["summary"]

    def test_add_worker_command(self):
        r = requests.post(f"{BASE_URL}/api/command", headers=JH,
                          json={"text": "Add worker TEST_Sunil as mason at 950 daily"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["applied"] is True

    def test_attendance_command(self):
        r = requests.post(f"{BASE_URL}/api/command", headers=JH,
                          json={"text": "Ten workers arrived today at Skyline Towers"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["applied"] is True

    def test_gibberish_command(self):
        r = requests.post(f"{BASE_URL}/api/command", headers=JH,
                          json={"text": "asdlkfjq weoiruq qwerty gibberish"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        assert r.json()["applied"] is False


# ----------------------------------------------------------- subcontractors
class TestSubcontractors:
    def test_full_flow(self, created):
        r = requests.post(f"{BASE_URL}/api/subcontractors", headers=JH,
                          json={"name": "TEST_SubCo", "firm": "TSC", "trade": "electrical",
                                "contract_value": 1000000, "retention_percent": 5}, timeout=15)
        assert r.status_code == 200
        sub = r.json()
        sid = sub["id"]
        created["sub_id"] = sid
        assert sub["summary"]["retention_held"] == 50000

        # negative amount => 400
        r = requests.post(f"{BASE_URL}/api/subcontractors/{sid}/transactions", headers=JH,
                          json={"type": "payment", "amount": -100}, timeout=15)
        assert r.status_code == 400

        # extra_work + material + deduction + payment + retention_release
        for t, amt in [("extra_work", 200000), ("material", 50000), ("deduction", 20000),
                       ("payment", 300000), ("retention_release", 10000)]:
            r = requests.post(f"{BASE_URL}/api/subcontractors/{sid}/transactions", headers=JH,
                              json={"type": t, "amount": amt}, timeout=15)
            assert r.status_code == 200, f"{t}: {r.text}"

        r = requests.get(f"{BASE_URL}/api/subcontractors/{sid}", headers=H, timeout=15)
        assert r.status_code == 200
        s = r.json()["summary"]
        assert s["gross"] == 1200000  # 1000000 + 200000
        assert s["retention_held"] == 1200000 * 0.05 - 10000  # 50000
        assert s["net_payable"] == 1200000 - 50000 - 20000 - s["retention_held"]
        assert s["paid"] == 300000
        assert abs(s["pending"] - (s["net_payable"] - 300000)) < 0.01

    def test_delete_cascades(self, created):
        r = requests.delete(f"{BASE_URL}/api/subcontractors/{created['sub_id']}", headers=H, timeout=15)
        assert r.status_code == 200
        r = requests.get(f"{BASE_URL}/api/subcontractors/{created['sub_id']}", headers=H, timeout=15)
        assert r.status_code == 404


# ----------------------------------------------------------- compliance
class TestCompliance:
    def test_create_and_analyze(self, created):
        r = requests.post(f"{BASE_URL}/api/compliance", headers=JH,
                          json={"title": "TEST_BOCW registration renewal", "category": "registration",
                                "due_date": "2026-02-15",
                                "document_text": "Registration under Building and Other Construction Workers Welfare Cess Act needs renewal"},
                          timeout=15)
        assert r.status_code == 200
        cid = r.json()["id"]
        created["compliance_id"] = cid

        r = requests.post(f"{BASE_URL}/api/compliance/{cid}/analyze", headers=H, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        a = r.json()["analysis"]
        for k in ["summary", "what_changed", "who_is_affected", "deadline", "penalties", "actions_required", "risk_level"]:
            assert k in a
        assert isinstance(a["actions_required"], list)


# ----------------------------------------------------------- feed
class TestFeed:
    def test_manual_add(self, created):
        r = requests.post(f"{BASE_URL}/api/feed", headers=JH,
                          json={"title": "TEST_Manual regulation", "source": "manual",
                                "category": "labour", "summary": "Test entry"}, timeout=15)
        assert r.status_code == 200
        created["feed_id_manual"] = r.json()["id"]

    def test_fetch_live(self, created):
        r = requests.post(f"{BASE_URL}/api/feed/fetch", headers=H, timeout=120)
        assert r.status_code == 200
        # may be 0 if all urls already exist, but items should exist in list
        r2 = requests.get(f"{BASE_URL}/api/feed", headers=H, timeout=15)
        items = r2.json()
        verified = [i for i in items if i.get("verified") and i.get("url")]
        assert len(verified) > 0, "no verified feed items"
        created["feed_id"] = verified[0]["id"]

    def test_impact(self, created):
        if "feed_id" not in created:
            pytest.skip("no feed item")
        r = requests.post(f"{BASE_URL}/api/feed/{created['feed_id']}/impact", headers=H, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        imp = r.json()["impact"]
        for k in ["impact_summary", "urgency", "affected_projects", "recommended_actions"]:
            assert k in imp

    def test_track(self, created):
        if "feed_id" not in created:
            pytest.skip("no feed item")
        r = requests.post(f"{BASE_URL}/api/feed/{created['feed_id']}/track", headers=H, timeout=30)
        assert r.status_code == 200
        assert "id" in r.json()

    def test_delete_manual(self, created):
        r = requests.delete(f"{BASE_URL}/api/feed/{created['feed_id_manual']}", headers=H, timeout=15)
        assert r.status_code == 200


# ----------------------------------------------------------- SOPs
class TestSops:
    def test_generate(self):
        r = requests.post(f"{BASE_URL}/api/sops/generate", headers=JH,
                          json={"title": "Concrete pouring", "category": "quality",
                                "raw_input": "M25 concrete pour for ground floor slab. Ensure formwork checked, vibrator ready, curing plan. Workers must wear PPE."},
                          timeout=AI_TIMEOUT)
        assert r.status_code == 200
        c = r.json()["content"]
        for k in ["title", "objective", "steps", "safety_precautions", "inspection_points",
                  "required_tools", "acceptance_criteria", "escalation"]:
            assert k in c
        assert len(c["steps"]) >= 2


# ----------------------------------------------------------- knowledge
class TestKnowledge:
    def test_create_and_ask(self, created):
        r = requests.post(f"{BASE_URL}/api/knowledge", headers=JH,
                          json={"title": "TEST_Best Vendor", "content": "For TMT steel, prefer TATA Tiscon from Kochi depot — reliable delivery in 2 days.",
                                "tags": ["vendor", "steel"]}, timeout=15)
        assert r.status_code == 200
        created["knowledge_id"] = r.json()["id"]

        r = requests.post(f"{BASE_URL}/api/knowledge/ask", headers=JH,
                          json={"question": "Which TMT steel vendor is preferred?"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        assert "TATA" in r.json()["answer"] or "Tiscon" in r.json()["answer"].lower() or "tata" in r.json()["answer"].lower()


# ----------------------------------------------------------- assistant
class TestAssistant:
    def test_ask_ledger(self):
        r = requests.post(f"{BASE_URL}/api/assistant/ask", headers=JH,
                          json={"question": "How much do I owe Rajesh?"}, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        ans = r.json()["answer"]
        assert len(ans) > 5
        assert "Rajesh" in ans or "rajesh" in ans.lower() or "₹" in ans


# ----------------------------------------------------------- dashboard
class TestDashboard:
    def test_stats(self):
        r = requests.get(f"{BASE_URL}/api/dashboard/stats", headers=H, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["workers", "projects", "labour_cost_today", "pending_settlements",
                  "subcontractor_pending", "retention_held", "workers_missing_docs", "compliance_health"]:
            assert k in d["totals"], f"missing {k}"
        assert len(d["trend"]) == 7
        assert "project_spend" in d
        assert "subcontractor_dues" in d


# ----------------------------------------------------------- notifications
class TestNotifications:
    def test_list_and_dismiss(self):
        r = requests.get(f"{BASE_URL}/api/notifications", headers=H, timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert "unread" in d and "notifications" in d
        # find a worker-insurance or compliance alert to dismiss
        target = next((n for n in d["notifications"] if not n["dismissed"]), None)
        if not target:
            pytest.skip("no non-dismissed notifications")
        key = target["key"]
        r2 = requests.post(f"{BASE_URL}/api/notifications/dismiss", headers=JH,
                           json={"key": key}, timeout=15)
        assert r2.status_code == 200
        r3 = requests.get(f"{BASE_URL}/api/notifications", headers=H, timeout=15)
        found = next((n for n in r3.json()["notifications"] if n["key"] == key), None)
        if found:
            assert found["dismissed"] is True


# ----------------------------------------------------------- insights
class TestInsights:
    def test_insights(self):
        r = requests.get(f"{BASE_URL}/api/insights", headers=H, timeout=30)
        assert r.status_code == 200
        d = r.json()
        for k in ["labour_shortage", "cost_overrun", "delay_risk"]:
            assert k in d["predictions"]
            for kk in ["level", "metric", "detail"]:
                assert kk in d["predictions"][k]
        assert isinstance(d["subcontractor_scorecards"], list)
        assert isinstance(d["project_overrun"], list)

    def test_briefing(self):
        r = requests.get(f"{BASE_URL}/api/insights/briefing", headers=H, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        assert "ai_summary" in r.json()


# ----------------------------------------------------------- files
class TestFiles:
    def test_upload_txt(self, created):
        files = {"file": ("test.txt", b"Hello Karya compliance document.", "text/plain")}
        r = requests.post(f"{BASE_URL}/api/files/upload", headers=H, files=files, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["extracted_text"].startswith("Hello Karya")
        assert d["path"] and d["filename"] == "test.txt"
        created["file_path"] = d["path"]

    def test_download_file_bearer(self, created):
        r = requests.get(f"{BASE_URL}/api/files/{created['file_path']}", headers=H, timeout=15)
        assert r.status_code == 200
        assert b"Hello Karya" in r.content

    def test_download_unauth(self, created):
        r = requests.get(f"{BASE_URL}/api/files/{created['file_path']}", timeout=15)
        assert r.status_code == 401

    def test_upload_image(self, created):
        with open("/tmp/site_photo.jpg", "rb") as f:
            files = {"file": ("site.jpg", f, "image/jpeg")}
            r = requests.post(f"{BASE_URL}/api/files/upload", headers=H, files=files, timeout=60)
        assert r.status_code == 200
        created["photo_id"] = r.json()["id"]


# ----------------------------------------------------------- voice
class TestVoice:
    def test_transcribe(self):
        with open("/tmp/test.wav", "rb") as f:
            files = {"file": ("test.wav", f, "audio/wav")}
            data = {"language": "en"}
            r = requests.post(f"{BASE_URL}/api/voice/transcribe", headers=H, files=files, data=data, timeout=AI_TIMEOUT)
        assert r.status_code == 200
        assert "text" in r.json()


# ----------------------------------------------------------- daily reports (NEW)
class TestDailyReports:
    def test_validation_empty(self):
        r = requests.post(f"{BASE_URL}/api/reports/generate", headers=JH,
                          json={"location": "site", "notes_text": "", "photo_ids": []}, timeout=15)
        assert r.status_code == 400

    def test_generate(self, created):
        assert "photo_id" in created, "photo not uploaded"
        payload = {
            "location": "Skyline Towers, Kochi",
            "notes_text": "Poured M25 concrete for 3rd floor slab. 12 workers on site. Some formwork delay in morning.",
            "photo_ids": [created["photo_id"]],
            "report_date": "2026-01-15",
        }
        r = requests.post(f"{BASE_URL}/api/reports/generate", headers=JH, json=payload, timeout=180)
        assert r.status_code == 200, r.text
        d = r.json()
        c = d["content"]
        for k in ["title", "summary", "work_completed", "manpower", "materials_used",
                  "issues_delays", "safety_observations", "next_steps"]:
            assert k in c, f"missing {k}"
        assert isinstance(c["work_completed"], list)
        created["report_id"] = d["id"]

    def test_list_reports(self, created):
        r = requests.get(f"{BASE_URL}/api/reports", headers=H, timeout=15)
        assert r.status_code == 200
        assert any(rep["id"] == created["report_id"] for rep in r.json())

    def test_delete_report(self, created):
        r = requests.delete(f"{BASE_URL}/api/reports/{created['report_id']}", headers=H, timeout=15)
        assert r.status_code == 200


# ----------------------------------------------------------- cleanup
@pytest.fixture(scope="module", autouse=True)
def cleanup(created):
    yield
    if "worker_id" in created:
        requests.delete(f"{BASE_URL}/api/workers/{created['worker_id']}", headers=H, timeout=15)
    if "compliance_id" in created:
        # no delete endpoint; leave test items (they have TEST_ prefix)
        pass
    if "knowledge_id" in created:
        pass  # no delete endpoint
