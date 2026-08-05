"""Estimator router: project cost estimation with AI-powered pricing, optimization, and client quotations."""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field


# ---------------------------------------------------------------- Models

class LineItemIn(BaseModel):
    category: str = "material"          # material | labor | equipment | overhead | other
    name: str = ""
    unit: str = "sqft"
    quantity: float = 0
    unit_price: float = 0
    notes: str = ""


class EstimateIn(BaseModel):
    project_id: Optional[str] = None
    title: str = ""
    client_name: str = ""
    client_phone: str = ""
    client_email: str = ""
    work_type: str = "general"          # interior | civil | electrical | plumbing | painting | flooring | general
    area_sqft: float = 0
    area_unit: str = "sqft"             # sqft | sqm
    line_items: List[LineItemIn] = []
    gross_margin_percent: float = 0
    gst_percent: float = 0             # 0, 5, 12, 18
    discount_percent: float = 0
    estimated_days: int = 0
    valid_until: str = ""
    terms: str = ""
    notes: str = ""


class MaterialPriceIn(BaseModel):
    name: str
    category: str = "general"
    unit: str = "sqft"
    price: float = 0
    region: str = ""


class AiSeedIn(BaseModel):
    region: str = "bangalore"
    work_type: str = "interior"


class OptimizeIn(BaseModel):
    focus: str = "cost"                 # cost | quality | speed


# ---------------------------------------------------------------- Deps

@dataclass
class Deps:
    db: Any
    get_current_user: Callable
    new_id: Callable[[], str]
    now_iso: Callable[[], str]
    today_str: Callable[[], str]
    country_ctx: Callable[[dict], dict]
    money_str: Callable[[float, dict], str]
    rate_limit: Callable
    ai_json: Callable
    ai_text: Callable
    logger: Any


# ---------------------------------------------------------------- Helpers

def _calc_totals(line_items: list, gross_margin_pct: float, gst_pct: float, discount_pct: float) -> dict:
    """Recalculate all totals from line items."""
    material_total = 0.0
    labor_total = 0.0
    equipment_total = 0.0
    overhead_total = 0.0
    other_total = 0.0

    calculated_items = []
    for li in line_items:
        qty = float(li.get("quantity", 0) if isinstance(li, dict) else getattr(li, "quantity", 0))
        price = float(li.get("unit_price", 0) if isinstance(li, dict) else getattr(li, "unit_price", 0))
        total = round(qty * price, 2)
        cat = (li.get("category", "other") if isinstance(li, dict) else getattr(li, "category", "other"))

        item = {
            "id": li.get("id") if isinstance(li, dict) else getattr(li, "id", None),
            "category": cat,
            "name": (li.get("name", "") if isinstance(li, dict) else getattr(li, "name", "")),
            "unit": (li.get("unit", "") if isinstance(li, dict) else getattr(li, "unit", "")),
            "quantity": qty,
            "unit_price": price,
            "total": total,
            "notes": (li.get("notes", "") if isinstance(li, dict) else getattr(li, "notes", "")),
        }
        if not item["id"]:
            item["id"] = f"li_{uuid.uuid4().hex[:8]}"
        calculated_items.append(item)

        if cat == "material":
            material_total += total
        elif cat == "labor":
            labor_total += total
        elif cat == "equipment":
            equipment_total += total
        elif cat == "overhead":
            overhead_total += total
        else:
            other_total += total

    subtotal = material_total + labor_total + equipment_total + overhead_total + other_total
    gross_margin_amount = round(subtotal * (gross_margin_pct / 100), 2) if gross_margin_pct else 0.0
    after_margin = subtotal + gross_margin_amount
    discount_amount = round(after_margin * (discount_pct / 100), 2) if discount_pct else 0.0
    after_discount = after_margin - discount_amount
    gst_amount = round(after_discount * (gst_pct / 100), 2) if gst_pct else 0.0
    grand_total = round(after_discount + gst_amount, 2)

    return {
        "line_items": calculated_items,
        "material_total": round(material_total, 2),
        "labor_total": round(labor_total, 2),
        "equipment_total": round(equipment_total, 2),
        "overhead_total": round(overhead_total, 2),
        "other_total": round(other_total, 2),
        "subtotal": round(subtotal, 2),
        "gross_margin_amount": gross_margin_amount,
        "discount_amount": discount_amount,
        "gst_amount": gst_amount,
        "grand_total": grand_total,
    }


# ---------------------------------------------------------------- AI Prompts

OPTIMIZE_SYSTEM = """You are a construction cost optimization expert for Indian contractors.
Given an estimate with line items, suggest practical ways to reduce cost, improve quality, or speed up the project.

For each suggestion, provide:
- "title": short name
- "description": explanation
- "savings_percent": estimated % savings on that line item (0 if not applicable)
- "affected_items": list of line item names this applies to
- "priority": "high" | "medium" | "low"

Output JSON: {"suggestions": [...]}
Keep suggestions practical and specific to Indian construction. Max 6 suggestions.
"""

MATERIAL_SEED_SYSTEM = """You are an Indian construction material pricing expert.
Given a region (city) and work type, provide approximate current retail market prices for common construction materials.

For each material provide:
- "name": material name with specification (e.g., "Marine Plywood 19mm", "Cement OPC 53 Grade")
- "category": wood | cement | steel | tiles | paint | electrical | plumbing | hardware | glass | stone | adhesive | waterproofing | other
- "unit": the standard unit (sqft, bag, kg, piece, litre, meter, bundle, etc.)
- "price": approximate retail price per unit in INR
- "notes": brief spec or brand reference

Output JSON: {"materials": [...]}
Include 30-50 materials relevant to the work type. Prices should be realistic for the specified Indian city.
"""

QUOTATION_SYSTEM = """You are a professional document formatter for Indian construction contractors.
Given an estimate's data, generate a clean, professional quotation summary in plain text.

Include:
- Quotation title and reference number
- Client details
- Itemized breakdown grouped by category (Materials, Labour, Equipment, etc.)
- Subtotal, Margin, GST, Discount, Grand Total
- Terms and conditions
- Validity period

Keep it professional and suitable for sharing with an Indian construction client.
Output JSON: {"quotation_text": "...", "subject_line": "..."}
"""


# ---------------------------------------------------------------- Router

def build_router(deps: Deps) -> APIRouter:
    router = APIRouter()

    # ---- ESTIMATES CRUD ----

    @router.get("/estimates")
    async def list_estimates(
        user: dict = Depends(deps.get_current_user),
        project_id: str = "", status: str = "", q: str = "",
        limit: int = 100, offset: int = 0,
    ):
        query: Dict[str, Any] = {"owner_id": user["user_id"]}
        if project_id:
            query["project_id"] = project_id
        if status:
            query["status"] = status
        if q:
            needle = re.escape(q.strip())
            if needle:
                query["$or"] = [
                    {"title": {"$regex": needle, "$options": "i"}},
                    {"client_name": {"$regex": needle, "$options": "i"}},
                ]
        limit = max(1, min(int(limit), 500))
        offset = max(0, int(offset))
        total_count = await deps.db.estimates.count_documents(query)
        docs = (
            await deps.db.estimates.find(query, {"_id": 0})
            .sort("updated_at", -1)
            .skip(offset)
            .limit(limit)
            .to_list(limit)
        )
        return {"items": docs, "count": total_count, "limit": limit, "offset": offset}

    @router.post("/estimates")
    async def create_estimate(body: EstimateIn, user: dict = Depends(deps.get_current_user)):
        ctx = deps.country_ctx(user)
        items_raw = [li.model_dump() for li in body.line_items]
        calcs = _calc_totals(items_raw, body.gross_margin_percent, body.gst_percent, body.discount_percent)
        valid = body.valid_until or (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%Y-%m-%d")

        doc = {
            "id": deps.new_id(),
            "owner_id": user["user_id"],
            "project_id": body.project_id or None,
            "version": 1,
            "status": "draft",
            "title": body.title.strip() or "Untitled Estimate",
            "client_name": body.client_name.strip(),
            "client_phone": body.client_phone.strip(),
            "client_email": body.client_email.strip(),
            "work_type": body.work_type,
            "area_sqft": float(body.area_sqft or 0),
            "area_unit": body.area_unit or "sqft",
            "line_items": calcs["line_items"],
            "subtotal": calcs["subtotal"],
            "material_total": calcs["material_total"],
            "labor_total": calcs["labor_total"],
            "equipment_total": calcs["equipment_total"],
            "overhead_total": calcs["overhead_total"],
            "other_total": calcs["other_total"],
            "gross_margin_percent": float(body.gross_margin_percent or 0),
            "gross_margin_amount": calcs["gross_margin_amount"],
            "gst_percent": float(body.gst_percent or 0),
            "gst_amount": calcs["gst_amount"],
            "discount_percent": float(body.discount_percent or 0),
            "discount_amount": calcs["discount_amount"],
            "grand_total": calcs["grand_total"],
            "estimated_days": int(body.estimated_days or 0),
            "valid_until": valid,
            "terms": body.terms.strip(),
            "notes": body.notes.strip(),
            "currency": ctx["currency_code"],
            "ai_suggestions": [],
            "created_at": deps.now_iso(),
            "updated_at": deps.now_iso(),
        }
        await deps.db.estimates.insert_one({**doc})
        doc.pop("_id", None)
        return doc

    @router.get("/estimates/{estimate_id}")
    async def get_estimate(estimate_id: str, user: dict = Depends(deps.get_current_user)):
        doc = await deps.db.estimates.find_one(
            {"id": estimate_id, "owner_id": user["user_id"]}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Estimate not found")
        return doc

    @router.put("/estimates/{estimate_id}")
    async def update_estimate(estimate_id: str, body: EstimateIn, user: dict = Depends(deps.get_current_user)):
        existing = await deps.db.estimates.find_one(
            {"id": estimate_id, "owner_id": user["user_id"]}
        )
        if not existing:
            raise HTTPException(status_code=404, detail="Estimate not found")

        items_raw = [li.model_dump() for li in body.line_items]
        calcs = _calc_totals(items_raw, body.gross_margin_percent, body.gst_percent, body.discount_percent)

        update = {
            "project_id": body.project_id or existing.get("project_id"),
            "title": body.title.strip() or existing.get("title", ""),
            "client_name": body.client_name.strip(),
            "client_phone": body.client_phone.strip(),
            "client_email": body.client_email.strip(),
            "work_type": body.work_type,
            "area_sqft": float(body.area_sqft or 0),
            "area_unit": body.area_unit or "sqft",
            "line_items": calcs["line_items"],
            "subtotal": calcs["subtotal"],
            "material_total": calcs["material_total"],
            "labor_total": calcs["labor_total"],
            "equipment_total": calcs["equipment_total"],
            "overhead_total": calcs["overhead_total"],
            "other_total": calcs["other_total"],
            "gross_margin_percent": float(body.gross_margin_percent or 0),
            "gross_margin_amount": calcs["gross_margin_amount"],
            "gst_percent": float(body.gst_percent or 0),
            "gst_amount": calcs["gst_amount"],
            "discount_percent": float(body.discount_percent or 0),
            "discount_amount": calcs["discount_amount"],
            "grand_total": calcs["grand_total"],
            "estimated_days": int(body.estimated_days or 0),
            "valid_until": body.valid_until or existing.get("valid_until", ""),
            "terms": body.terms.strip(),
            "notes": body.notes.strip(),
            "updated_at": deps.now_iso(),
        }
        await deps.db.estimates.update_one(
            {"id": estimate_id, "owner_id": user["user_id"]}, {"$set": update}
        )
        updated = await deps.db.estimates.find_one(
            {"id": estimate_id, "owner_id": user["user_id"]}, {"_id": 0}
        )
        return updated

    @router.delete("/estimates/{estimate_id}")
    async def delete_estimate(estimate_id: str, user: dict = Depends(deps.get_current_user)):
        res = await deps.db.estimates.delete_one(
            {"id": estimate_id, "owner_id": user["user_id"]}
        )
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Estimate not found")
        return {"deleted": True}

    @router.post("/estimates/{estimate_id}/duplicate")
    async def duplicate_estimate(estimate_id: str, user: dict = Depends(deps.get_current_user)):
        """Create a new revision (version) of an existing estimate."""
        original = await deps.db.estimates.find_one(
            {"id": estimate_id, "owner_id": user["user_id"]}, {"_id": 0}
        )
        if not original:
            raise HTTPException(status_code=404, detail="Estimate not found")

        # Find highest version for this lineage
        same_title = await deps.db.estimates.find(
            {"owner_id": user["user_id"], "title": original["title"]},
            {"version": 1}
        ).to_list(100)
        max_ver = max((d.get("version", 1) for d in same_title), default=1)

        new_doc = {**original}
        new_doc["id"] = deps.new_id()
        new_doc["version"] = max_ver + 1
        new_doc["status"] = "draft"
        new_doc["created_at"] = deps.now_iso()
        new_doc["updated_at"] = deps.now_iso()
        new_doc.pop("_id", None)

        # Mark original as revised
        await deps.db.estimates.update_one(
            {"id": estimate_id, "owner_id": user["user_id"]},
            {"$set": {"status": "revised"}}
        )
        await deps.db.estimates.insert_one({**new_doc})
        new_doc.pop("_id", None)
        return new_doc

    @router.patch("/estimates/{estimate_id}/status")
    async def update_estimate_status(estimate_id: str, user: dict = Depends(deps.get_current_user), status: str = "sent"):
        if status not in ("draft", "sent", "accepted", "revised"):
            raise HTTPException(status_code=400, detail="Invalid status")
        res = await deps.db.estimates.update_one(
            {"id": estimate_id, "owner_id": user["user_id"]},
            {"$set": {"status": status, "updated_at": deps.now_iso()}}
        )
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Estimate not found")
        return {"status": status}

    # ---- AI OPTIMIZATION ----

    @router.post("/estimates/{estimate_id}/optimize")
    async def optimize_estimate(estimate_id: str, body: OptimizeIn, user: dict = Depends(deps.get_current_user)):
        await deps.rate_limit(f"est_opt:{user['user_id']}", limit=10, window_seconds=60)
        doc = await deps.db.estimates.find_one(
            {"id": estimate_id, "owner_id": user["user_id"]}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Estimate not found")

        ctx = deps.country_ctx(user)
        items_summary = "\n".join(
            f"- {li['name']} ({li['category']}): {li['quantity']} {li['unit']} × ₹{li['unit_price']} = ₹{li['total']}"
            for li in doc.get("line_items", [])
        )
        prompt = (
            f"Work type: {doc.get('work_type', 'general')}\n"
            f"Area: {doc.get('area_sqft', 0)} {doc.get('area_unit', 'sqft')}\n"
            f"Region/Country: {ctx.get('name', 'India')}\n"
            f"Focus: {body.focus}\n"
            f"Subtotal: ₹{doc.get('subtotal', 0):,.0f}\n"
            f"Grand Total: ₹{doc.get('grand_total', 0):,.0f}\n\n"
            f"Line items:\n{items_summary}"
        )

        result = await deps.ai_json(OPTIMIZE_SYSTEM, prompt, provider="openai", model="gpt-4o")
        suggestions = result.get("suggestions", [])

        # Save suggestions on the estimate
        await deps.db.estimates.update_one(
            {"id": estimate_id, "owner_id": user["user_id"]},
            {"$set": {"ai_suggestions": suggestions, "updated_at": deps.now_iso()}}
        )
        return {"suggestions": suggestions}

    # ---- QUOTATION ----

    @router.get("/estimates/{estimate_id}/quotation")
    async def get_quotation(estimate_id: str, user: dict = Depends(deps.get_current_user)):
        """Generate a client-facing quotation view from an estimate."""
        doc = await deps.db.estimates.find_one(
            {"id": estimate_id, "owner_id": user["user_id"]}, {"_id": 0}
        )
        if not doc:
            raise HTTPException(status_code=404, detail="Estimate not found")

        # Build grouped line items for the quotation
        grouped: Dict[str, list] = {}
        for li in doc.get("line_items", []):
            cat = li.get("category", "other")
            grouped.setdefault(cat, []).append(li)

        ctx = deps.country_ctx(user)
        return {
            "estimate_id": doc["id"],
            "ref_number": f"EST-{doc['id'][:8].upper()}",
            "version": doc.get("version", 1),
            "title": doc.get("title", ""),
            "status": doc.get("status", "draft"),
            "contractor_name": user.get("name", ""),
            "contractor_company": user.get("company", ""),
            "contractor_phone": user.get("phone", ""),
            "contractor_email": user.get("email", ""),
            "client_name": doc.get("client_name", ""),
            "client_phone": doc.get("client_phone", ""),
            "client_email": doc.get("client_email", ""),
            "work_type": doc.get("work_type", ""),
            "area": f"{doc.get('area_sqft', 0)} {doc.get('area_unit', 'sqft')}",
            "grouped_items": grouped,
            "subtotal": doc.get("subtotal", 0),
            "gross_margin_percent": doc.get("gross_margin_percent", 0),
            "gross_margin_amount": doc.get("gross_margin_amount", 0),
            "discount_percent": doc.get("discount_percent", 0),
            "discount_amount": doc.get("discount_amount", 0),
            "gst_percent": doc.get("gst_percent", 0),
            "gst_amount": doc.get("gst_amount", 0),
            "grand_total": doc.get("grand_total", 0),
            "currency": doc.get("currency", ctx["currency_code"]),
            "estimated_days": doc.get("estimated_days", 0),
            "valid_until": doc.get("valid_until", ""),
            "terms": doc.get("terms", ""),
            "notes": doc.get("notes", ""),
            "created_at": doc.get("created_at", ""),
        }

    # ---- MATERIAL PRICES ----

    @router.get("/material-prices")
    async def list_material_prices(
        user: dict = Depends(deps.get_current_user),
        category: str = "", q: str = "",
    ):
        query: Dict[str, Any] = {"owner_id": user["user_id"]}
        if category:
            query["category"] = category
        if q:
            needle = re.escape(q.strip())
            if needle:
                query["name"] = {"$regex": needle, "$options": "i"}
        docs = (
            await deps.db.material_prices.find(query, {"_id": 0})
            .sort("name", 1)
            .to_list(500)
        )
        return {"items": docs, "count": len(docs)}

    @router.post("/material-prices")
    async def upsert_material_price(body: MaterialPriceIn, user: dict = Depends(deps.get_current_user)):
        # Upsert by name+owner so duplicates are updated
        existing = await deps.db.material_prices.find_one(
            {"owner_id": user["user_id"], "name": {"$regex": f"^{re.escape(body.name.strip())}$", "$options": "i"}}
        )
        if existing:
            await deps.db.material_prices.update_one(
                {"id": existing["id"]},
                {"$set": {
                    "category": body.category,
                    "unit": body.unit,
                    "price": float(body.price),
                    "region": body.region.strip(),
                    "source": "manual",
                    "updated_at": deps.now_iso(),
                }}
            )
            updated = await deps.db.material_prices.find_one({"id": existing["id"]}, {"_id": 0})
            return updated
        else:
            doc = {
                "id": deps.new_id(),
                "owner_id": user["user_id"],
                "name": body.name.strip(),
                "category": body.category,
                "unit": body.unit,
                "price": float(body.price),
                "market_price": None,
                "region": body.region.strip(),
                "source": "manual",
                "updated_at": deps.now_iso(),
            }
            await deps.db.material_prices.insert_one({**doc})
            doc.pop("_id", None)
            return doc

    @router.delete("/material-prices/{price_id}")
    async def delete_material_price(price_id: str, user: dict = Depends(deps.get_current_user)):
        res = await deps.db.material_prices.delete_one(
            {"id": price_id, "owner_id": user["user_id"]}
        )
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Material price not found")
        return {"deleted": True}

    @router.post("/material-prices/ai-seed")
    async def ai_seed_prices(body: AiSeedIn, user: dict = Depends(deps.get_current_user)):
        """AI generates approximate market prices for common materials in a region."""
        await deps.rate_limit(f"mat_seed:{user['user_id']}", limit=3, window_seconds=300)
        ctx = deps.country_ctx(user)
        prompt = (
            f"Region/City: {body.region}\n"
            f"Country: {ctx.get('name', 'India')}\n"
            f"Work type: {body.work_type}\n"
            f"Currency: {ctx['currency_code']}\n"
            f"Provide approximate current retail prices for common construction materials."
        )
        result = await deps.ai_json(MATERIAL_SEED_SYSTEM, prompt, provider="openai", model="gpt-4o")
        materials = result.get("materials", [])

        seeded = []
        for mat in materials:
            name = (mat.get("name") or "").strip()
            if not name:
                continue
            # Don't overwrite user's manual prices
            existing = await deps.db.material_prices.find_one(
                {"owner_id": user["user_id"], "name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
            )
            if existing:
                # Just update the market_price reference
                await deps.db.material_prices.update_one(
                    {"id": existing["id"]},
                    {"$set": {"market_price": float(mat.get("price", 0)), "updated_at": deps.now_iso()}}
                )
            else:
                doc = {
                    "id": deps.new_id(),
                    "owner_id": user["user_id"],
                    "name": name,
                    "category": mat.get("category", "other"),
                    "unit": mat.get("unit", "piece"),
                    "price": float(mat.get("price", 0)),
                    "market_price": float(mat.get("price", 0)),
                    "region": body.region.strip(),
                    "source": "ai_seeded",
                    "notes": mat.get("notes", ""),
                    "updated_at": deps.now_iso(),
                }
                await deps.db.material_prices.insert_one({**doc})
                doc.pop("_id", None)
                seeded.append(doc)

        total = await deps.db.material_prices.count_documents({"owner_id": user["user_id"]})
        return {"seeded": len(seeded), "total": total, "items": seeded}

    return router
