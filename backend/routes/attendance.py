"""Attendance router.

Provides `/attendance` CRUD + roster + bulk + headcount endpoints, plus the raw
async helpers `_mark_attendance` and `_headcount_attendance` that the Telegram
`/attendance` command handler in server.py still uses directly.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


ATTENDANCE_STATUSES = ("present", "absent", "half_day")


class AttendanceMarkIn(BaseModel):
    date: str = ""  # YYYY-MM-DD; defaults to today
    worker_id: Optional[str] = None
    project_id: Optional[str] = None
    status: str = "present"  # present|absent|half_day
    note: Optional[str] = None


class AttendanceBulkIn(BaseModel):
    date: str = ""
    project_id: Optional[str] = None
    entries: List[AttendanceMarkIn] = []


class AttendanceHeadcountIn(BaseModel):
    """Quick 'N workers came today' entry for supervisors who don't track by name."""
    date: str = ""
    project_id: Optional[str] = None
    count: int = 1
    note: Optional[str] = None


@dataclass
class Deps:
    db: Any
    get_current_user: Callable
    new_id: Callable[[], str]
    now_iso: Callable[[], str]
    today_str: Callable[[], str]


async def mark_attendance_core(deps: Deps, body: AttendanceMarkIn, user: dict) -> dict:
    """Callable from the Telegram handler AND the HTTP route."""
    if not body.worker_id:
        raise HTTPException(status_code=400, detail="worker_id required")
    if body.status not in ATTENDANCE_STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {ATTENDANCE_STATUSES}")
    uid = user["user_id"]
    worker = await deps.db.workers.find_one({"id": body.worker_id, "owner_id": uid}, {"_id": 0})
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    day = body.date or deps.today_str()
    project_id = body.project_id or worker.get("project_id")
    doc = {
        "id": deps.new_id(), "owner_id": uid, "worker_id": worker["id"],
        "project_id": project_id, "date": day, "status": body.status,
        "count": 1 if body.status != "absent" else 0,
        "note": (body.note or "").strip() or None,
        "created_at": deps.now_iso(),
    }
    existing = await deps.db.attendance.find_one(
        {"owner_id": uid, "worker_id": worker["id"], "date": day},
        {"_id": 0, "id": 1},
    )
    if existing:
        doc["id"] = existing["id"]
        await deps.db.attendance.update_one(
            {"id": existing["id"]},
            {"$set": {k: v for k, v in doc.items() if k not in ("id", "created_at")}},
        )
    else:
        await deps.db.attendance.insert_one({**doc})
    return doc


async def headcount_attendance_core(deps: Deps, body: AttendanceHeadcountIn, user: dict) -> dict:
    if body.count < 0 or body.count > 10000:
        raise HTTPException(status_code=400, detail="count out of range")
    day = body.date or deps.today_str()
    doc = {
        "id": deps.new_id(), "owner_id": user["user_id"], "worker_id": None,
        "project_id": body.project_id or None, "date": day,
        "count": int(body.count), "status": None,
        "note": (body.note or "").strip() or None,
        "created_at": deps.now_iso(),
    }
    await deps.db.attendance.insert_one({**doc})
    return doc


def build_router(deps: Deps) -> APIRouter:
    router = APIRouter()

    @router.get("/attendance")
    async def list_attendance(
        user: dict = Depends(deps.get_current_user),
        date: str = "",
        from_date: str = "",
        to_date: str = "",
        project_id: str = "",
        worker_id: str = "",
        limit: int = 500,
    ):
        q: Dict[str, Any] = {"owner_id": user["user_id"]}
        if date:
            q["date"] = date
        elif from_date or to_date:
            q["date"] = {}
            if from_date:
                q["date"]["$gte"] = from_date
            if to_date:
                q["date"]["$lte"] = to_date
        if project_id:
            q["project_id"] = project_id
        if worker_id:
            q["worker_id"] = worker_id
        try:
            limit_val = int(limit)
        except (TypeError, ValueError):
            limit_val = 500
        limit = max(1, min(limit_val, 2000))
        rows = await deps.db.attendance.find(q, {"_id": 0}).sort("date", -1).limit(limit).to_list(limit)
        return {"items": rows, "count": len(rows)}

    @router.get("/attendance/roster")
    async def attendance_roster(
        user: dict = Depends(deps.get_current_user),
        date: str = "",
        project_id: str = "",
    ):
        day = date or deps.today_str()
        uid = user["user_id"]
        w_query: Dict[str, Any] = {"owner_id": uid}
        if project_id:
            w_query["project_id"] = project_id
        workers = await deps.db.workers.find(w_query, {"_id": 0}).sort("name", 1).to_list(2000)
        att_q: Dict[str, Any] = {"owner_id": uid, "date": day, "worker_id": {"$ne": None}}
        att = await deps.db.attendance.find(att_q, {"_id": 0}).to_list(5000)
        by_worker = {a["worker_id"]: a for a in att}
        roster = []
        for w in workers:
            rec = by_worker.get(w["id"])
            roster.append({
                "worker_id": w["id"],
                "name": w.get("name") or "",
                "role": w.get("role") or "",
                "project_id": w.get("project_id"),
                "rate": w.get("rate") or 0,
                "rate_type": w.get("rate_type") or "daily",
                "status": (rec or {}).get("status") or "unmarked",
                "note": (rec or {}).get("note") or "",
                "attendance_id": (rec or {}).get("id"),
            })
        head_q: Dict[str, Any] = {"owner_id": uid, "date": day, "worker_id": None}
        if project_id:
            head_q["project_id"] = project_id
        headcounts = await deps.db.attendance.find(head_q, {"_id": 0}).to_list(200)
        return {"date": day, "project_id": project_id or None, "roster": roster, "headcounts": headcounts}

    @router.post("/attendance/mark")
    async def mark_attendance(body: AttendanceMarkIn, user: dict = Depends(deps.get_current_user)):
        return await mark_attendance_core(deps, body, user)

    @router.post("/attendance/bulk")
    async def bulk_mark_attendance(body: AttendanceBulkIn, user: dict = Depends(deps.get_current_user)):
        day = body.date or deps.today_str()
        results = []
        for e in body.entries:
            payload = AttendanceMarkIn(
                date=day, worker_id=e.worker_id,
                project_id=e.project_id or body.project_id,
                status=e.status, note=e.note,
            )
            try:
                results.append(await mark_attendance_core(deps, payload, user))
            except HTTPException as exc:
                results.append({"error": exc.detail, "worker_id": e.worker_id})
        return {"date": day, "results": results}

    @router.post("/attendance/headcount")
    async def headcount_attendance(body: AttendanceHeadcountIn, user: dict = Depends(deps.get_current_user)):
        return await headcount_attendance_core(deps, body, user)

    @router.delete("/attendance/{attendance_id}")
    async def delete_attendance(attendance_id: str, user: dict = Depends(deps.get_current_user)):
        r = await deps.db.attendance.delete_one({"id": attendance_id, "owner_id": user["user_id"]})
        if r.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Not found")
        return {"deleted": True}

    return router
