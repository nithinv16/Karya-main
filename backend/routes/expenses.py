"""Expenses router: list (regex search), create, upload-receipt (AI parse), delete."""
from __future__ import annotations

import asyncio
import base64
import re
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel


class ExpenseIn(BaseModel):
    vendor: str = ""
    date: str = ""
    amount: float = 0.0
    currency: str = ""
    category: str = "other"
    summary: str = ""
    items: List[Dict[str, Any]] = []
    project_id: Optional[str] = None


@dataclass
class Deps:
    db: Any
    get_current_user: Callable
    new_id: Callable[[], str]
    now_iso: Callable[[], str]
    today_str: Callable[[], str]
    country_ctx: Callable[[dict], dict]
    money_str: Callable[[float, dict], str]
    rate_limit: Callable  # async(key, limit, window_seconds)
    put_object: Callable
    extract_text: Callable
    ai_json: Callable
    image_content_cls: Any
    receipt_system: str
    app_name: str
    logger: Any


def build_router(deps: Deps) -> APIRouter:
    router = APIRouter()

    @router.get("/expenses")
    async def list_expenses(
        user: dict = Depends(deps.get_current_user),
        q: str = "", category: str = "", limit: int = 500, offset: int = 0,
    ):
        query: Dict[str, Any] = {"owner_id": user["user_id"]}
        if category:
            query["category"] = category
        if q:
            needle = re.escape(q.strip())
            if needle:
                query["$or"] = [
                    {"vendor": {"$regex": needle, "$options": "i"}},
                    {"summary": {"$regex": needle, "$options": "i"}},
                ]
        try:
            limit_val = int(limit)
        except (TypeError, ValueError):
            limit_val = 500
        try:
            offset_val = int(offset)
        except (TypeError, ValueError):
            offset_val = 0
        limit = max(1, min(limit_val, 2000))
        offset = max(0, offset_val)
        total_count = await deps.db.expenses.count_documents(query)
        docs = await deps.db.expenses.find(query, {"_id": 0}).sort("date", -1).skip(offset).limit(limit).to_list(limit)
        ctx = deps.country_ctx(user)
        total = round(sum(float(d.get("amount") or 0) for d in docs), 2)
        by_cat: Dict[str, float] = {}
        for d in docs:
            by_cat[d.get("category", "other")] = by_cat.get(d.get("category", "other"), 0) + float(d.get("amount") or 0)
        return {
            "items": docs,
            "total": total,
            "count": total_count,
            "limit": limit,
            "offset": offset,
            "currency": ctx["currency_code"],
            "by_category": [{"category": k, "amount": round(v, 2)} for k, v in sorted(by_cat.items(), key=lambda kv: -kv[1])],
        }

    @router.post("/expenses")
    async def create_expense(body: ExpenseIn, user: dict = Depends(deps.get_current_user)):
        ctx = deps.country_ctx(user)
        exp = {
            "id": deps.new_id(), "owner_id": user["user_id"],
            "vendor": body.vendor.strip(), "date": body.date or deps.today_str(),
            "amount": float(body.amount or 0), "currency": (body.currency or ctx["currency_code"]).strip(),
            "category": body.category or "other", "items": body.items or [],
            "summary": body.summary.strip(), "attachment": None, "source": "manual",
            "project_id": body.project_id or None,
            "created_at": deps.now_iso(),
        }
        await deps.db.expenses.insert_one({**exp})
        exp.pop("_id", None)
        return exp

    @router.post("/expenses/upload-receipt")
    async def upload_receipt(
        file: UploadFile = File(...),
        project_id: Optional[str] = Form(None),
        user: dict = Depends(deps.get_current_user),
    ):
        await deps.rate_limit(f"receipt:{user['user_id']}", limit=20, window_seconds=60)
        data = await file.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty file")
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Receipt too large (20MB max)")
        ct = (file.content_type or "").lower()
        fname = file.filename or "receipt"
        is_image = ct.startswith("image/") or any(fname.lower().endswith(x) for x in (".jpg", ".jpeg", ".png", ".webp", ".heic"))
        is_pdf = ct == "application/pdf" or fname.lower().endswith(".pdf")
        if not (is_image or is_pdf):
            raise HTTPException(status_code=415, detail="Please upload a photo (JPG/PNG) or PDF of the receipt.")

        ext = fname.rsplit(".", 1)[-1].lower() if "." in fname else ("jpg" if is_image else "pdf")
        path = f"{deps.app_name}/receipts/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
        stored = await asyncio.to_thread(deps.put_object, path, data, ct or ("image/jpeg" if is_image else "application/pdf"))
        file_rec = {
            "id": deps.new_id(), "owner_id": user["user_id"], "path": stored["path"],
            "filename": fname, "content_type": ct or ("image/jpeg" if is_image else "application/pdf"),
            "size": stored.get("size", len(data)),
            "extracted_text": deps.extract_text(data, ct, fname) if is_pdf else "",
            "is_deleted": False, "created_at": deps.now_iso(),
        }
        await deps.db.files.insert_one({**file_rec})

        parsed: Dict[str, Any] = {}
        try:
            if is_image:
                b64 = base64.b64encode(data).decode()
                parsed = await deps.ai_json(
                    deps.receipt_system, "Extract this receipt.",
                    images=[deps.image_content_cls(image_base64=b64)],
                    provider="openai", model="gpt-4o",
                )
            else:
                text = file_rec.get("extracted_text") or ""
                if not text.strip():
                    raise HTTPException(status_code=422, detail="Couldn't read any text from that PDF. Try a clearer scan or photo.")
                parsed = await deps.ai_json(
                    deps.receipt_system, f"Receipt text:\n{text[:5000]}",
                    provider="openai", model="gpt-4o",
                )
        except HTTPException:
            raise
        except Exception as e:
            deps.logger.warning(f"receipt parse failed: {e}")
            parsed = {}

        amount = float(parsed.get("total_amount") or 0)
        ctx = deps.country_ctx(user)
        att = {"path": file_rec["path"], "filename": file_rec["filename"], "content_type": file_rec["content_type"], "size": file_rec["size"]}
        exp = {
            "id": deps.new_id(), "owner_id": user["user_id"],
            "vendor": (parsed.get("vendor") or "").strip(),
            "date": parsed.get("date") or deps.today_str(),
            "amount": amount,
            "currency": (parsed.get("currency") or ctx["currency_code"]).strip(),
            "category": parsed.get("category") or "other",
            "items": parsed.get("items") or [],
            "summary": (parsed.get("summary") or "").strip(),
            "attachment": att,
            "source": "web_upload",
            "project_id": project_id or None,
            "created_at": deps.now_iso(),
        }
        await deps.db.expenses.insert_one({**exp})
        exp.pop("_id", None)
        await deps.db.knowledge.insert_one({
            "id": deps.new_id(), "owner_id": user["user_id"],
            "title": f"Receipt — {exp['vendor'] or 'unknown vendor'} ({deps.money_str(amount, user)})",
            "content": exp["summary"] or f"Receipt of {deps.money_str(amount, user)} — category {exp['category']}.",
            "project_id": exp["project_id"], "tags": ["receipt", "expense", "web"],
            "attachment": att, "created_at": deps.now_iso(),
        })
        return {"expense": exp, "parsed": bool(parsed.get("total_amount"))}

    @router.delete("/expenses/{expense_id}")
    async def delete_expense(expense_id: str, user: dict = Depends(deps.get_current_user)):
        result = await deps.db.expenses.delete_one({"id": expense_id, "owner_id": user["user_id"]})
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Expense not found")
        return {"deleted": True}

    return router
