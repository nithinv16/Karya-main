"""Iteration 17 — Phase 2: Export endpoints (PDF/DOCX/XLSX).

Tests all 5 export endpoints:
- GET /api/reports/{id}/export
- GET /api/workers/{id}/ledger/export
- GET /api/payroll/export
- GET /api/insights/export
- GET /api/compliance/export

Verifies file signatures, MIME types, Content-Disposition, invalid format=400,
cross-owner 404, and content sanity (ledger math, xlsx sheet counts).
"""
import os
import io
import uuid
import zipfile
from datetime import datetime

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://karya-setup.preview.emergentagent.com").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "karya_database")

OWNER_ID = "test-user-karya1"
TOKEN = "test_session_karya1"

HDRS = {"Authorization": f"Bearer {TOKEN}"}


# --------------------------------------------------------------------- fixtures

@pytest.fixture(scope="module")
def db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def seed(db):
    """Seed 1 project, 1 worker, txns, 1 daily report, 1 compliance item."""
    tag = f"TEST17_{uuid.uuid4().hex[:6]}"
    project_id = f"proj_{tag}"
    worker_id = f"wrk_{tag}"
    report_id = f"rep_{tag}"
    compliance_id = f"cmp_{tag}"
    other_report_id = f"otherrep_{tag}"

    now = datetime.utcnow().isoformat()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    db.projects.insert_one({
        "id": project_id, "owner_id": OWNER_ID, "name": f"{tag}_Skyline", "location": "Chennai",
        "client": "Acme Ltd", "budget": 5000000, "created_at": now, "status": "active"
    })
    db.workers.insert_one({
        "id": worker_id, "owner_id": OWNER_ID, "name": f"{tag}_Ramesh", "role": "Mason",
        "rate": 800, "rate_type": "day", "project_id": project_id, "created_at": now,
    })
    # Ledger sample: wage 10000 (earn), advance 2000, payment 5000 (paid), deduction 500, bonus 1000 (earn), food 200 (deduct)
    tx_docs = [
        {"id": f"tx1_{tag}", "worker_id": worker_id, "owner_id": OWNER_ID, "type": "wage", "amount": 10000, "date": today, "note": "12 days", "created_at": now},
        {"id": f"tx2_{tag}", "worker_id": worker_id, "owner_id": OWNER_ID, "type": "advance", "amount": 2000, "date": today, "note": "cash advance", "created_at": now},
        {"id": f"tx3_{tag}", "worker_id": worker_id, "owner_id": OWNER_ID, "type": "payment", "amount": 5000, "date": today, "note": "settlement", "created_at": now},
        {"id": f"tx4_{tag}", "worker_id": worker_id, "owner_id": OWNER_ID, "type": "deduction", "amount": 500, "date": today, "note": "damage", "created_at": now},
        {"id": f"tx5_{tag}", "worker_id": worker_id, "owner_id": OWNER_ID, "type": "bonus", "amount": 1000, "date": today, "note": "target", "created_at": now},
        {"id": f"tx6_{tag}", "worker_id": worker_id, "owner_id": OWNER_ID, "type": "food", "amount": 200, "date": today, "note": "canteen", "created_at": now},
    ]
    db.transactions.insert_many(tx_docs)

    db.daily_reports.insert_one({
        "id": report_id, "owner_id": OWNER_ID, "project_id": project_id,
        "project_name": f"{tag}_Skyline", "report_date": today, "location": "Chennai",
        "notes_text": "Foundation on schedule.", "photos": [], "created_at": now,
        "content": {
            "title": "Daily Site Report — Day 12",
            "summary": "Concrete pour on level 2 completed without incidents.",
            "weather": "Clear, 32C",
            "work_completed": ["Level 2 concrete pour", "Column shuttering L3"],
            "manpower": "22 workers on site (18 skilled, 4 helpers)",
            "materials_used": ["Cement 40 bags", "Steel bars 3T"],
            "issues_delays": ["Sand delivery delayed 2h"],
            "safety_observations": ["All PPE in use"],
            "next_steps": ["Start L3 shuttering by tomorrow"],
        },
    })
    # Cross-owner report
    db.daily_reports.insert_one({
        "id": other_report_id, "owner_id": "some-other-user", "project_id": "x",
        "project_name": "Other", "report_date": today,
        "content": {"title": "Other", "summary": "not visible"}, "photos": [], "created_at": now,
    })
    db.compliance.insert_one({
        "id": compliance_id, "owner_id": OWNER_ID, "title": f"{tag}_PF_return",
        "category": "PF", "due_date": today, "status": "pending",
        "notes": "Monthly PF filing.", "created_at": now,
    })

    yield {
        "tag": tag, "project_id": project_id, "worker_id": worker_id,
        "report_id": report_id, "other_report_id": other_report_id,
        "compliance_id": compliance_id, "today": today,
    }

    # cleanup
    db.projects.delete_many({"id": project_id})
    db.workers.delete_many({"id": worker_id})
    db.transactions.delete_many({"id": {"$regex": f"^tx.*_{tag}$"}})
    db.daily_reports.delete_many({"id": {"$in": [report_id, other_report_id]}})
    db.compliance.delete_many({"id": compliance_id})


# --------------------------------------------------------------------- helpers

PDF_SIG = b"%PDF"
DOCX_SIG = b"PK\x03\x04"
XLSX_SIG = b"PK\x03\x04"

MIME = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _check_response(r, fmt, min_size):
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:300]}"
    assert MIME[fmt] in r.headers.get("content-type", ""), f"bad content-type: {r.headers.get('content-type')}"
    cd = r.headers.get("content-disposition", "")
    assert "attachment" in cd.lower() and "filename" in cd.lower(), f"bad content-disposition: {cd}"
    body = r.content
    assert len(body) >= min_size, f"file too small: {len(body)} < {min_size}"
    if fmt == "pdf":
        assert body[:4] == PDF_SIG, f"not a real PDF: {body[:20]!r}"
    else:
        assert body[:4] == DOCX_SIG, f"not a valid zip/docx/xlsx: {body[:20]!r}"
    return body


def _xlsx_sheet_names(body):
    zf = zipfile.ZipFile(io.BytesIO(body))
    wb_xml = zf.read("xl/workbook.xml").decode()
    import re
    return re.findall(r'<sheet[^>]*name="([^"]+)"', wb_xml)


def _xlsx_all_text(body):
    zf = zipfile.ZipFile(io.BytesIO(body))
    txt = ""
    for name in zf.namelist():
        if name.startswith("xl/") and name.endswith(".xml"):
            txt += zf.read(name).decode(errors="ignore")
    return txt


def _docx_text(body):
    zf = zipfile.ZipFile(io.BytesIO(body))
    return zf.read("word/document.xml").decode(errors="ignore")


# --------------------------------------------------------------------- daily report

@pytest.mark.parametrize("fmt,min_size", [("pdf", 500), ("docx", 1000), ("xlsx", 1000)])
def test_daily_report_export_formats(seed, fmt, min_size):
    url = f"{BASE_URL}/api/reports/{seed['report_id']}/export"
    r = requests.get(url, params={"format": fmt}, headers=HDRS, timeout=30)
    body = _check_response(r, fmt, min_size)
    # Verify content contains sections
    if fmt == "docx":
        txt = _docx_text(body)
        for kw in ["Summary", "Work Completed", "Manpower", "Issues", "Safety", "Next Steps", "Attendance"]:
            assert kw.lower() in txt.lower(), f"missing section '{kw}' in docx"
    elif fmt == "xlsx":
        txt = _xlsx_all_text(body)
        for kw in ["Summary", "Manpower", "Attendance"]:
            assert kw.lower() in txt.lower(), f"missing '{kw}' in xlsx"


def test_daily_report_cross_owner_404(seed):
    url = f"{BASE_URL}/api/reports/{seed['other_report_id']}/export"
    r = requests.get(url, params={"format": "pdf"}, headers=HDRS, timeout=15)
    assert r.status_code == 404


def test_daily_report_invalid_format(seed):
    url = f"{BASE_URL}/api/reports/{seed['report_id']}/export"
    r = requests.get(url, params={"format": "txt"}, headers=HDRS, timeout=15)
    assert r.status_code == 400


# --------------------------------------------------------------------- worker ledger

@pytest.mark.parametrize("fmt,min_size", [("pdf", 500), ("docx", 1000), ("xlsx", 1000)])
def test_worker_ledger_export_formats(seed, fmt, min_size):
    url = f"{BASE_URL}/api/workers/{seed['worker_id']}/ledger/export"
    r = requests.get(url, params={"format": fmt}, headers=HDRS, timeout=30)
    body = _check_response(r, fmt, min_size)
    # ledger math: earned=11000, advances=2000, deductions=700, paid=5000, balance=3300
    if fmt == "docx":
        txt = _docx_text(body)
        assert "11,000" in txt, "earned 11,000 missing"
        assert "2,000" in txt, "advances 2,000 missing"
        assert "700" in txt, "deductions 700 missing"
        assert "5,000" in txt, "paid 5,000 missing"
        assert "3,300" in txt, "balance 3,300 missing"
    elif fmt == "xlsx":
        names = _xlsx_sheet_names(body)
        assert "Summary" in names and "Transactions" in names, f"expected Summary+Transactions sheets, got {names}"
        txt = _xlsx_all_text(body)
        for v in ["11,000", "2,000", "700", "5,000", "3,300"]:
            assert v in txt, f"missing {v} in xlsx"


def test_worker_ledger_cross_owner_404():
    url = f"{BASE_URL}/api/workers/nonexistent-worker-id/ledger/export"
    r = requests.get(url, params={"format": "pdf"}, headers=HDRS, timeout=15)
    assert r.status_code == 404


def test_worker_ledger_invalid_format(seed):
    url = f"{BASE_URL}/api/workers/{seed['worker_id']}/ledger/export"
    r = requests.get(url, params={"format": "csv"}, headers=HDRS, timeout=15)
    assert r.status_code == 400


# --------------------------------------------------------------------- payroll

@pytest.mark.parametrize("fmt,min_size", [("pdf", 500), ("docx", 1000), ("xlsx", 1000)])
def test_payroll_settlements_export(seed, fmt, min_size):
    url = f"{BASE_URL}/api/payroll/export"
    r = requests.get(url, params={"format": fmt}, headers=HDRS, timeout=30)
    body = _check_response(r, fmt, min_size)
    if fmt == "xlsx":
        names = _xlsx_sheet_names(body)
        assert "Settlements" in names and "Transactions" in names, f"expected 2 sheets, got {names}"


def test_payroll_invalid_format():
    r = requests.get(f"{BASE_URL}/api/payroll/export", params={"format": "html"}, headers=HDRS, timeout=15)
    assert r.status_code == 400


# --------------------------------------------------------------------- insights

@pytest.mark.parametrize("fmt,min_size", [("pdf", 500), ("docx", 1000), ("xlsx", 1000)])
def test_insights_export(seed, fmt, min_size):
    url = f"{BASE_URL}/api/insights/export"
    r = requests.get(url, params={"format": fmt}, headers=HDRS, timeout=60)
    body = _check_response(r, fmt, min_size)
    if fmt == "xlsx":
        names = _xlsx_sheet_names(body)
        for s in ["Predictions", "Subcontractors", "Project Burn", "AI Briefing"]:
            assert s in names, f"expected sheet '{s}', got {names}"


def test_insights_invalid_format():
    r = requests.get(f"{BASE_URL}/api/insights/export", params={"format": "zip"}, headers=HDRS, timeout=15)
    assert r.status_code == 400


# --------------------------------------------------------------------- compliance

@pytest.mark.parametrize("fmt,min_size", [("pdf", 500), ("docx", 1000), ("xlsx", 1000)])
def test_compliance_export(seed, fmt, min_size):
    url = f"{BASE_URL}/api/compliance/export"
    r = requests.get(url, params={"format": fmt}, headers=HDRS, timeout=30)
    body = _check_response(r, fmt, min_size)
    if fmt == "docx":
        txt = _docx_text(body)
        for col in ["Title", "Category", "Due Date", "Status", "Notes"]:
            assert col in txt, f"column '{col}' missing"
        assert seed["tag"] in txt, "seeded compliance item not present"


def test_compliance_invalid_format():
    r = requests.get(f"{BASE_URL}/api/compliance/export", params={"format": "xml"}, headers=HDRS, timeout=15)
    assert r.status_code == 400


# --------------------------------------------------------------------- unauth

def test_export_requires_auth():
    r = requests.get(f"{BASE_URL}/api/payroll/export", params={"format": "xlsx"}, timeout=15)
    assert r.status_code in (401, 403)
