"""Contact form + public company-info router.

Extracted from server.py. Uses a Deps container so this module does not import
server directly (avoids circular imports and keeps the router pure).
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel


class ContactIn(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    subject: str = ""
    message: str = ""


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass
class Deps:
    db: Any
    new_id: Callable[[], str]
    now_iso: Callable[[], str]
    rate_limit: Callable  # async callable(key, limit, window_seconds)
    tg_configured: Callable[[], bool]
    tg_send: Callable  # async callable(chat_id: int, text: str)
    tg_user_lang: Any  # ContextVar[str]
    company_legal_name: str
    app_name: str
    contact_email: str
    website: str
    logger: Any


def build_router(deps: Deps) -> APIRouter:
    router = APIRouter()

    @router.get("/company-info")
    async def company_info():
        """Public: legal + support info displayed on the Contact Us page and footer."""
        return {
            "legal_name": deps.company_legal_name,
            "product_name": deps.app_name,
            "support_email": deps.contact_email,
            "website": deps.website,
        }

    @router.post("/contact")
    async def submit_contact(body: ContactIn, request: Request):
        """Public form — validates input, saves the submission, and quietly delivers
        it to the Karya ops-owner via Telegram (chat_id resolved server-side; the
        recipient's handle is never exposed to clients).
        """
        await deps.rate_limit(
            f"contact:{request.client.host if request.client else 'anon'}",
            limit=5, window_seconds=300,
        )
        name = (body.name or "").strip()[:120]
        email = (body.email or "").strip()[:120]
        phone = (body.phone or "").strip()[:40]
        company = (body.company or "").strip()[:120]
        subject = (body.subject or "").strip()[:200]
        message = (body.message or "").strip()[:5000]
        if not name:
            raise HTTPException(status_code=400, detail="Please enter your name.")
        if not email or not _EMAIL_RE.match(email):
            raise HTTPException(status_code=400, detail="Enter a valid email address.")
        if len(message) < 10:
            raise HTTPException(status_code=400, detail="Please share a bit more detail (at least 10 characters).")
        submission = {
            "id": deps.new_id(),
            "name": name, "email": email, "phone": phone, "company": company,
            "subject": subject or "Contact form submission",
            "message": message,
            "source_ip": (request.client.host if request.client else "") or "",
            "user_agent": request.headers.get("user-agent", "")[:300],
            "status": "new",
            "delivered_via": [],
            "created_at": deps.now_iso(),
        }
        await deps.db.contact_submissions.insert_one({**submission})

        delivered = []
        try:
            chat_id: Optional[int] = None
            cached = await deps.db.system_config.find_one({"key": "contact_chat_id"})
            if cached and cached.get("value"):
                try:
                    chat_id = int(cached["value"])
                except (TypeError, ValueError):
                    chat_id = None
            if chat_id and deps.tg_configured():
                text = (
                    "📮 <b>New contact form submission</b>\n\n"
                    f"<b>Name:</b> {html.escape(name)}\n"
                    f"<b>Email:</b> {html.escape(email)}\n"
                    + (f"<b>Phone:</b> {html.escape(phone)}\n" if phone else "")
                    + (f"<b>Company:</b> {html.escape(company)}\n" if company else "")
                    + f"<b>Subject:</b> {html.escape(subject or '—')}\n\n"
                    f"<b>Message:</b>\n{html.escape(message)[:3500]}"
                )
                tok = deps.tg_user_lang.set("en")  # never translate an internal ops alert
                try:
                    await deps.tg_send(chat_id, text)
                finally:
                    deps.tg_user_lang.reset(tok)
                delivered.append("telegram")
        except Exception as e:
            deps.logger.warning(f"contact telegram delivery failed: {e}")

        if delivered:
            await deps.db.contact_submissions.update_one(
                {"id": submission["id"]}, {"$set": {"delivered_via": delivered, "delivered_at": deps.now_iso()}}
            )
        return {"ok": True, "id": submission["id"]}

    return router
