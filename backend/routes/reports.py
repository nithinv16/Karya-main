"""Daily Reports + WhatsApp router.

Extracted from server.py for readability. Uses a small `Deps` container populated
at wiring time so this module does not import server.py directly (avoiding
circular imports).
"""
from __future__ import annotations

import asyncio
import base64
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class ReportGenIn(BaseModel):
    project_id: Optional[str] = None
    location: str = ""
    notes_text: str = ""
    photo_ids: List[str] = []
    report_date: Optional[str] = None
    whatsapp_send: bool = False
    whatsapp_audience: Dict[str, bool] = {}
    whatsapp_extra_numbers: List[str] = []


class WhatsappSendIn(BaseModel):
    audience: Dict[str, bool] = {}
    extra_numbers: List[str] = []


@dataclass
class Deps:
    db: Any
    get_current_user: Callable
    new_id: Callable[[], str]
    now_iso: Callable[[], str]
    today_str: Callable[[], str]
    get_object: Callable  # storage getter
    ai_json: Callable
    image_content_cls: Any  # emergentintegrations ImageContent
    twilio_client: Callable  # returns twilio client or None
    twilio_from: str
    twilio_rest_exception: Any
    build_signed_file_url: Callable
    backend_public_url: str
    logger: Any


REPORT_SYSTEM = """You write professional daily site reports for construction & maintenance companies in India.
You receive field notes (often a rough voice-note transcript), site photos, a location and a date.
Study the photos carefully — describe visible work, progress, equipment, materials and any safety issues you can see.
Output JSON:
{"title": str, "summary": str, "weather": str|null, "work_completed": [str], "manpower": str,
 "materials_used": [str], "issues_delays": [str], "safety_observations": [str], "next_steps": [str]}
Keep it factual and professional — this report goes to the client/management. If a field is unknown, use an empty list or null."""


def _normalize_phone(p: str) -> Optional[str]:
    if not p:
        return None
    s = re.sub(r"[^\d+]", "", p.strip())
    if not s:
        return None
    if not s.startswith("+"):
        if len(s) == 10:
            s = "+91" + s
        else:
            s = "+" + s
    return f"whatsapp:{s}"


def _format_report_message(rec: dict) -> str:
    c = rec.get("content") or {}
    lines = [
        f"*{c.get('title') or 'Daily Site Report'}*",
        f"_{rec.get('project_name') or 'Site'} · {rec.get('report_date') or ''}_",
        "",
    ]
    if c.get("summary"):
        lines.append(c["summary"])
        lines.append("")
    if c.get("work_completed"):
        lines.append("*Work completed:*")
        lines += [f"• {x}" for x in c["work_completed"][:6]]
        lines.append("")
    if c.get("manpower"):
        lines.append(f"*Manpower:* {c['manpower']}")
    if c.get("issues_delays"):
        lines.append("*Issues / delays:*")
        lines += [f"• {x}" for x in c["issues_delays"][:4]]
    if c.get("next_steps"):
        lines.append("*Next steps:*")
        lines += [f"• {x}" for x in c["next_steps"][:4]]
    if rec.get("location"):
        lines.append("")
        lines.append(f"📍 {rec['location']}")
    return "\n".join(lines).strip()[:1500]


def build_router(deps: Deps) -> APIRouter:
    router = APIRouter()

    async def _resolve_report_recipients(owner_id, project_id, audience, extra):
        numbers: List[str] = []
        if audience.get("client") and project_id:
            proj = await deps.db.projects.find_one({"id": project_id, "owner_id": owner_id}, {"_id": 0})
            if proj and proj.get("client_phone"):
                numbers.append(proj["client_phone"])
        if audience.get("subcontractors"):
            q = {"owner_id": owner_id, **({"project_id": project_id} if project_id else {})}
            subs = await deps.db.subcontractors.find(q, {"_id": 0, "phone": 1}).to_list(200)
            numbers += [s.get("phone", "") for s in subs if s.get("phone")]
        if audience.get("labour"):
            q = {"owner_id": owner_id}
            if project_id:
                q["project_id"] = project_id
            workers = await deps.db.workers.find(q, {"_id": 0, "phone": 1}).to_list(500)
            numbers += [w.get("phone", "") for w in workers if w.get("phone")]
        numbers += list(extra or [])
        seen, out = set(), []
        for n in numbers:
            norm = _normalize_phone(n)
            if norm and norm not in seen:
                seen.add(norm)
                out.append(norm)
        return out

    def _build_media(rec: dict) -> Optional[List[str]]:
        if not deps.backend_public_url:
            return None
        urls: List[str] = []
        for p in (rec.get("photos") or [])[:3]:
            if p.get("path"):
                urls.append(deps.build_signed_file_url(p["path"], deps.backend_public_url))
        return urls or None

    def _send_batch(numbers, body, media_urls):
        tw = deps.twilio_client()
        if not tw:
            return {"sent": 0, "failed": 0, "errors": ["Twilio not configured — set TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN"], "recipients": numbers}
        sent, failed, errors = 0, 0, []
        for n in numbers:
            try:
                kwargs = {"from_": deps.twilio_from, "to": n, "body": body}
                if media_urls:
                    kwargs["media_url"] = media_urls[:5]
                tw.messages.create(**kwargs)
                sent += 1
            except deps.twilio_rest_exception as e:
                failed += 1
                errors.append(f"{n}: {e.msg or str(e)}")
            except Exception as e:
                failed += 1
                errors.append(f"{n}: {e}")
        return {"sent": sent, "failed": failed, "errors": errors[:10], "recipients": numbers}

    async def _dispatch(rec: dict, numbers: List[str]):
        media = _build_media(rec)
        result = await asyncio.to_thread(_send_batch, numbers, _format_report_message(rec), media)
        await deps.db.daily_reports.update_one({"id": rec["id"]}, {"$set": {"whatsapp": result}})
        return result

    @router.post("/reports/generate")
    async def generate_report(body: ReportGenIn, user: dict = Depends(deps.get_current_user)):
        uid = user["user_id"]
        if not body.notes_text.strip() and not body.photo_ids:
            raise HTTPException(status_code=400, detail="Provide field notes or at least one photo")
        project = None
        if body.project_id:
            project = await deps.db.projects.find_one({"id": body.project_id, "owner_id": uid}, {"_id": 0})
        photos, images = [], []
        for fid in body.photo_ids[:4]:
            rec = await deps.db.files.find_one({"id": fid, "owner_id": uid, "is_deleted": False}, {"_id": 0})
            if not rec:
                continue
            photos.append(rec)
            if (rec.get("content_type") or "").startswith("image/"):
                try:
                    data, _ = await asyncio.to_thread(deps.get_object, rec["path"])
                    images.append(deps.image_content_cls(image_base64=base64.b64encode(data).decode()))
                except Exception as e:
                    deps.logger.warning(f"Photo fetch failed: {e}")
        rdate = body.report_date or deps.today_str()
        prompt = (
            f"Project: {project['name'] if project else 'Not specified'}"
            + (f" ({project.get('location')}, client: {project.get('client')})" if project else "") + "\n"
            f"Report date: {rdate}\nLocation: {body.location or 'Not specified'}\n"
            f"Field notes / voice transcript:\n{body.notes_text.strip() or '(none — rely on the photos)'}\n"
            f"Photos attached: {len(images)}"
        )
        content = await deps.ai_json(REPORT_SYSTEM, prompt, images=images or None)
        doc = {
            "id": deps.new_id(), "owner_id": uid, "project_id": body.project_id,
            "project_name": project["name"] if project else None,
            "location": body.location, "notes_text": body.notes_text,
            "report_date": rdate, "photos": photos, "content": content,
            "whatsapp": {"sent": 0, "failed": 0, "recipients": []},
            "created_at": deps.now_iso(),
        }
        await deps.db.daily_reports.insert_one({**doc})
        doc.pop("_id", None)
        if body.whatsapp_send:
            numbers = await _resolve_report_recipients(uid, body.project_id, body.whatsapp_audience or {}, body.whatsapp_extra_numbers or [])
            doc["whatsapp"] = await _dispatch(doc, numbers)
        return doc

    @router.post("/reports/{report_id}/whatsapp")
    async def send_whatsapp(report_id: str, body: WhatsappSendIn, user: dict = Depends(deps.get_current_user)):
        uid = user["user_id"]
        rec = await deps.db.daily_reports.find_one({"id": report_id, "owner_id": uid}, {"_id": 0})
        if not rec:
            raise HTTPException(status_code=404, detail="Report not found")
        numbers = await _resolve_report_recipients(uid, rec.get("project_id"), body.audience or {}, body.extra_numbers or [])
        if not numbers:
            raise HTTPException(status_code=400, detail="No valid recipient numbers resolved")
        return await _dispatch(rec, numbers)

    @router.post("/reports/{report_id}/whatsapp/quick")
    async def send_whatsapp_quick(report_id: str, user: dict = Depends(deps.get_current_user)):
        """One-tap resend: project client + user.default_client_phone."""
        uid = user["user_id"]
        rec = await deps.db.daily_reports.find_one({"id": report_id, "owner_id": uid}, {"_id": 0})
        if not rec:
            raise HTTPException(status_code=404, detail="Report not found")
        extras: List[str] = []
        if user.get("default_client_phone"):
            extras.append(user["default_client_phone"])
        numbers = await _resolve_report_recipients(uid, rec.get("project_id"), {"client": True}, extras)
        if not numbers:
            raise HTTPException(status_code=400, detail="Set a client WhatsApp number on the project or a default in your profile.")
        return await _dispatch(rec, numbers)

    @router.get("/reports")
    async def list_reports(user: dict = Depends(deps.get_current_user)):
        return await deps.db.daily_reports.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

    @router.get("/reports/{report_id}")
    async def get_report(report_id: str, user: dict = Depends(deps.get_current_user)):
        rec = await deps.db.daily_reports.find_one({"id": report_id, "owner_id": user["user_id"]}, {"_id": 0})
        if not rec:
            raise HTTPException(status_code=404, detail="Report not found")
        return rec

    @router.delete("/reports/{report_id}")
    async def delete_report(report_id: str, user: dict = Depends(deps.get_current_user)):
        res = await deps.db.daily_reports.delete_one({"id": report_id, "owner_id": user["user_id"]})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Report not found")
        return {"ok": True}

    return router
