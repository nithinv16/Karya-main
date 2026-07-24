"""Cost trends router.

Aggregates cost across three streams (expenses, labour wages, subcontractor
payments) into a time-bucketed view + budget vs actual per project. Extracted
from server.py.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends


LABOUR_COST_TYPES = ["wage", "bonus"]
SUB_COST_TYPES = ["payment", "advance", "extra_work"]


def _bucket_key(date_str: str, period: str) -> Optional[tuple[str, str]]:
    if not date_str or len(date_str) < 7:
        return None
    try:
        dt = datetime.fromisoformat(date_str[:10])
    except Exception:
        return None
    if period == "week":
        iso_year, iso_week, _ = dt.isocalendar()
        return f"{iso_year}-W{iso_week:02d}", f"W{iso_week} {iso_year}"
    if period == "quarter":
        q = (dt.month - 1) // 3 + 1
        return f"{dt.year}-Q{q}", f"Q{q} {dt.year}"
    if period == "year":
        return f"{dt.year}", f"{dt.year}"
    return f"{dt.year}-{dt.month:02d}", dt.strftime("%b %Y")


@dataclass
class Deps:
    db: Any
    get_current_user: Callable
    country_ctx: Callable[[dict], dict]


def build_router(deps: Deps) -> APIRouter:
    router = APIRouter()

    @router.get("/cost-trends")
    async def cost_trends(
        period: str = "month",
        project_id: str = "",
        user: dict = Depends(deps.get_current_user),
    ):
        period = period if period in ("week", "month", "quarter", "year") else "month"
        uid = user["user_id"]
        ctx = deps.country_ctx(user)

        workers = await deps.db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(5000)
        worker_project = {w["id"]: w.get("project_id") for w in workers}
        subs = await deps.db.subcontractors.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
        sub_project = {s["id"]: s.get("project_id") for s in subs}
        projects = await deps.db.projects.find({"owner_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(500)

        pid_filter = project_id or None

        exp_query: Dict[str, Any] = {"owner_id": uid}
        if pid_filter:
            exp_query["project_id"] = pid_filter
        expenses = await deps.db.expenses.find(exp_query, {"_id": 0}).to_list(5000)

        txn_query: Dict[str, Any] = {"owner_id": uid, "type": {"$in": LABOUR_COST_TYPES}}
        txns = await deps.db.transactions.find(txn_query, {"_id": 0}).to_list(20000)
        if pid_filter:
            txns = [t for t in txns if worker_project.get(t.get("worker_id")) == pid_filter]

        sub_query: Dict[str, Any] = {"owner_id": uid, "type": {"$in": SUB_COST_TYPES}}
        sub_txns = await deps.db.sub_transactions.find(sub_query, {"_id": 0}).to_list(20000)
        if pid_filter:
            sub_txns = [t for t in sub_txns if sub_project.get(t.get("sub_id")) == pid_filter]

        buckets: Dict[str, Dict[str, Any]] = {}

        def _add(bkt: Optional[tuple[str, str]], field: str, amt: float):
            if not bkt:
                return
            key, label = bkt
            b = buckets.setdefault(key, {"key": key, "label": label, "expenses": 0.0, "labour": 0.0, "subs": 0.0})
            b[field] += float(amt or 0)

        for e in expenses:
            _add(_bucket_key(e.get("date") or "", period), "expenses", e.get("amount") or 0)
        for t in txns:
            _add(_bucket_key(t.get("date") or "", period), "labour", t.get("amount") or 0)
        for t in sub_txns:
            _add(_bucket_key(t.get("date") or "", period), "subs", t.get("amount") or 0)

        ordered = sorted(buckets.values(), key=lambda b: b["key"])
        for b in ordered:
            b["expenses"] = round(b["expenses"], 2)
            b["labour"] = round(b["labour"], 2)
            b["subs"] = round(b["subs"], 2)
            b["total"] = round(b["expenses"] + b["labour"] + b["subs"], 2)

        # Budget vs Actual per project (all-time).
        all_expenses = await deps.db.expenses.find({"owner_id": uid}, {"_id": 0}).to_list(5000)
        all_txns_labour = await deps.db.transactions.find(
            {"owner_id": uid, "type": {"$in": LABOUR_COST_TYPES}}, {"_id": 0}
        ).to_list(20000)
        all_sub_txns = await deps.db.sub_transactions.find(
            {"owner_id": uid, "type": {"$in": SUB_COST_TYPES}}, {"_id": 0}
        ).to_list(20000)

        per_project: Dict[str, Dict[str, float]] = {p["id"]: {"expenses": 0.0, "labour": 0.0, "subs": 0.0} for p in projects}
        unassigned = {"expenses": 0.0, "labour": 0.0, "subs": 0.0}

        def _accum(pid: Optional[str], field: str, amt: float):
            if pid and pid in per_project:
                per_project[pid][field] += float(amt or 0)
            else:
                unassigned[field] += float(amt or 0)

        for e in all_expenses:
            _accum(e.get("project_id"), "expenses", e.get("amount") or 0)
        for t in all_txns_labour:
            _accum(worker_project.get(t.get("worker_id")), "labour", t.get("amount") or 0)
        for t in all_sub_txns:
            _accum(sub_project.get(t.get("sub_id")), "subs", t.get("amount") or 0)

        project_rows: List[dict] = []
        total_budget = 0.0
        total_actual = 0.0
        for p in projects:
            pid = p["id"]
            parts = per_project[pid]
            actual = round(parts["expenses"] + parts["labour"] + parts["subs"], 2)
            budget = float(p.get("budget") or 0)
            raw_pct = (actual / budget) * 100 if budget > 0 else 0
            pct = round(raw_pct, 1)
            remaining = round(budget - actual, 2) if budget > 0 else 0
            status = "no_budget" if budget <= 0 else ("over" if raw_pct > 100 else ("warn" if raw_pct >= 80 else "ok"))
            project_rows.append({
                "id": pid, "name": p.get("name") or "Untitled",
                "budget": round(budget, 2), "actual": actual, "remaining": remaining, "percent": pct,
                "expenses": round(parts["expenses"], 2), "labour": round(parts["labour"], 2), "subs": round(parts["subs"], 2),
                "status": status,
            })
            total_budget += budget
            total_actual += actual

        unassigned_total = round(unassigned["expenses"] + unassigned["labour"] + unassigned["subs"], 2)
        overall = {
            "budget": round(total_budget, 2),
            "actual": round(total_actual, 2),
            "unassigned": unassigned_total,
            "percent": round((total_actual / total_budget) * 100, 1) if total_budget > 0 else 0,
        }

        return {
            "period": period,
            "project_id": pid_filter,
            "buckets": ordered,
            "projects": project_rows,
            "overall": overall,
            "currency": ctx["currency_code"],
            "has_data": len(ordered) > 0 or total_actual > 0,
        }

    return router
