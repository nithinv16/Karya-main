"""Telegram notification-preferences router (settings only; the ping
scheduler stays in server.py for now since it touches ContextVars, tg_send,
and startup lifecycle)."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel


class NotificationsIn(BaseModel):
    timezone: Optional[str] = None
    morning_briefing: Optional[Dict[str, Any]] = None
    compliance_alerts: Optional[Dict[str, Any]] = None
    payroll_reminder: Optional[Dict[str, Any]] = None


@dataclass
class Deps:
    db: Any
    get_current_user: Callable
    notifications_for: Callable[[dict], Dict[str, Any]]


def build_router(deps: Deps) -> APIRouter:
    router = APIRouter()

    @router.get("/telegram/notifications")
    async def get_notifications(user: dict = Depends(deps.get_current_user)):
        return {
            "notifications": deps.notifications_for(user),
            "telegram_linked": bool(user.get("telegram_chat_id")),
        }

    @router.put("/telegram/notifications")
    async def update_notifications(body: NotificationsIn, user: dict = Depends(deps.get_current_user)):
        from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
        patch: Dict[str, Any] = {}
        if body.timezone is not None:
            tz = (body.timezone or "").strip()
            try:
                ZoneInfo(tz)
                patch["timezone"] = tz
            except (ZoneInfoNotFoundError, Exception):
                raise HTTPException(status_code=400, detail=f"Unknown timezone '{tz}'")
        for key in ("morning_briefing", "compliance_alerts", "payroll_reminder"):
            raw = getattr(body, key)
            if raw is None:
                continue
            clean: Dict[str, Any] = {}
            if "enabled" in raw:
                clean["enabled"] = bool(raw["enabled"])
            if "time" in raw and raw["time"] is not None:
                t = (str(raw["time"]) or "").strip()
                if not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", t):
                    raise HTTPException(status_code=400, detail=f"Invalid time '{t}' for {key} (expected HH:MM 24-hour)")
                clean["time"] = t
            if "days" in raw and raw["days"] is not None:
                days = [int(d) for d in raw["days"] if isinstance(d, (int, float)) or (isinstance(d, str) and d.isdigit())]
                days = sorted({d for d in days if 1 <= d <= 7})
                clean["days"] = days
            patch[key] = clean
        if not patch:
            return {"notifications": deps.notifications_for(user)}
        existing = user.get("notifications") or {}
        merged = {**existing}
        for k, v in patch.items():
            if k == "timezone":
                merged["timezone"] = v
            else:
                merged[k] = {**(existing.get(k) or {}), **v}
        await deps.db.users.update_one({"user_id": user["user_id"]}, {"$set": {"notifications": merged}})
        fresh = await deps.db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
        return {
            "notifications": deps.notifications_for(fresh),
            "telegram_linked": bool(fresh.get("telegram_chat_id")),
        }

    return router
