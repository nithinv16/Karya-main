import os
import io
import re
import html
import json
import uuid
import secrets
import base64
import asyncio
import logging
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from typing import Optional, List, Dict, Any
from urllib.parse import quote

import requests as http_requests
import feedparser
from fastapi import FastAPI, APIRouter, HTTPException, Depends, Request, Response, UploadFile, File, Form, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from pypdf import PdfReader
from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech
from twilio.rest import Client as TwilioClient
from twilio.base.exceptions import TwilioRestException

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("karya")

mongo_client = AsyncIOMotorClient(os.environ["MONGO_URL"])
db = mongo_client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
AUTH_SESSION_URL = "https://demobackend.emergentagent.com/auth/v1/env/oauth/session-data"
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
APP_NAME = "karya"

# Public backend URL for building absolute media URLs (used by Twilio WhatsApp).
# Falls back to the CORS origin list on startup if not explicitly set.
BACKEND_PUBLIC_URL = os.environ.get("BACKEND_PUBLIC_URL", "").rstrip("/")
if not BACKEND_PUBLIC_URL:
    # Derive from first non-localhost CORS origin as a reasonable default so signed
    # file URLs (used as Twilio media_url) work without extra configuration.
    for _o in [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",")]:
        if _o.startswith("https://") and "localhost" not in _o:
            BACKEND_PUBLIC_URL = _o.rstrip("/")
            break
FILE_URL_SIGNING_KEY = os.environ.get("FILE_URL_SIGNING_KEY", EMERGENT_LLM_KEY)  # stable per-env secret

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
# Empty env var must NOT override the sandbox default — os.environ.get("X", "default")
# returns "" (not the default) when X="" is present. So we normalise here.
TWILIO_WHATSAPP_FROM = (os.environ.get("TWILIO_WHATSAPP_FROM") or "").strip() or "whatsapp:+14155238886"
TWILIO_VERIFY_SERVICE_SID = os.environ.get("TWILIO_VERIFY_SERVICE_SID", "").strip()
TWILIO_VERIFY_SERVICE_NAME = (os.environ.get("TWILIO_VERIFY_SERVICE_NAME") or "").strip() or "Karya AI"
# Contact form recipient: a private Telegram username (never surfaced in UI).
# We watch inbound messages and cache the chat_id when this user pings the bot,
# then send /api/contact submissions to that chat_id. Falls back to email log.
CONTACT_TG_USERNAME = (os.environ.get("CONTACT_TG_USERNAME") or "").strip()
CONTACT_EMAIL = (os.environ.get("CONTACT_EMAIL") or "").strip() or "admin@dukaaon.in"
COMPANY_LEGAL_NAME = "SIXN8 Technologies Private Ltd"
# Auto-provisioned Verify Service SID (cached after first successful create/lookup).
_AUTO_VERIFY_SID: Optional[str] = None

def _twilio_client():
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        return None
    return TwilioClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


async def _get_verify_sid() -> Optional[str]:
    """Return a usable Twilio Verify Service SID.

    Preference order:
      1. TWILIO_VERIFY_SERVICE_SID env var (explicit)
      2. Previously auto-provisioned SID cached in memory / db.system_config
      3. A newly-created Verify Service (default name = TWILIO_VERIFY_SERVICE_NAME)
    Returns None only if Twilio itself isn't configured.
    """
    global _AUTO_VERIFY_SID
    if TWILIO_VERIFY_SERVICE_SID:
        return TWILIO_VERIFY_SERVICE_SID
    if _AUTO_VERIFY_SID:
        return _AUTO_VERIFY_SID
    tw = _twilio_client()
    if not tw:
        return None
    # 2) Check DB for a previously provisioned SID (survives restarts).
    cached = await db.system_config.find_one({"key": "twilio_verify_sid"})
    if cached and cached.get("value"):
        _AUTO_VERIFY_SID = cached["value"]
        return _AUTO_VERIFY_SID
    # 3) Look for an existing service with our name before creating a new one.
    try:
        services = await asyncio.to_thread(lambda: tw.verify.v2.services.list(limit=50))
        for s in services or []:
            if (getattr(s, "friendly_name", "") or "").strip() == TWILIO_VERIFY_SERVICE_NAME:
                _AUTO_VERIFY_SID = s.sid
                await db.system_config.update_one({"key": "twilio_verify_sid"}, {"$set": {"value": s.sid, "updated_at": now_iso()}}, upsert=True)
                logger.info(f"Reusing existing Twilio Verify Service '{TWILIO_VERIFY_SERVICE_NAME}' ({s.sid})")
                return _AUTO_VERIFY_SID
    except Exception as e:
        logger.warning(f"Twilio verify list failed: {e}")
    # 4) Create a fresh service.
    try:
        svc = await asyncio.to_thread(lambda: tw.verify.v2.services.create(friendly_name=TWILIO_VERIFY_SERVICE_NAME))
        _AUTO_VERIFY_SID = svc.sid
        await db.system_config.update_one({"key": "twilio_verify_sid"}, {"$set": {"value": svc.sid, "created_at": now_iso()}}, upsert=True)
        logger.info(f"Auto-provisioned Twilio Verify Service '{TWILIO_VERIFY_SERVICE_NAME}' ({svc.sid})")
        return _AUTO_VERIFY_SID
    except Exception as e:
        logger.error(f"Failed to auto-provision Twilio Verify Service: {e}")
        return None

def sign_file_path(path: str, expires_at: int) -> str:
    """HMAC-SHA256 signature for time-limited public file URLs."""
    import hmac
    import hashlib
    msg = f"{path}|{expires_at}".encode()
    return hmac.new(FILE_URL_SIGNING_KEY.encode(), msg, hashlib.sha256).hexdigest()[:32]

def build_signed_file_url(path: str, base_url: str, ttl_seconds: int = 3 * 24 * 3600) -> str:
    """Return an absolute URL to /api/files/<path> valid for `ttl_seconds`."""
    import time
    exp = int(time.time()) + ttl_seconds
    sig = sign_file_path(path, exp)
    return f"{base_url.rstrip('/')}/api/files/{path}?sig={sig}&exp={exp}"

app = FastAPI(title="Karya API")
api = APIRouter(prefix="/api")

ONBOARDING_KEYS = ["id_collected", "contract_signed", "induction_done", "site_access", "insurance", "bank_details"]
# Money the worker *earns* (owed to them). "payment" is now tracked separately as "paid".
EARN_TYPES = ["wage", "bonus"]
PAID_TYPES = ["payment"]
DEDUCT_TYPES = ["deduction", "food", "accommodation", "transport", "penalty"]

# ---------------------------------------------------------------- helpers

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def today_str():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")

def new_id():
    return str(uuid.uuid4())

def parse_json_block(text: str) -> dict:
    t = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.DOTALL)
    if m:
        t = m.group(1).strip()
    start, end = t.find("{"), t.rfind("}")
    if start != -1 and end != -1:
        t = t[start:end + 1]
    return json.loads(t)

async def ai_text(system: str, prompt: str, images: Optional[list] = None, provider: str = "anthropic", model: str = "claude-sonnet-4-6") -> str:
    last_err = None
    for attempt in range(3):
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"karya-{uuid.uuid4().hex[:10]}",
                system_message=system,
            ).with_model(provider, model)
            msg = UserMessage(text=prompt, file_contents=images) if images else UserMessage(text=prompt)
            resp = await chat.send_message(msg)
            return resp if isinstance(resp, str) else str(resp)
        except Exception as e:
            last_err = e
            logger.warning(f"AI attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(1.5 * (attempt + 1))
    raise HTTPException(status_code=502, detail=f"AI temporarily unavailable: {last_err}")

async def ai_json(system: str, prompt: str, images: Optional[list] = None, provider: str = "anthropic", model: str = "claude-sonnet-4-6") -> dict:
    for attempt in range(2):
        raw = await ai_text(system, prompt + "\nRespond with ONLY a valid JSON object, no prose.", images, provider=provider, model=model)
        try:
            return parse_json_block(raw)
        except Exception:
            continue
    raise HTTPException(status_code=502, detail="AI returned unparseable response")

def find_by_name(items: list, name: Optional[str]):
    if not name:
        return None
    n = name.lower().strip()
    for it in items:
        if it["name"].lower() == n:
            return it
    for it in items:
        if n in it["name"].lower() or it["name"].lower() in n:
            return it
    ntok = n.split()[0] if n.split() else n
    for it in items:
        toks = it["name"].lower().split()
        if toks and toks[0] == ntok:
            return it
    return None

# ---------------------------------------------------------------- object storage

_storage_key = None

def init_storage():
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = http_requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_LLM_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key

def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    resp = http_requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data, timeout=120,
    )
    resp.raise_for_status()
    return resp.json()

def get_object(path: str):
    key = init_storage()
    resp = http_requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=60)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# ---------------------------------------------------------------- auth

async def _resolve_user(token: Optional[str]) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    session = await db.user_sessions.find_one({"session_token": token}, {"_id": 0})
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session")
    expires_at = session["expires_at"]
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    user = await db.users.find_one({"user_id": session["user_id"]}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

async def get_current_user(request: Request) -> dict:
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    return await _resolve_user(token)

class SessionIn(BaseModel):
    session_id: str

@api.post("/auth/session")
async def create_session(body: SessionIn, response: Response):
    resp = http_requests.get(AUTH_SESSION_URL, headers={"X-Session-ID": body.session_id}, timeout=20)
    if resp.status_code != 200:
        logging.error(
            f"[auth/session] Emergent returned {resp.status_code}: {resp.text[:500]} | "
            f"session_id={body.session_id!r} (len={len(body.session_id)}) | url={AUTH_SESSION_URL}"
        )
        raise HTTPException(status_code=401, detail=f"emergent_{resp.status_code}: {resp.text[:200]}")
    data = resp.json()
    user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    if not user:
        user = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": data["email"],
            "name": data.get("name", ""),
            "picture": data.get("picture", ""),
            "company_name": f"{(data.get('name') or 'My').split()[0]}'s Construction Co.",
            "phone": "",
            "address": "",
            "role": "",
            "default_client_phone": "",
            "profile_complete": False,
            "created_at": now_iso(),
        }
        await db.users.insert_one({**user})
        user.pop("_id", None)
    else:
        await db.users.update_one({"email": data["email"]}, {"$set": {"name": data.get("name", user["name"]), "picture": data.get("picture", user.get("picture", ""))}})
        user["name"] = data.get("name", user["name"])
        user["picture"] = data.get("picture", user.get("picture", ""))
    token = data["session_token"]
    await db.user_sessions.insert_one({
        "user_id": user["user_id"],
        "session_token": token,
        "expires_at": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "created_at": now_iso(),
    })
    response.set_cookie("session_token", token, httponly=True, secure=True, samesite="none", path="/", max_age=7 * 24 * 3600)
    # Also return the token in the body so the frontend can use Authorization: Bearer
    # (needed when the frontend is on a different Emergent preview origin — the
    # platform ingress rewrites CORS to `*` which blocks credentialed cookies).
    return {**user, "session_token": token}

@api.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return user

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok": True}


class ProfileIn(BaseModel):
    name: str
    phone: str = ""
    address: str = ""
    company_name: str = ""
    role: str = ""
    default_client_phone: str = ""
    country: str = "IN"  # IN | AE
    language: str = "en"  # en | ar (RTL when 'ar' + country='AE')
    ramadan_mode: bool = False  # 6h shifts + prayer breaks in attendance


# ---------------- Localization / country context (India + UAE) --------------
COUNTRY_META = {
    "IN": {
        "name": "India",
        "currency_code": "INR",
        "currency_symbol": "₹",
        "locale": "en-IN",
        "rate_types": ["daily", "weekly", "monthly", "contract", "sqft", "task", "milestone", "piece"],
        "compliance_categories": [
            "permit", "license", "insurance", "registration", "safety",
            "tender", "labour", "gst", "municipal", "environment"
        ],
        "compliance_seed": [
            {"title": "BOCW Cess Payment", "category": "labour", "note": "Building & Other Construction Workers Welfare Cess — 1% of construction cost, monthly."},
            {"title": "GST Return (GSTR-1 / 3B)", "category": "gst", "note": "Monthly outward supplies + summary."},
            {"title": "Labour License Renewal", "category": "license", "note": "State labour department, per project or annual."},
            {"title": "Contract Labour Registration (CLRA)", "category": "labour", "note": "If ≥20 contract workers, register with the state labour commissioner."},
            {"title": "Factories Act / Shops & Establishments", "category": "registration", "note": "State-level registration for the office/site."},
            {"title": "ESIC / EPFO Compliance", "category": "labour", "note": "Monthly employee state insurance and provident fund filings."},
        ],
        "news_hl": "en-IN",
        "news_gl": "IN",
        "news_ceid": "IN:en",
        "context_prompt": "You are advising a small/mid-size construction contractor operating in India. Reference Indian statutes: BOCW Act, Contract Labour (R&A) Act, Factories Act, ESI, EPF, GST, RERA, state labour laws, municipal PWD/CPWD tenders. Use INR (₹) for money. Cite typical Indian penalty ranges.",
    },
    "AE": {
        "name": "United Arab Emirates",
        "currency_code": "AED",
        "currency_symbol": "AED",
        "locale": "en-AE",
        "rate_types": ["hourly", "daily", "weekly", "monthly", "contract", "sqm", "task", "milestone", "piece"],
        "compliance_categories": [
            "trade_license", "labour_card", "emirates_id", "visa",
            "wps", "civil_defense", "municipality_noc", "tasheel",
            "insurance", "safety", "environment", "tender"
        ],
        "compliance_seed": [
            {"title": "DED Trade License Renewal", "category": "trade_license", "note": "Annual renewal via Department of Economic Development (Dubai) or equivalent authority in each emirate."},
            {"title": "MOHRE Labour Cards", "category": "labour_card", "note": "Ministry of Human Resources & Emiratisation — issued/renewed per worker."},
            {"title": "Emirates ID renewal — workforce", "category": "emirates_id", "note": "Federal Authority for Identity & Citizenship — verify every worker's ID validity."},
            {"title": "Residence Visa expiry monitoring", "category": "visa", "note": "GDRFA (Dubai) / ICP — 30-day pre-alert per worker."},
            {"title": "WPS (Wage Protection System)", "category": "wps", "note": "MOHRE WPS — monthly salary transfer via approved bank/exchange, on-time."},
            {"title": "Civil Defense NOC (site fire safety)", "category": "civil_defense", "note": "Per project — required before commencement and at handover."},
            {"title": "Municipality Building Permit / NOC", "category": "municipality_noc", "note": "Dubai Municipality / Abu Dhabi DMT — permit approval and inspections."},
            {"title": "Tas'heel Service Center forms", "category": "tasheel", "note": "Labour contract, offer letters, and MOHRE submissions."},
        ],
        "news_hl": "en-AE",
        "news_gl": "AE",
        "news_ceid": "AE:en",
        "context_prompt": "You are advising a small/mid-size construction contractor operating in the United Arab Emirates. Reference UAE regulations: MOHRE (labour ministry) rules, WPS (Wage Protection System), Emirates ID/GDRFA visa rules, DED trade license, Dubai/Abu Dhabi Municipality permits, Civil Defense NOC, Tas'heel forms, DIFC free zone rules where relevant. Use AED for money. Cite typical UAE fine ranges (e.g. WPS delay AED 5,000 per employee/month; expired labour card AED 500-1,000/worker; visa overstay AED 50/day).",
    },
}


def user_country(user: dict) -> str:
    """Return the country code for the current user, defaulting to India."""
    c = (user or {}).get("country") or "IN"
    return c if c in COUNTRY_META else "IN"


def country_ctx(user_or_country) -> dict:
    code = user_or_country if isinstance(user_or_country, str) else user_country(user_or_country)
    return COUNTRY_META.get(code, COUNTRY_META["IN"])


def money_str(amount, user_or_country) -> str:
    m = country_ctx(user_or_country)
    n = int(amount or 0)
    if m["currency_code"] == "INR":
        return f"₹{n:,}"
    return f"AED {n:,}"


@api.get("/config/countries")
async def get_countries():
    return {code: {"name": m["name"], "currency_code": m["currency_code"], "currency_symbol": m["currency_symbol"],
                    "locale": m["locale"], "rate_types": m["rate_types"], "compliance_categories": m["compliance_categories"]}
            for code, m in COUNTRY_META.items()}


@api.put("/auth/profile")
async def update_profile(body: ProfileIn, user: dict = Depends(get_current_user)):
    patch = body.model_dump()
    if patch.get("country") not in COUNTRY_META:
        patch["country"] = "IN"
    patch["profile_complete"] = bool(patch["name"].strip() and patch["phone"].strip())
    prev = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0}) or {}
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": patch})
    # First-time country selection seeds a country-appropriate compliance starter kit.
    just_completed = (not prev.get("profile_complete")) and patch["profile_complete"]
    if just_completed:
        seed = country_ctx(patch["country"]).get("compliance_seed", [])
        if seed and await db.compliance.count_documents({"owner_id": user["user_id"]}) == 0:
            for s in seed:
                await db.compliance.insert_one({
                    "id": new_id(), "owner_id": user["user_id"], "title": s["title"], "category": s["category"],
                    "due_date": "", "expiry_date": "", "project_ids": [], "status": "pending",
                    "document_text": "", "attachments": [], "analysis": None, "renewal_plan": None,
                    "penalty_estimate": None,
                    "history": [{"action": "seeded", "at": now_iso(), "note": f"country={patch['country']}"}],
                    "notes": s.get("note", ""), "created_at": now_iso(),
                })
    updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return updated


class LanguageIn(BaseModel):
    language: str


_SUPPORTED_LANGS = {"en", "hi", "ml", "ta", "te"}


@api.patch("/auth/profile/language")
async def update_profile_language(body: LanguageIn, user: dict = Depends(get_current_user)):
    """Lightweight language-only update (bypasses required ProfileIn fields).
    Frontend calls this from the Profile language switcher to avoid a 422 on
    profiles that haven't been fully filled in yet."""
    lang = (body.language or "").strip().lower()
    if lang not in _SUPPORTED_LANGS:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'. Supported: {sorted(_SUPPORTED_LANGS)}")
    await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"language": lang}})
    updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return updated


# ---------------------------------------------------------------- phone verification (Twilio Verify)

_E164 = re.compile(r"^\+[1-9]\d{7,14}$")

def _normalize_phone(p: str) -> str:
    if not p:
        return ""
    s = "".join(ch for ch in p.strip() if ch.isdigit() or ch == "+")
    if s and not s.startswith("+"):
        s = "+" + s
    return s


class PhoneVerifyStartIn(BaseModel):
    phone: str


class PhoneVerifyCheckIn(BaseModel):
    phone: str
    code: str


@api.post("/profile/phone/verify/start")
async def phone_verify_start(body: PhoneVerifyStartIn, user: dict = Depends(get_current_user)):
    tw = _twilio_client()
    if not tw:
        raise HTTPException(status_code=503, detail="Phone verification is not configured on this server.")
    verify_sid = await _get_verify_sid()
    if not verify_sid:
        raise HTTPException(status_code=503, detail="Phone verification service unavailable. Please try again in a moment.")
    phone = _normalize_phone(body.phone)
    if not _E164.match(phone):
        raise HTTPException(status_code=400, detail="Enter your phone in international format, e.g. +919876543210 or +971501234567.")
    try:
        v = await asyncio.to_thread(
            lambda: tw.verify.v2.services(verify_sid).verifications.create(to=phone, channel="sms")
        )
    except TwilioRestException as e:
        msg = getattr(e, "msg", None) or str(e)
        raise HTTPException(status_code=400, detail=f"Couldn't send code: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Verify start failed: {e}")
    return {"status": v.status, "phone": phone}


@api.post("/profile/phone/verify/check")
async def phone_verify_check(body: PhoneVerifyCheckIn, user: dict = Depends(get_current_user)):
    tw = _twilio_client()
    if not tw:
        raise HTTPException(status_code=503, detail="Phone verification is not configured on this server.")
    verify_sid = await _get_verify_sid()
    if not verify_sid:
        raise HTTPException(status_code=503, detail="Phone verification service unavailable. Please try again in a moment.")
    phone = _normalize_phone(body.phone)
    code = (body.code or "").strip()
    if not _E164.match(phone) or not code:
        raise HTTPException(status_code=400, detail="Phone or code missing.")
    try:
        check = await asyncio.to_thread(
            lambda: tw.verify.v2.services(verify_sid).verification_checks.create(to=phone, code=code)
        )
    except TwilioRestException as e:
        msg = getattr(e, "msg", None) or str(e)
        raise HTTPException(status_code=400, detail=f"Couldn't verify: {msg}")
    approved = getattr(check, "status", None) == "approved"
    if not approved:
        return {"verified": False, "status": getattr(check, "status", "pending")}
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"phone": phone, "phone_verified": True, "phone_verified_at": now_iso()}},
    )
    updated = await db.users.find_one({"user_id": user["user_id"]}, {"_id": 0})
    return {"verified": True, "user": updated}


@api.get("/profile/phone/verify/status")
async def phone_verify_status(user: dict = Depends(get_current_user)):
    tw_ok = bool(_twilio_client())
    verify_sid: Optional[str] = None
    if tw_ok:
        try:
            verify_sid = await _get_verify_sid()
        except Exception:
            verify_sid = None
    return {
        "verify_available": tw_ok and bool(verify_sid),
        "phone": user.get("phone", "") or "",
        "phone_verified": bool(user.get("phone_verified")),
    }


# ---------------------------------------------------------------- projects & workers

class ProjectIn(BaseModel):
    name: str
    location: str = ""
    client: str = ""
    client_phone: str = ""
    budget: float = 0

class WorkerIn(BaseModel):
    name: str
    role: str = "Labour"
    phone: str = ""
    rate: float = 0
    rate_type: str = "daily"
    project_id: Optional[str] = None
    subcontractor: str = ""

class OnboardingIn(BaseModel):
    onboarding: Dict[str, bool]

@api.get("/projects")
async def list_projects(user: dict = Depends(get_current_user)):
    return await db.projects.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/projects")
async def create_project(body: ProjectIn, user: dict = Depends(get_current_user)):
    doc = {"id": new_id(), "owner_id": user["user_id"], **body.model_dump(), "created_at": now_iso()}
    await db.projects.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.get("/projects/{project_id}")
async def get_project(project_id: str, user: dict = Depends(get_current_user)):
    project = await db.projects.find_one({"id": project_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    worker_count = await db.workers.count_documents({"project_id": project_id, "owner_id": user["user_id"]})
    return {**project, "worker_count": worker_count}

@api.put("/projects/{project_id}")
async def update_project(project_id: str, body: ProjectIn, user: dict = Depends(get_current_user)):
    res = await db.projects.update_one(
        {"id": project_id, "owner_id": user["user_id"]},
        {"$set": body.model_dump()},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    updated = await db.projects.find_one({"id": project_id, "owner_id": user["user_id"]}, {"_id": 0})
    return updated

@api.delete("/projects/{project_id}")
async def delete_project(project_id: str, user: dict = Depends(get_current_user)):
    res = await db.projects.delete_one({"id": project_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Project not found")
    # Unassign workers from the deleted project (don't delete workers themselves).
    await db.workers.update_many(
        {"project_id": project_id, "owner_id": user["user_id"]},
        {"$set": {"project_id": None}},
    )
    return {"deleted": True}

@api.get("/workers")
async def list_workers(user: dict = Depends(get_current_user)):
    return await db.workers.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api.post("/workers")
async def create_worker(body: WorkerIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": new_id(), "owner_id": user["user_id"], **body.model_dump(),
        "onboarding": {k: False for k in ONBOARDING_KEYS}, "created_at": now_iso(),
    }
    await db.workers.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.delete("/workers/{worker_id}")
async def delete_worker(worker_id: str, user: dict = Depends(get_current_user)):
    res = await db.workers.delete_one({"id": worker_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Worker not found")
    await db.transactions.delete_many({"worker_id": worker_id, "owner_id": user["user_id"]})
    await db.attendance.delete_many({"worker_id": worker_id, "owner_id": user["user_id"]})
    return {"ok": True}

@api.post("/workers/{worker_id}/onboarding")
async def update_onboarding(worker_id: str, body: OnboardingIn, user: dict = Depends(get_current_user)):
    ob = {k: bool(body.onboarding.get(k, False)) for k in ONBOARDING_KEYS}
    res = await db.workers.update_one({"id": worker_id, "owner_id": user["user_id"]}, {"$set": {"onboarding": ob}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Worker not found")
    return await db.workers.find_one({"id": worker_id}, {"_id": 0})


# ---------------------------------------------------------------- attendance
# CRUD endpoints have been moved to routes/attendance.py. The Telegram
# /attendance command handler below still calls the extracted core helpers
# via server-level shims wired in the mount block.
from routes.attendance import (
    AttendanceMarkIn, AttendanceHeadcountIn,
    mark_attendance_core as _mark_attendance_core,
    headcount_attendance_core as _headcount_attendance_core,
    Deps as _AttendanceDeps,
)

_ATTENDANCE_DEPS_LAZY: Optional[_AttendanceDeps] = None


def _attendance_deps() -> _AttendanceDeps:
    """Lazy: db/helpers are defined earlier in this module; build once."""
    global _ATTENDANCE_DEPS_LAZY
    if _ATTENDANCE_DEPS_LAZY is None:
        _ATTENDANCE_DEPS_LAZY = _AttendanceDeps(
            db=db, get_current_user=get_current_user,
            new_id=new_id, now_iso=now_iso, today_str=today_str,
        )
    return _ATTENDANCE_DEPS_LAZY


async def mark_attendance(body: AttendanceMarkIn, user: dict):  # shim for Telegram handler
    return await _mark_attendance_core(_attendance_deps(), body, user)


async def headcount_attendance(body: AttendanceHeadcountIn, user: dict):  # shim for Telegram handler
    return await _headcount_attendance_core(_attendance_deps(), body, user)


# ---------------------------------------------------------------- transactions & ledger

class TxnIn(BaseModel):
    worker_id: str
    type: str
    amount: float
    note: str = ""

def ledger_summary(txns: list) -> dict:
    earned = sum(t["amount"] for t in txns if t["type"] in EARN_TYPES)
    advances = sum(t["amount"] for t in txns if t["type"] == "advance")
    deductions = sum(t["amount"] for t in txns if t["type"] in DEDUCT_TYPES)
    paid = sum(t["amount"] for t in txns if t["type"] in PAID_TYPES)
    # Net payable = earnings minus what worker already received (paid/advances) and any deductions.
    return {
        "earned": earned,
        "advances": advances,
        "deductions": deductions,
        "paid": paid,
        "balance": earned - advances - deductions - paid,
    }

@api.get("/transactions")
async def list_transactions(user: dict = Depends(get_current_user)):
    return await db.transactions.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5000)

@api.post("/transactions")
async def create_transaction(body: TxnIn, user: dict = Depends(get_current_user)):
    worker = await db.workers.find_one({"id": body.worker_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    doc = {"id": new_id(), "owner_id": user["user_id"], **body.model_dump(), "date": today_str(), "created_at": now_iso()}
    await db.transactions.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.get("/workers/{worker_id}/ledger")
async def worker_ledger(worker_id: str, user: dict = Depends(get_current_user)):
    worker = await db.workers.find_one({"id": worker_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    txns = await db.transactions.find({"worker_id": worker_id, "owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return {**ledger_summary(txns), "transactions": txns, "worker": worker}

# ---------------------------------------------------------------- subcontractors

class SubIn(BaseModel):
    name: str
    firm: str = ""
    trade: str = ""
    project_id: Optional[str] = None
    contact: str = ""
    contract_value: float = 0
    retention_percent: float = 0

class SubTxnIn(BaseModel):
    type: str
    amount: float
    note: str = ""

def sub_summary(sub: dict, txns: list) -> dict:
    extra = sum(t["amount"] for t in txns if t["type"] == "extra_work")
    material = sum(t["amount"] for t in txns if t["type"] == "material")
    deductions = sum(t["amount"] for t in txns if t["type"] == "deduction")
    released = sum(t["amount"] for t in txns if t["type"] == "retention_release")
    paid = sum(t["amount"] for t in txns if t["type"] in ("payment", "advance"))
    gross = sub.get("contract_value", 0) + extra
    retention_held = max(0, gross * sub.get("retention_percent", 0) / 100 - released)
    net_payable = gross - material - deductions - retention_held
    return {
        "contract_value": sub.get("contract_value", 0), "extra_work": extra, "gross": gross,
        "material_recovered": material, "deductions": deductions, "retention_held": retention_held,
        "net_payable": net_payable, "paid": paid, "pending": net_payable - paid,
    }

@api.get("/subcontractors")
async def list_subs(user: dict = Depends(get_current_user)):
    subs = await db.subcontractors.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)
    if not subs:
        return []
    # Single bulk query instead of one round-trip per sub (was N+1).
    sub_ids = [s["id"] for s in subs]
    all_txns = await db.sub_transactions.find({"sub_id": {"$in": sub_ids}}, {"_id": 0}).to_list(20000)
    by_sub: Dict[str, List[dict]] = {}
    for t in all_txns:
        by_sub.setdefault(t.get("sub_id"), []).append(t)
    return [{**s, "summary": sub_summary(s, by_sub.get(s["id"], []))} for s in subs]

@api.post("/subcontractors")
async def create_sub(body: SubIn, user: dict = Depends(get_current_user)):
    doc = {"id": new_id(), "owner_id": user["user_id"], **body.model_dump(), "created_at": now_iso()}
    await db.subcontractors.insert_one({**doc})
    doc.pop("_id", None)
    return {**doc, "summary": sub_summary(doc, [])}

@api.get("/subcontractors/{sub_id}")
async def get_sub(sub_id: str, user: dict = Depends(get_current_user)):
    sub = await db.subcontractors.find_one({"id": sub_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Subcontractor not found")
    txns = await db.sub_transactions.find({"sub_id": sub_id}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    return {**sub, "summary": sub_summary(sub, txns), "transactions": txns}

@api.delete("/subcontractors/{sub_id}")
async def delete_sub(sub_id: str, user: dict = Depends(get_current_user)):
    res = await db.subcontractors.delete_one({"id": sub_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subcontractor not found")
    await db.sub_transactions.delete_many({"sub_id": sub_id})
    return {"ok": True}

@api.post("/subcontractors/{sub_id}/transactions")
async def create_sub_txn(sub_id: str, body: SubTxnIn, user: dict = Depends(get_current_user)):
    if body.amount <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero")
    sub = await db.subcontractors.find_one({"id": sub_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not sub:
        raise HTTPException(status_code=404, detail="Subcontractor not found")
    doc = {"id": new_id(), "owner_id": user["user_id"], "sub_id": sub_id, **body.model_dump(), "date": today_str(), "created_at": now_iso()}
    await db.sub_transactions.insert_one({**doc})
    doc.pop("_id", None)
    return doc

# ---------------------------------------------------------------- files

TEXT_EXTRACT_LIMIT = 6000

def extract_text(data: bytes, content_type: str, filename: str) -> str:
    try:
        if "pdf" in (content_type or "") or filename.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(data))
            text = "\n".join((p.extract_text() or "") for p in reader.pages[:10])
            return text.strip()[:TEXT_EXTRACT_LIMIT]
        if (content_type or "").startswith("text/") or filename.lower().endswith(".txt"):
            return data.decode("utf-8", errors="ignore").strip()[:TEXT_EXTRACT_LIMIT]
    except Exception as e:
        logger.warning(f"Text extraction failed: {e}")
    return ""

@api.post("/files/upload")
async def upload_file(file: UploadFile = File(...), user: dict = Depends(get_current_user)):
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 20MB)")
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in (file.filename or "") else "bin"
    path = f"{APP_NAME}/uploads/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
    result = await asyncio.to_thread(put_object, path, data, file.content_type or "application/octet-stream")
    rec = {
        "id": new_id(), "owner_id": user["user_id"], "path": result["path"],
        "filename": file.filename, "content_type": file.content_type or "application/octet-stream",
        "size": result.get("size", len(data)),
        "extracted_text": extract_text(data, file.content_type or "", file.filename or ""),
        "is_deleted": False, "created_at": now_iso(),
    }
    await db.files.insert_one({**rec})
    rec.pop("_id", None)
    return rec

@api.get("/files/{path:path}")
async def download_file(
    path: str,
    request: Request,
    auth: Optional[str] = Query(None),
    sig: Optional[str] = Query(None),
    exp: Optional[int] = Query(None),
):
    # Path 1: valid HMAC-signed URL (used by Twilio to fetch media). No auth needed.
    if sig and exp:
        import time
        import hmac as _hmac
        if exp > int(time.time()) and _hmac.compare_digest(sig, sign_file_path(path, exp)):
            rec = await db.files.find_one({"path": path, "is_deleted": False}, {"_id": 0})
            if rec:
                data, ct = await asyncio.to_thread(get_object, path)
                return Response(content=data, media_type=rec.get("content_type") or ct)
        raise HTTPException(status_code=403, detail="Invalid or expired signature")

    # Path 2: session-bound access (cookie, bearer, or ?auth=<token>).
    token = request.cookies.get("session_token")
    if not token:
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
    if not token and auth:
        token = auth
    user = await _resolve_user(token)
    rec = await db.files.find_one({"path": path, "owner_id": user["user_id"], "is_deleted": False}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="File not found")
    data, ct = await asyncio.to_thread(get_object, path)
    return Response(content=data, media_type=rec.get("content_type") or ct)

# ---- rate limiter -----------------------------------------------------------
# In-process sliding window. Fine for our single-pod deployment; migrate to
# Redis if we ever scale out horizontally.
_RATE_BUCKETS: Dict[str, List[float]] = {}
_RATE_LOCK = asyncio.Lock()


async def rate_limit(key: str, limit: int, window_seconds: int):
    """Raise HTTP 429 if `key` has exceeded `limit` calls in `window_seconds`."""
    import time as _time
    now = _time.monotonic()
    cutoff = now - window_seconds
    async with _RATE_LOCK:
        hits = [t for t in _RATE_BUCKETS.get(key, []) if t > cutoff]
        if len(hits) >= limit:
            retry_after = max(1, int(window_seconds - (now - hits[0])))
            raise HTTPException(
                status_code=429,
                detail="Too many requests. Please slow down.",
                headers={"Retry-After": str(retry_after)},
            )
        hits.append(now)
        _RATE_BUCKETS[key] = hits
        # Occasional GC: drop keys older than any window we care about.
        if len(_RATE_BUCKETS) > 5000:
            for k in list(_RATE_BUCKETS.keys()):
                if not _RATE_BUCKETS[k] or _RATE_BUCKETS[k][-1] < now - 3600:
                    _RATE_BUCKETS.pop(k, None)



@api.post("/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...), language: str = Form("auto"), user: dict = Depends(get_current_user)):
    # 30 transcriptions / minute per user — well above realistic use, cheap to bypass abuse.
    await rate_limit(f"stt:{user['user_id']}", limit=30, window_seconds=60)
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio")
    # Guard-rail: 25 MB is OpenAI Whisper's own limit; reject earlier so the
    # ingress doesn't 504 on huge uploads.
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio too large (25MB max)")
    buf = io.BytesIO(data)
    buf.name = file.filename or "clip.webm"
    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    kwargs: Dict[str, Any] = {}
    if language and language != "auto":
        kwargs["language"] = language
    # 2 attempts with a short backoff — we're behind a 60s ingress and a longer
    # loop just guarantees a 504 to the browser. Fail fast, let the UI retry.
    last_err: Optional[Exception] = None
    for attempt in range(2):
        try:
            buf.seek(0)
            resp = await asyncio.wait_for(
                stt.transcribe(file=buf, model="whisper-1", response_format="json", **kwargs),
                timeout=25,
            )
            return {"text": (resp.text or "").strip()}
        except asyncio.TimeoutError:
            last_err = Exception("upstream timeout")
        except Exception as e:
            last_err = e
        if attempt == 0:
            await asyncio.sleep(0.6)
    logger.warning(f"voice_transcribe failed: {last_err}")
    raise HTTPException(status_code=502, detail="Transcription temporarily unavailable. Please try again.")

# ---------------------------------------------------------------- NL command

class CommandIn(BaseModel):
    text: str

COMMAND_SYSTEM = """You parse natural-language commands for a construction operations platform in India.
Commands may be in English, Hindi, Tamil, Malayalam, Kannada, Telugu, Marathi or Bengali (or transliterated).
Classify into one intent and extract fields. Output JSON:
{"intent": "add_worker|advance|payment|bonus|deduction|attendance|log_work_days|complete_task|unknown",
 "worker_name": str|null, "project_name": str|null, "amount": number|null, "role": str|null,
 "rate": number|null, "rate_type": "daily|weekly|monthly|contract|sqft|task|milestone|piece"|null,
 "count": number|null, "days": number|null, "quantity": number|null, "unit": str|null, "note": str|null}
Rules:
- "X took an advance of 5000" -> advance
- "Pay X 12000" -> payment
- "Ten workers arrived today at <project>" -> attendance with count
- "Add worker X as mason at 950 daily" -> add_worker
- "X worked 8 days" -> log_work_days
- "X completed 200 sqft tiling" -> complete_task with quantity and unit
- Amounts may use ₹, Rs, rupees, k (5k=5000), lakh (1 lakh=100000)."""

@api.post("/command")
async def run_command(body: CommandIn, user: dict = Depends(get_current_user)):
    return await _execute_command(body.text, user)


async def _execute_command(text: str, user: dict) -> dict:
    """Shared NL → action executor. Reused by /command HTTP endpoint AND Telegram intake."""
    uid = user["user_id"]
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(500)
    prompt = (
        f"Known workers: {', '.join(w['name'] for w in workers) or 'none'}\n"
        f"Known projects: {', '.join(p['name'] for p in projects) or 'none'}\n"
        f"Command: {text}"
    )
    try:
        parsed = await ai_json(COMMAND_SYSTEM, prompt)
    except HTTPException:
        return {"applied": False, "summary": "Couldn't reach the AI parser. Try again."}
    intent = parsed.get("intent", "unknown")

    money = _money_fn(user)

    if intent == "add_worker":
        name = parsed.get("worker_name") or parsed.get("note")
        if not name:
            return {"applied": False, "summary": "Couldn't identify the worker's name."}
        proj = find_by_name(projects, parsed.get("project_name"))
        doc = {
            "id": new_id(), "owner_id": uid, "name": name, "role": parsed.get("role") or "Labour",
            "phone": "", "rate": float(parsed.get("rate") or 0), "rate_type": parsed.get("rate_type") or "daily",
            "project_id": proj["id"] if proj else None, "subcontractor": "",
            "onboarding": {k: False for k in ONBOARDING_KEYS}, "created_at": now_iso(),
        }
        await db.workers.insert_one({**doc})
        return {"applied": True, "summary": f"Added {name} as {doc['role']} at ₹{int(doc['rate'])}/{doc['rate_type']}."}

    if intent in ("advance", "payment", "bonus", "deduction"):
        worker = find_by_name(workers, parsed.get("worker_name"))
        if not worker:
            return {"applied": False, "summary": f"Couldn't find worker \"{parsed.get('worker_name') or '?'}\". Add them first."}
        amount = float(parsed.get("amount") or 0)
        if amount <= 0:
            return {"applied": False, "summary": "Couldn't understand the amount."}
        await db.transactions.insert_one({
            "id": new_id(), "owner_id": uid, "worker_id": worker["id"], "type": intent,
            "amount": amount, "note": parsed.get("note") or f"Via command: {text[:80]}",
            "date": today_str(), "created_at": now_iso(),
        })
        return {"applied": True, "summary": f"Recorded {intent} of {money(amount)} for {worker['name']}."}

    if intent == "attendance":
        proj = find_by_name(projects, parsed.get("project_name"))
        count = int(parsed.get("count") or 1)
        worker = find_by_name(workers, parsed.get("worker_name"))
        await db.attendance.insert_one({
            "id": new_id(), "owner_id": uid, "worker_id": worker["id"] if worker else None,
            "project_id": proj["id"] if proj else None, "date": today_str(), "count": count if not worker else 1,
            "created_at": now_iso(),
        })
        where = f" at {proj['name']}" if proj else ""
        who = worker["name"] if worker else f"{count} workers"
        return {"applied": True, "summary": f"Marked {who} present today{where}."}

    if intent == "log_work_days":
        worker = find_by_name(workers, parsed.get("worker_name"))
        if not worker:
            return {"applied": False, "summary": f"Couldn't find worker \"{parsed.get('worker_name') or '?'}\"."}
        days = int(parsed.get("days") or 1)
        wage = days * float(worker.get("rate") or 0)
        await db.attendance.insert_one({
            "id": new_id(), "owner_id": uid, "worker_id": worker["id"], "project_id": worker.get("project_id"),
            "date": today_str(), "count": days, "created_at": now_iso(),
        })
        if wage > 0:
            await db.transactions.insert_one({
                "id": new_id(), "owner_id": uid, "worker_id": worker["id"], "type": "wage",
                "amount": wage, "note": f"{days} day(s) work", "date": today_str(), "created_at": now_iso(),
            })
        return {"applied": True, "summary": f"Logged {days} day(s) for {worker['name']} — wage {money(wage)}."}

    if intent == "complete_task":
        worker = find_by_name(workers, parsed.get("worker_name"))
        if not worker:
            return {"applied": False, "summary": f"Couldn't find worker \"{parsed.get('worker_name') or '?'}\"."}
        qty = float(parsed.get("quantity") or 0)
        rate = float(parsed.get("rate") or worker.get("rate") or 0)
        wage = qty * rate if qty > 0 and worker.get("rate_type") in ("sqft", "task", "piece", "milestone", "contract") else float(parsed.get("amount") or qty * rate)
        if wage > 0:
            await db.transactions.insert_one({
                "id": new_id(), "owner_id": uid, "worker_id": worker["id"], "type": "wage",
                "amount": wage, "note": f"Task: {parsed.get('note') or text[:80]}", "date": today_str(), "created_at": now_iso(),
            })
        await db.knowledge.insert_one({
            "id": new_id(), "owner_id": uid, "title": f"Task completed — {worker['name']}",
            "content": text, "project_id": worker.get("project_id"), "tags": ["task", "command"],
            "created_at": now_iso(),
        })
        return {"applied": True, "summary": f"Logged task for {worker['name']}" + (f" — wage {money(wage)}." if wage > 0 else ".")}

    return {"applied": False, "unknown": True, "summary": "I couldn't understand that command. Try e.g. \"Ramesh took an advance of ₹5000\"."}

# ---------------------------------------------------------------- telegram intake

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_WEBHOOK_SECRET = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "").strip()
TG_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
TG_FILE_API = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}"


class TgLinkResponse(BaseModel):
    code: str
    bot_username: Optional[str] = None
    deep_link: Optional[str] = None


def _tg_configured() -> bool:
    return bool(TELEGRAM_BOT_TOKEN)


async def tg_api(method: str, payload: dict) -> dict:
    """Fire a Telegram Bot API call. Returns the JSON body (or empty dict on failure)."""
    if not _tg_configured():
        return {}
    try:
        r = await asyncio.to_thread(
            http_requests.post, f"{TG_API}/{method}", json=payload, timeout=15,
        )
        return r.json() if r.content else {}
    except Exception as e:
        logger.warning(f"tg_api {method} failed: {e}")
        return {}


# --- Voice-reply context: when the user sent a voice note, we mirror our text
# replies as spoken audio via OpenAI TTS. A ContextVar propagates the flag
# through async chains so we don't have to thread a parameter through every
# nested handler.
from contextvars import ContextVar
_TG_SPEAK: ContextVar[bool] = ContextVar("tg_speak", default=False)
# When we know which linked user we're replying to (set in the webhook after
# resolving chat_id → user), every tg_send() call translates the outgoing text
# into user.language before shipping to Telegram. English-preferring users pay
# no LLM overhead — translate_text() short-circuits when target is 'en'.
_TG_USER_LANG: ContextVar[str] = ContextVar("tg_user_lang", default="en")

# Strip HTML tags + common markdown so TTS speaks clean prose
_HTML_STRIP = re.compile(r"<[^>]+>")
_MD_EMPH = re.compile(r"[*_`]{1,3}")


def _for_tts(text: str) -> str:
    if not text:
        return ""
    s = _HTML_STRIP.sub("", text)
    s = _MD_EMPH.sub("", s)
    # Common shorthand → speakable
    s = s.replace("—", ", ").replace("•", ", ").replace("\n", ". ")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:600]  # keep TTS calls short (cost + latency)


async def tg_send_voice(chat_id: int, audio_bytes: bytes, filename: str = "reply.ogg"):
    """Upload a voice note (opus) to Telegram via multipart sendVoice."""
    if not _tg_configured() or not audio_bytes:
        return {}
    try:
        files = {"voice": (filename, audio_bytes, "audio/ogg")}
        data = {"chat_id": str(chat_id)}
        r = await asyncio.to_thread(
            http_requests.post, f"{TG_API}/sendVoice", data=data, files=files, timeout=30,
        )
        return r.json() if r.content else {}
    except Exception as e:
        logger.warning(f"tg sendVoice failed: {e}")
        return {}


async def tg_speak(chat_id: int, text: str, lang: str = "en"):
    """Synthesize `text` to speech via OpenAI TTS and forward as a Telegram voice note."""
    spoken = _for_tts(text)
    if not spoken or not EMERGENT_LLM_KEY:
        return
    try:
        tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
        # nova = warm/upbeat, good for confirmations. Opus is Telegram's native voice format.
        audio_bytes = await tts.generate_speech(
            text=spoken, model="tts-1", voice="nova", response_format="opus",
        )
        await tg_send_voice(chat_id, audio_bytes)
    except Exception as e:
        logger.warning(f"tg tts failed: {e}")


async def tg_send(chat_id: int, text: str, reply_markup: Optional[dict] = None):
    # Translate outgoing reply to the linked user's language when we know it.
    # Skip very short strings (confirmations, echoes, ✅ acks) — they don't warrant
    # an LLM roundtrip and often contain proper nouns we'd rather not translate.
    lang = _TG_USER_LANG.get()
    stripped = (text or "").strip()
    if lang and lang != "en" and len(stripped) >= 40:
        try:
            text = await translate_text(text, lang, context="Telegram bot reply for a construction contractor")
        except Exception as e:
            logger.warning(f"tg_send translate failed for lang={lang}: {e}")
    payload = {"chat_id": chat_id, "text": text[:4000], "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = await tg_api("sendMessage", payload)
    # If the user came in via a voice note, also speak this reply back.
    if _TG_SPEAK.get():
        await tg_speak(chat_id, text)
    return result


async def tg_get_file_bytes(file_id: str) -> Optional[tuple[bytes, str]]:
    """Resolve a Telegram file_id to (bytes, filename)."""
    info = await tg_api("getFile", {"file_id": file_id})
    if not info.get("ok"):
        return None
    file_path = info["result"]["file_path"]
    try:
        r = await asyncio.to_thread(http_requests.get, f"{TG_FILE_API}/{file_path}", timeout=30)
        r.raise_for_status()
        return r.content, os.path.basename(file_path)
    except Exception as e:
        logger.warning(f"tg download failed: {e}")
        return None


@api.get("/telegram/status")
async def telegram_status(user: dict = Depends(get_current_user)):
    linked = bool(user.get("telegram_chat_id"))
    return {
        "configured": _tg_configured(),
        "linked": linked,
        "telegram_username": user.get("telegram_username"),
        "chat_id": user.get("telegram_chat_id"),
    }


@api.post("/telegram/link/code", response_model=TgLinkResponse)
async def telegram_link_code(user: dict = Depends(get_current_user)):
    """Generate a one-time linking code the user pastes into Telegram via /start."""
    if not _tg_configured():
        raise HTTPException(status_code=503, detail="Telegram bot is not configured on the server.")
    # 6-char code, upper-case alphanumerics
    code = "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(6))
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    # Invalidate any pre-existing codes for this user.
    await db.telegram_link_codes.delete_many({"user_id": user["user_id"]})
    await db.telegram_link_codes.insert_one({
        "code": code, "user_id": user["user_id"], "expires_at": expires_at, "created_at": now_iso(),
    })
    # Claim the Telegram webhook for THIS backend so /start CODE routes back to
    # the same env whose Mongo actually holds this code. Prevents "invalid code"
    # when preview + production both point their bot at each other.
    try:
        if BACKEND_PUBLIC_URL:
            await tg_api("setWebhook", {
                "url": f"{BACKEND_PUBLIC_URL}/api/telegram/webhook",
                "secret_token": TELEGRAM_WEBHOOK_SECRET,
                "allowed_updates": ["message", "edited_message", "callback_query"],
            })
    except Exception as e:
        logger.warning(f"telegram setWebhook on link/code failed (non-fatal): {e}")
    # Fetch bot username (cached in a class var to save API calls).
    global _TG_BOT_USERNAME
    if not globals().get("_TG_BOT_USERNAME"):
        me = await tg_api("getMe", {})
        _TG_BOT_USERNAME = (me.get("result") or {}).get("username", "")
    bot_username = globals().get("_TG_BOT_USERNAME") or ""
    deep_link = f"https://t.me/{bot_username}?start={code}" if bot_username else None
    return TgLinkResponse(code=code, bot_username=bot_username or None, deep_link=deep_link)


@api.post("/telegram/link/unlink")
async def telegram_unlink(user: dict = Depends(get_current_user)):
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$unset": {"telegram_chat_id": "", "telegram_username": ""}},
    )
    await db.telegram_link_codes.delete_many({"user_id": user["user_id"]})
    await db.telegram_sessions.delete_many({"user_id": user["user_id"]})
    return {"unlinked": True}


# ---- webhook + intake helpers ------------------------------------------------

WELCOME_LINKED = (
    "✅ <b>Karya linked for {name}.</b> Here's the field playbook 👇\n\n"
    "<b>🗣 Talk to me in plain language — voice, text, any supported language.</b>\n"
    "• <i>“Ramesh took an advance of {amt}”</i> → creates advance transaction\n"
    "• <i>“Pay Manoj {pay}”</i> → logs payment, drops his pending balance\n"
    "• <i>“10 workers at Skyline today”</i> → attendance rows for today\n"
    "• <i>“Add Suresh, mason, 800 per day, on Skyline”</i> → new worker\n"
    "• <i>“How much do I owe Ramesh?”</i> → live answer from ledger\n\n"
    "<b>🎙 Voice notes</b> in any language — I transcribe and act on them, and speak the confirmation back so you don't have to look at the screen.\n\n"
    "<b>📸 Send photos / receipts / PDFs</b> — I ask <i>“what should I do with this?”</i> and file it under:\n"
    "• Worker file · Daily report · Receipt (auto-parsed into Expenses) · Compliance · Note\n"
    "Tip: add a caption like <i>“this is Ramesh's Aadhaar”</i> and I skip the question.\n\n"
    "<b>📋 Commands</b>\n"
    "• /report — generate today's daily site report from your drafts\n"
    "• /attendance — mark headcount or per-worker attendance (present/absent/half day)\n"
    "• /help &lt;question&gt; — ask anything about Karya (in your language)\n"
    "• /unlink — disconnect this chat\n\n"
    "Ready when you are — send your first update. 🚧"
)

# Short "how do I…" primer used by /help when no argument is supplied.
HELP_OVERVIEW = (
    "🧭 <b>How to use Karya on Telegram</b>\n\n"
    "1. <b>Log field activity</b> — text, voice or photo. e.g. <i>“Ramesh took ₹5,000 advance”</i>.\n"
    "2. <b>Send receipts</b> as a photo — tap <i>Receipt</i> when I ask. AI extracts vendor + amount into Expenses.\n"
    "3. <b>Send worker IDs / photos</b> — tap <i>Worker file</i>, tell me whose file. Stored on the worker card.\n"
    "4. <b>Daily reports</b> — jot notes / send photos through the day, then send /report to generate.\n"
    "5. <b>Ask questions</b> — <i>/help how do I mark attendance</i> · <i>/help WhatsApp not sending</i>.\n\n"
    "Everything you do here appears in the Karya web app in real time."
)

WELCOME_UNLINKED = (
    "👷 <b>Welcome to Karya Assistant.</b>\n\n"
    "Please link this chat to your Karya account first.\n\n"
    "Steps:\n"
    "1. Open Karya → Profile → <b>Connect Telegram</b>\n"
    "2. Copy the 6-character code shown\n"
    "3. Return here and send: <code>/start ABCDEF</code>\n\n"
    "That code is valid for 15 minutes."
)


async def _handle_tg_start(chat_id: int, from_user: dict, arg: str):
    if not arg:
        await tg_send(chat_id, WELCOME_UNLINKED)
        return
    # Strip any leading @botusername mention (Telegram groups sometimes prefix)
    code = arg.strip().split()[0].upper()
    entry = await db.telegram_link_codes.find_one({"code": code})
    if not entry:
        logger.info(f"telegram /start: code '{code}' not found in db={os.environ.get('DB_NAME', '?')}")
        await tg_send(
            chat_id,
            "⚠️ That linking code isn't valid or has already been used.\n\n"
            "Please open Karya → <b>Profile</b> → <b>Connect Telegram</b>, tap "
            "<b>Generate new code</b>, and send the fresh 6-character code here as "
            "<code>/start ABCDEF</code>.\n\n"
            "Tip: make sure you're generating the code from the <i>same</i> Karya URL you signed up on.",
        )
        return
    try:
        exp = datetime.fromisoformat(entry["expires_at"])
        if exp < datetime.now(timezone.utc):
            await db.telegram_link_codes.delete_one({"code": code})
            await tg_send(chat_id, "⚠️ That code has expired. Please generate a new one.")
            return
    except Exception:
        pass
    user = await db.users.find_one({"user_id": entry["user_id"]}, {"_id": 0})
    if not user:
        await tg_send(chat_id, "⚠️ That Karya account no longer exists.")
        return
    # Detach this chat from any prior user, then link to the new one.
    await db.users.update_many({"telegram_chat_id": chat_id}, {"$unset": {"telegram_chat_id": "", "telegram_username": ""}})
    await db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"telegram_chat_id": chat_id, "telegram_username": from_user.get("username", "") or ""}},
    )
    await db.telegram_link_codes.delete_one({"code": code})
    ctx = country_ctx(user)
    amt = "AED 500" if ctx["currency_code"] == "AED" else "₹5000"
    pay = "AED 1200" if ctx["currency_code"] == "AED" else "₹12000"
    await tg_send(chat_id, WELCOME_LINKED.format(name=user.get("name", "you"), amt=amt, pay=pay))


async def _tg_user_for_chat(chat_id: int) -> Optional[dict]:
    return await db.users.find_one({"telegram_chat_id": chat_id}, {"_id": 0})


# ---- conversational agent (pending-media) layer ------------------------------

TG_ACTION_KB = {
    "inline_keyboard": [
        [{"text": "📋 Daily report", "callback_data": "act|report"},
         {"text": "👷 Worker file", "callback_data": "act|worker"}],
        [{"text": "🧾 Receipt / expense", "callback_data": "act|receipt"},
         {"text": "🛡️ Compliance", "callback_data": "act|compliance"}],
        [{"text": "🧠 Save as note", "callback_data": "act|note"},
         {"text": "✖️ Discard", "callback_data": "act|cancel"}],
    ]
}

TG_ROUTER_SYSTEM = """You route a user's instruction about a file they just sent (photo/PDF) to a construction-ops bot.
Known workers: {workers}
Output JSON: {{"action": "daily_report|worker_file|receipt|compliance|knowledge|cancel|chat",
 "worker_name": str|null, "note": str|null}}
Rules:
- "add to today's report" / "site progress photo" -> daily_report
- "upload it under <name>" / "this is <name>'s photo/id/document" / "save to <worker>'s file" -> worker_file with worker_name
- "this is a receipt/bill/invoice/expense" -> receipt
- "permit / license / notice / legal or govt document" -> compliance
- "just save it" / "note it down" -> knowledge
- "discard / ignore / cancel / delete" -> cancel
- If the message is unrelated to the file (a question or a normal ops command), use "chat".
The instruction may be in English, Hindi, or other Indian languages (or transliterated)."""

RECEIPT_SYSTEM = """You extract structured data from a purchase receipt/bill/invoice for a construction contractor.
Output JSON: {"vendor": str, "date": "YYYY-MM-DD or empty", "total_amount": number, "currency": str,
 "category": "material|fuel|food|transport|equipment|rent|other", "items": [{"name": str, "qty": str, "amount": number}], "summary": str}
If the image/text is not a receipt, set total_amount to 0 and explain in summary."""


async def _get_pending(user_id: str) -> Optional[dict]:
    return await db.telegram_pending.find_one({"user_id": user_id}, {"_id": 0}, sort=[("created_at", -1)])


async def _clear_pending(user_id: str):
    await db.telegram_pending.delete_many({"user_id": user_id})


def _pending_attachment(pending: dict) -> dict:
    return {
        "id": new_id(), "filename": pending.get("filename") or "file",
        "content_type": pending.get("content_type") or "application/octet-stream",
        "size": pending.get("size", 0), "path": pending["path"], "url": None,
        "extracted_text": (pending.get("extracted_text") or "")[:800],
        "uploaded_at": now_iso(), "source": "telegram", "caption": pending.get("caption", ""),
    }


async def _attach_to_worker(chat_id: int, user: dict, pending: dict, worker: dict):
    att = _pending_attachment(pending)
    await db.workers.update_one({"id": worker["id"]}, {"$push": {"documents": att}})
    await _clear_pending(user["user_id"])
    await tg_send(chat_id, f"👷 Saved <b>{att['filename']}</b> under <b>{worker['name']}</b>'s file. View it in Karya → Workforce.")


async def _file_pending_to_compliance(chat_id: int, user: dict, pending: dict):
    text = pending.get("extracted_text") or ""
    filename = pending.get("filename") or "document"
    title = filename.rsplit(".", 1)[0][:120] or "Uploaded compliance document"
    att = _pending_attachment(pending)
    item = {
        "id": new_id(), "owner_id": user["user_id"], "title": title, "category": "permit",
        "due_date": "", "expiry_date": "", "project_ids": [], "status": "pending",
        "document_text": (text or "")[:8000], "attachments": [att],
        "analysis": None, "renewal_plan": None, "penalty_estimate": None,
        "history": [{"action": "uploaded_via_telegram", "at": now_iso(), "note": filename}],
        "created_at": now_iso(),
    }
    await db.compliance.insert_one({**item})
    await _clear_pending(user["user_id"])
    await tg_send(chat_id, f"📄 <b>{title}</b> added to your compliance register. Running AI analysis…")
    try:
        ctx = country_ctx(user)
        analysis = await ai_json(
            COMPLIANCE_SYSTEM.format(country_context=ctx["context_prompt"]),
            f"Title: {title}\nCategory: permit\nDocument text:\n{(text or '')[:5000]}",
        )
        patch: Dict[str, Any] = {"analysis": analysis}
        if analysis and analysis.get("expiry_date"):
            patch["expiry_date"] = analysis["expiry_date"]
            patch["due_date"] = analysis["expiry_date"]
        await db.compliance.update_one({"id": item["id"]}, {"$set": patch, "$push": {"history": {"action": "analyzed", "at": now_iso(), "note": ""}}})
        summary_line = (analysis or {}).get("summary") or "Analysis complete — open Karya to review."
        risk = (analysis or {}).get("risk_level") or ""
        expiry_hint = f"\n🗓 <b>Expiry:</b> {analysis.get('expiry_date')}" if (analysis and analysis.get("expiry_date")) else ""
        await tg_send(chat_id, f"🧠 <b>{title}</b>{expiry_hint}\n<b>Risk:</b> {risk}\n{summary_line[:600]}")
    except Exception as e:
        logger.warning(f"tg compliance analysis failed: {e}")
        await tg_send(chat_id, "⚠️ Analysis failed but the document is saved. Open Karya → Compliance to review manually.")


async def _apply_pending_action(chat_id: int, action: str, user: dict, pending: dict, worker_name: Optional[str], note: str):
    uid = user["user_id"]
    if action == "cancel":
        await _clear_pending(uid)
        await tg_send(chat_id, "🗑 Discarded.")
        return
    if action == "worker_file":
        workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
        worker = find_by_name(workers, worker_name)
        if not worker:
            await db.telegram_pending.update_one({"id": pending["id"]}, {"$set": {"stage": "await_worker"}})
            names = ", ".join(w["name"] for w in workers[:15]) or "no workers yet — add one first"
            await tg_send(chat_id, f"👷 Which worker should I file this under?\nKnown: {names}")
            return
        await _attach_to_worker(chat_id, user, pending, worker)
        return
    if action == "daily_report":
        att = _pending_attachment(pending)
        today = today_str()
        field = "photos" if pending.get("kind") == "photo" else "documents"
        await db.telegram_wip.update_one(
            {"user_id": uid, "date": today},
            {"$push": {field: att}, "$setOnInsert": {"created_at": now_iso(), "notes": ""}, "$set": {"updated_at": now_iso()}},
            upsert=True,
        )
        if note:
            await db.telegram_wip.update_one({"user_id": uid, "date": today}, {"$set": {"last_caption": note}})
        wip = await db.telegram_wip.find_one({"user_id": uid, "date": today}, {"_id": 0})
        n = len(wip.get("photos") or []) + len(wip.get("documents") or [])
        await _clear_pending(uid)
        await tg_send(chat_id, f"📋 Added to today's report draft ({n} file(s) attached). Send more, or /report to generate the daily report.")
        return
    if action == "receipt":
        await tg_send(chat_id, "🧾 Reading the receipt…")
        parsed = {}
        try:
            if pending.get("kind") == "photo" or (pending.get("content_type") or "").startswith("image/"):
                data, _ct = await asyncio.to_thread(get_object, pending["path"])
                b64 = base64.b64encode(data).decode()
                parsed = await ai_json(RECEIPT_SYSTEM, "Extract this receipt.", images=[ImageContent(image_base64=b64)], provider="openai", model="gpt-4o")
            else:
                parsed = await ai_json(RECEIPT_SYSTEM, f"Receipt text:\n{(pending.get('extracted_text') or '')[:5000]}", provider="openai", model="gpt-4o")
        except Exception as e:
            logger.warning(f"receipt parse failed: {e}")
        amount = float(parsed.get("total_amount") or 0)
        att = _pending_attachment(pending)
        exp = {
            "id": new_id(), "owner_id": uid, "vendor": parsed.get("vendor") or "", "date": parsed.get("date") or today_str(),
            "amount": amount, "currency": parsed.get("currency") or country_ctx(user)["currency_code"],
            "category": parsed.get("category") or "other", "items": parsed.get("items") or [],
            "summary": parsed.get("summary") or "", "attachment": att, "source": "telegram",
            "project_id": None,
            "created_at": now_iso(),
        }
        await db.expenses.insert_one({**exp})
        await db.knowledge.insert_one({
            "id": new_id(), "owner_id": uid,
            "title": f"Receipt — {exp['vendor'] or 'unknown vendor'} ({money_str(amount, user)})",
            "content": exp["summary"] or f"Receipt of {money_str(amount, user)} — category {exp['category']}.",
            "project_id": None, "tags": ["receipt", "expense", "telegram"], "attachment": att, "created_at": now_iso(),
        })
        await _clear_pending(uid)
        lines = "\n".join(f"• {i.get('name')} — {money_str(i.get('amount') or 0, user)}" for i in (exp["items"] or [])[:6])
        await tg_send(chat_id, f"🧾 <b>Receipt recorded</b>\nVendor: {exp['vendor'] or '—'}\nTotal: <b>{money_str(amount, user)}</b>\nCategory: {exp['category']}\n{lines}".strip())
        return
    if action == "compliance":
        await _file_pending_to_compliance(chat_id, user, pending)
        return
    # knowledge (default)
    att = _pending_attachment(pending)
    await db.knowledge.insert_one({
        "id": new_id(), "owner_id": uid, "title": f"Telegram upload — {att['filename']}",
        "content": (note or pending.get("caption") or "Saved from Telegram.") + (f"\n\nExtracted text:\n{(pending.get('extracted_text') or '')[:2000]}" if pending.get("extracted_text") else ""),
        "project_id": None, "tags": ["telegram", "upload"], "attachment": att, "created_at": now_iso(),
    })
    await _clear_pending(uid)
    await tg_send(chat_id, f"🧠 Saved <b>{att['filename']}</b> to Org Memory.")


async def _route_pending_instruction(chat_id: int, text: str, user: dict, pending: dict):
    workers = await db.workers.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    try:
        parsed = await ai_json(
            TG_ROUTER_SYSTEM.format(workers=", ".join(w["name"] for w in workers) or "none"),
            f"File: {pending.get('kind')} ({pending.get('filename')})\nInstruction: {text}",
            provider="openai", model="gpt-4o",
        )
    except Exception:
        parsed = {"action": "chat"}
    action = parsed.get("action") or "chat"
    if action == "chat":
        await _handle_tg_command_text(chat_id, text, user)
        return
    await _apply_pending_action(chat_id, action, user, pending, parsed.get("worker_name"), parsed.get("note") or text)


async def _handle_tg_command_text(chat_id: int, text: str, user: dict):
    result = await _execute_command(text, user)
    if result.get("applied"):
        await tg_send(chat_id, f"✅ {result.get('summary') or 'Done.'}")
        return
    if not result.get("unknown"):
        await tg_send(chat_id, f"🤔 {result.get('summary') or 'Could not apply that.'}")
        return
    # Not an ops command — answer conversationally from operational data.
    try:
        answer = await _assistant_answer(user, text)
        await tg_send(chat_id, f"💬 {answer[:3800]}")
    except Exception:
        await tg_send(chat_id, f"🤔 {result.get('summary')}")


async def _handle_tg_text(chat_id: int, text: str, user: dict):
    if not text:
        return
    pending = await _get_pending(user["user_id"])
    if pending:
        if text.lower().strip() in ("cancel", "discard", "stop", "no"):
            await _clear_pending(user["user_id"])
            await tg_send(chat_id, "🗑 Discarded.")
            return
        if pending.get("stage") == "await_worker":
            workers = await db.workers.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(1000)
            worker = find_by_name(workers, text)
            if worker:
                await _attach_to_worker(chat_id, user, pending, worker)
            else:
                names = ", ".join(w["name"] for w in workers[:15]) or "none yet"
                await tg_send(chat_id, f"⚠️ I couldn't find \"{text}\". Known workers: {names}. Reply with one of these names, or say \"cancel\".")
            return
        await _route_pending_instruction(chat_id, text, user, pending)
        return
    await _handle_tg_command_text(chat_id, text, user)


async def _handle_tg_voice(chat_id: int, file_id: str, user: dict):
    dl = await tg_get_file_bytes(file_id)
    if not dl:
        await tg_send(chat_id, "⚠️ Couldn't download that voice note.")
        return
    data, filename = dl
    # Very short recordings (<1KB) usually mean an accidental tap — Whisper
    # rejects them anyway with an unhelpful error.
    if len(data) < 1024:
        await tg_send(chat_id, "🎙️ That clip was too short. Please record for at least a second and try again.")
        return
    if not EMERGENT_LLM_KEY:
        logger.error("tg voice: EMERGENT_LLM_KEY not set — cannot transcribe.")
        await tg_send(chat_id, "⚠️ Voice transcription isn't configured on this server. Please type the command instead.")
        return
    # Ensure a Whisper-friendly filename extension so the SDK infers content type.
    if not filename or "." not in filename:
        filename = "voice.ogg"
    elif not filename.lower().endswith((".ogg", ".oga", ".mp3", ".wav", ".m4a", ".webm", ".opus")):
        filename = filename + ".ogg"
    # 2 attempts with a short backoff — matches /api/voice/transcribe hardening
    # from iter29. Fail fast so the Telegram webhook (60s ingress) doesn't 504.
    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    transcript = ""
    last_err: Optional[Exception] = None
    for attempt in range(2):
        try:
            buf = io.BytesIO(data)
            buf.name = filename
            resp = await asyncio.wait_for(
                stt.transcribe(file=buf, model="whisper-1", response_format="json"),
                timeout=25,
            )
            transcript = (getattr(resp, "text", None) or "").strip()
            last_err = None
            break
        except asyncio.TimeoutError:
            last_err = Exception("upstream timeout")
        except Exception as e:
            last_err = e
        if attempt == 0:
            await asyncio.sleep(0.6)
    if last_err is not None:
        # Log the specific exception so we can diagnose from server logs.
        logger.warning(
            "tg voice transcribe failed for user=%s filename=%s size=%d: %s: %s",
            user.get("user_id"), filename, len(data), type(last_err).__name__, last_err,
        )
        await tg_send(
            chat_id,
            "⚠️ Couldn't transcribe the voice note right now. Please try again in a moment or type the command.",
        )
        return
    if not transcript:
        await tg_send(chat_id, "🎙️ I couldn't hear anything in that recording. Please speak a bit louder and try again.")
        return
    # Any tg_send() called inside this block will ALSO speak the reply via OpenAI TTS.
    token = _TG_SPEAK.set(True)
    try:
        await tg_send(chat_id, f"🎙️ <i>Heard:</i> {transcript}")
        await _handle_tg_text(chat_id, transcript, user)
    finally:
        _TG_SPEAK.reset(token)


async def _handle_tg_photo(chat_id: int, file_id: str, caption: str, user: dict):
    """Photos become a pending item — the agent asks what to do (or uses the caption)."""
    dl = await tg_get_file_bytes(file_id)
    if not dl:
        await tg_send(chat_id, "⚠️ Couldn't download the photo.")
        return
    data, filename = dl
    if not filename.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        filename = (filename or "photo") + ".jpg"
    try:
        ext = filename.rsplit(".", 1)[-1].lower() or "jpg"
        path = f"{APP_NAME}/telegram/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
        stored = await asyncio.to_thread(put_object, path, data, "image/jpeg")
    except Exception as e:
        logger.warning(f"tg photo storage failed: {e}")
        await tg_send(chat_id, "⚠️ Couldn't save the photo. Please retry.")
        return
    await _clear_pending(user["user_id"])
    pending = {
        "id": new_id(), "user_id": user["user_id"], "chat_id": chat_id, "kind": "photo",
        "path": stored["path"], "filename": filename, "content_type": "image/jpeg",
        "size": len(data), "extracted_text": "", "caption": caption or "",
        "stage": "await_action", "created_at": now_iso(),
    }
    await db.telegram_pending.insert_one({**pending})
    pending.pop("_id", None)
    if caption:
        await _route_pending_instruction(chat_id, caption, user, pending)
    else:
        await tg_send(
            chat_id,
            "📸 Got the photo. What should I do with it?\nTap a button — or just tell me, e.g. <i>“upload it under Ramesh's file”</i> or <i>“this is a cement receipt”</i>.",
            TG_ACTION_KB,
        )


async def _handle_tg_document(chat_id: int, file_id: str, filename: str, mime: str, caption: str, user: dict):
    """Documents (PDFs etc.) become a pending item awaiting the user's instruction."""
    dl = await tg_get_file_bytes(file_id)
    if not dl:
        await tg_send(chat_id, "⚠️ Couldn't download the document.")
        return
    data, downloaded_name = dl
    filename = filename or downloaded_name or "document"
    is_image = mime.startswith("image/") if mime else filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))
    try:
        ext = (filename.rsplit(".", 1)[-1] if "." in filename else "bin").lower()
        path = f"{APP_NAME}/telegram/{user['user_id']}/{uuid.uuid4().hex}.{ext}"
        stored = await asyncio.to_thread(put_object, path, data, mime or "application/octet-stream")
    except Exception as e:
        logger.warning(f"tg doc storage failed: {e}")
        await tg_send(chat_id, "⚠️ Couldn't save the document.")
        return
    text = ""
    try:
        text = extract_text(data, mime or "", filename)
    except Exception:
        pass
    await _clear_pending(user["user_id"])
    pending = {
        "id": new_id(), "user_id": user["user_id"], "chat_id": chat_id,
        "kind": "photo" if is_image else "document",
        "path": stored["path"], "filename": filename,
        "content_type": mime or ("image/jpeg" if is_image else "application/octet-stream"),
        "size": len(data), "extracted_text": text or "", "caption": caption or "",
        "stage": "await_action", "created_at": now_iso(),
    }
    await db.telegram_pending.insert_one({**pending})
    pending.pop("_id", None)
    if caption:
        await _route_pending_instruction(chat_id, caption, user, pending)
    else:
        await tg_send(
            chat_id,
            f"📄 Received <b>{filename}</b>. What should I do with it?\nTap a button — or tell me, e.g. <i>“it's Manoj's labour card”</i> or <i>“add to compliance”</i>.",
            TG_ACTION_KB,
        )


async def _generate_and_send_report(chat_id: int, user: dict, project: Optional[dict]):
    """Assemble today's WIP into a real daily report + notify the chat."""
    today = today_str()
    wip = await db.telegram_wip.find_one({"user_id": user["user_id"], "date": today}, {"_id": 0})
    if not wip or (not wip.get("photos") and not wip.get("notes")):
        await tg_send(chat_id, "📝 Nothing in today's draft yet. Send photos or a short voice note describing progress, then /report.")
        return
    project_id = project["id"] if project else None
    project_name = project["name"] if project else ""
    ctx = country_ctx(user)
    sys_prompt = (
        "You write a daily site report for a construction contractor. "
        f"{ctx['context_prompt']} "
        "Given field notes + photos, output JSON with keys: title, summary, weather, work_completed[], manpower, materials_used[], issues_delays[], safety_observations[], next_steps[]."
    )
    notes_text = wip.get("notes") or ""
    if wip.get("last_caption"):
        notes_text = (notes_text + "\n" + wip["last_caption"]).strip()
    prompt = f"Project: {project_name}\nDate: {today}\nField notes: {notes_text or '(only photos provided)'}\nPhoto count: {len(wip.get('photos') or [])}"
    try:
        content = await ai_json(sys_prompt, prompt)
    except Exception:
        content = {"title": f"Daily Report — {project_name or 'Site'}", "summary": notes_text or "Photos attached, no text notes.", "work_completed": [], "manpower": "", "materials_used": [], "issues_delays": [], "safety_observations": [], "next_steps": []}
    rec = {
        "id": new_id(), "owner_id": user["user_id"], "project_id": project_id, "project_name": project_name,
        "report_date": today, "location": (project or {}).get("location", ""),
        "notes_text": notes_text, "photos": wip.get("photos") or [], "documents": [],
        "content": content, "sent_to": [], "created_at": now_iso(), "source": "telegram",
    }
    await db.daily_reports.insert_one({**rec})
    await db.telegram_wip.delete_one({"user_id": user["user_id"], "date": today})
    title = content.get("title") or "Daily Report"
    summary_line = (content.get("summary") or "")[:600]
    project_tag = f" for <b>{project_name}</b>" if project_name else ""
    await tg_send(
        chat_id,
        f"📋 <b>{title}</b>{project_tag}\n{summary_line}\n\nOpen Karya → Daily Reports to export as PDF/Word/Excel or send on WhatsApp.",
    )


async def _handle_tg_report_command(chat_id: int, user: dict):
    """
    /report — if the user has 0 projects, use no project.
    If exactly 1, use it silently.
    If 2+, present an inline keyboard so the user picks which project this report is for.
    """
    projects = await db.projects.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(50)
    if len(projects) <= 1:
        await _generate_and_send_report(chat_id, user, projects[0] if projects else None)
        return
    # Build 1-column inline keyboard of up to 8 most-recent projects + a "no project" fallback.
    buttons = [[{"text": p["name"][:56], "callback_data": f"report_pick|{p['id']}"}] for p in projects[:8]]
    buttons.append([{"text": "— No project —", "callback_data": "report_pick|__none__"}])
    await tg_send(
        chat_id,
        "🗂 <b>Which project is today's report for?</b>",
        reply_markup={"inline_keyboard": buttons},
    )


async def _handle_tg_attendance_command(chat_id: int, user: dict, text: str):
    """
    /attendance — free-form headcount + project picker.
    Usage examples:
      • /attendance                → show project picker for a quick headcount
      • /attendance 12             → 12 workers today (project picker follows)
      • /attendance 12 Site A      → 12 workers at Site A today
      • /attendance Ramesh present → mark Ramesh present today
    """
    uid = user["user_id"]
    arg = text[len("/attendance"):].strip()
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(50)
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(2000)

    # Path A: worker-status form ("Ramesh present" / "Suresh absent" / "Manoj half day").
    m = re.match(r"^(.+?)\s+(present|absent|half[\s-]?day|halfday)$", arg, re.IGNORECASE) if arg else None
    if m:
        who, status_raw = m.group(1).strip(), m.group(2).lower()
        status = "half_day" if status_raw.replace("-", "").replace(" ", "") == "halfday" else status_raw
        worker = find_by_name(workers, who)
        if not worker:
            names = ", ".join(w["name"] for w in workers[:10]) or "none yet"
            await tg_send(chat_id, f"⚠️ Couldn't find worker <b>{html.escape(who)}</b>. Known: {names}.")
            return
        try:
            await mark_attendance(AttendanceMarkIn(worker_id=worker["id"], status=status), user)
        except HTTPException as e:
            await tg_send(chat_id, f"⚠️ {e.detail}")
            return
        emoji = "✅" if status == "present" else ("🌓" if status == "half_day" else "❌")
        await tg_send(chat_id, f"{emoji} Marked <b>{html.escape(worker['name'])}</b> as <b>{status.replace('_', ' ')}</b> for today.")
        return

    # Path B: headcount form ("12" or "12 Site A").
    m2 = re.match(r"^(\d+)(?:\s+(.+))?$", arg) if arg else None
    if m2:
        count = max(0, min(int(m2.group(1)), 10000))
        proj_name = (m2.group(2) or "").strip()
        proj = find_by_name(projects, proj_name) if proj_name else None
        if not proj and len(projects) > 1:
            # Ask which project via inline keyboard.
            buttons = [[{"text": p["name"][:56], "callback_data": f"att_head|{count}|{p['id']}"}] for p in projects[:8]]
            buttons.append([{"text": "— No project —", "callback_data": f"att_head|{count}|__none__"}])
            await tg_send(chat_id, f"👷 <b>{count} workers today.</b> Which project?", reply_markup={"inline_keyboard": buttons})
            return
        proj = proj or (projects[0] if len(projects) == 1 else None)
        await headcount_attendance(AttendanceHeadcountIn(count=count, project_id=proj["id"] if proj else None), user)
        where = f" at <b>{html.escape(proj['name'])}</b>" if proj else ""
        await tg_send(chat_id, f"✅ Logged <b>{count}</b> workers present today{where}.")
        return

    # Path C: no arg — show a quick help.
    if not arg:
        today_att = await db.attendance.find({"owner_id": uid, "date": today_str()}, {"_id": 0}).to_list(500)
        marked = sum(1 for a in today_att if a.get("worker_id") and a.get("status") == "present")
        head = sum(int(a.get("count") or 0) for a in today_att if not a.get("worker_id"))
        await tg_send(
            chat_id,
            (
                "👷 <b>Attendance — today</b>\n"
                f"Named present: <b>{marked}</b>\n"
                f"Headcount tally: <b>{head}</b>\n\n"
                "Try:\n"
                "• <code>/attendance 12</code> — quick headcount (asks project)\n"
                "• <code>/attendance 12 Site A</code> — headcount for a specific site\n"
                "• <code>/attendance Ramesh present</code> — per-worker (present/absent/half day)\n"
            ),
        )
        return

    await tg_send(chat_id, "⚠️ Couldn't parse that. Try <code>/attendance 12</code> or <code>/attendance Ramesh present</code>.")


@api.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    """Telegram calls this endpoint for every update. Auth via the secret header."""
    if not _tg_configured():
        return {"ok": True}  # Silently accept if not configured.
    if TELEGRAM_WEBHOOK_SECRET:
        provided = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if provided != TELEGRAM_WEBHOOK_SECRET:
            raise HTTPException(status_code=403, detail="Invalid webhook secret")
    try:
        update = await request.json()
    except Exception:
        return {"ok": True}

    # Inline-button taps (choose what to do with a pending file).
    cq = update.get("callback_query")
    if cq:
        await tg_api("answerCallbackQuery", {"callback_query_id": cq.get("id")})
        cq_chat_id = ((cq.get("message") or {}).get("chat") or {}).get("id")
        data = cq.get("data") or ""
        if not cq_chat_id:
            return {"ok": True}
        user = await _tg_user_for_chat(cq_chat_id)
        if not user:
            await tg_send(cq_chat_id, WELCOME_UNLINKED)
            return {"ok": True}
        _TG_USER_LANG.set(user.get("language") or "en")
        pending = await _get_pending(user["user_id"])
        # Handle /report project picker callbacks (no pending required).
        if data.startswith("report_pick|"):
            pid = data.split("|", 1)[1]
            if pid == "__none__":
                await _generate_and_send_report(cq_chat_id, user, None)
            else:
                project = await db.projects.find_one({"owner_id": user["user_id"], "id": pid}, {"_id": 0})
                if not project:
                    await tg_send(cq_chat_id, "⚠️ That project no longer exists. Try /report again.")
                else:
                    await _generate_and_send_report(cq_chat_id, user, project)
            return {"ok": True}
        # Handle /attendance headcount picker callbacks.
        if data.startswith("att_head|"):
            _, count_s, pid = data.split("|", 2)
            try:
                count = int(count_s)
            except ValueError:
                count = 1
            proj = None
            if pid != "__none__":
                proj = await db.projects.find_one({"owner_id": user["user_id"], "id": pid}, {"_id": 0})
            await headcount_attendance(AttendanceHeadcountIn(count=count, project_id=proj["id"] if proj else None), user)
            where = f" at <b>{html.escape(proj['name'])}</b>" if proj else ""
            await tg_send(cq_chat_id, f"✅ Logged <b>{count}</b> workers present today{where}.")
            return {"ok": True}
        if not pending:
            await tg_send(cq_chat_id, "Nothing pending — send me a photo or document first.")
            return {"ok": True}
        action_map = {"report": "daily_report", "worker": "worker_file", "receipt": "receipt",
                      "compliance": "compliance", "note": "knowledge", "cancel": "cancel"}
        action = action_map.get(data.split("|", 1)[-1], "knowledge")
        await _apply_pending_action(cq_chat_id, action, user, pending, None, "")
        return {"ok": True}

    msg = update.get("message") or update.get("edited_message") or {}
    if not msg:
        return {"ok": True}
    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    from_user = msg.get("from") or {}
    text = (msg.get("text") or "").strip()
    caption = (msg.get("caption") or "").strip()
    if not chat_id:
        return {"ok": True}

    # Silently capture the ops-owner's chat_id the first time they message the
    # bot so /api/contact submissions can be delivered to them. The handle is
    # kept in env (CONTACT_TG_USERNAME) — we never surface it in any UI.
    try:
        uname = (from_user.get("username") or "").lstrip("@").lower()
        want = (CONTACT_TG_USERNAME or "").lstrip("@").lower()
        if want and uname and uname == want:
            existing = await db.system_config.find_one({"key": "contact_chat_id"})
            if not existing or str(existing.get("value")) != str(chat_id):
                await db.system_config.update_one(
                    {"key": "contact_chat_id"},
                    {"$set": {"value": str(chat_id), "updated_at": now_iso()}},
                    upsert=True,
                )
                logger.info("Captured contact recipient chat_id.")
    except Exception as e:
        logger.warning(f"contact chat_id capture skipped: {e}")

    # /start handles linking (works even when unlinked).
    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        arg = parts[1] if len(parts) > 1 else ""
        await _handle_tg_start(chat_id, from_user, arg)
        return {"ok": True}

    user = await _tg_user_for_chat(chat_id)
    if not user:
        await tg_send(chat_id, WELCOME_UNLINKED)
        return {"ok": True}
    _TG_USER_LANG.set(user.get("language") or "en")

    if text.startswith("/help"):
        ctx = country_ctx(user)
        amt = "AED 500" if ctx["currency_code"] == "AED" else "₹5000"
        await tg_send(
            chat_id,
            WELCOME_LINKED.format(name=user.get("name", "you"), amt=amt, pay="AED 1200" if ctx["currency_code"] == "AED" else "₹12000"),
        )
        return {"ok": True}
    if text.startswith("/unlink"):
        await db.users.update_one({"user_id": user["user_id"]}, {"$unset": {"telegram_chat_id": "", "telegram_username": ""}})
        await db.telegram_sessions.delete_many({"user_id": user["user_id"]})
        await tg_send(chat_id, "🔌 Unlinked. Message /start again with a new code to reconnect.")
        return {"ok": True}
    if text.startswith("/report"):
        await _handle_tg_report_command(chat_id, user)
        return {"ok": True}
    if text.startswith("/attendance"):
        await _handle_tg_attendance_command(chat_id, user, text)
        return {"ok": True}

    # Media handling.
    if msg.get("voice") or msg.get("audio"):
        v = msg.get("voice") or msg.get("audio") or {}
        await _handle_tg_voice(chat_id, v.get("file_id"), user)
        return {"ok": True}
    if msg.get("photo"):
        # Largest photo variant is last in the array.
        biggest = msg["photo"][-1]
        await _handle_tg_photo(chat_id, biggest.get("file_id"), caption, user)
        return {"ok": True}
    if msg.get("document"):
        doc = msg["document"]
        await _handle_tg_document(chat_id, doc.get("file_id"), doc.get("file_name", ""), doc.get("mime_type", ""), caption, user)
        return {"ok": True}

    if text:
        await _handle_tg_text(chat_id, text, user)
    return {"ok": True}


@api.post("/telegram/register-webhook")
async def telegram_register_webhook(user: dict = Depends(get_current_user)):
    """Call once (from Profile page) to register this preview/production URL with Telegram."""
    if not _tg_configured():
        raise HTTPException(status_code=503, detail="Telegram bot is not configured.")
    public_url = os.environ.get("BACKEND_PUBLIC_URL", "").rstrip("/")
    if not public_url:
        raise HTTPException(status_code=500, detail="BACKEND_PUBLIC_URL is not set.")
    webhook_url = f"{public_url}/api/telegram/webhook"
    payload = {
        "url": webhook_url,
        "secret_token": TELEGRAM_WEBHOOK_SECRET,
        "allowed_updates": ["message", "edited_message", "callback_query"],
        "drop_pending_updates": False,
    }
    r = await tg_api("setWebhook", payload)
    if not r.get("ok"):
        raise HTTPException(status_code=502, detail=f"Telegram rejected setWebhook: {r}")
    return {"ok": True, "webhook_url": webhook_url, "description": r.get("description")}


@app.on_event("startup")
async def _tg_autoregister_webhook():
    """Register the Telegram webhook automatically when the server boots.

    IMPORTANT: A Telegram bot has ONE global webhook — preview and production
    would otherwise fight over it and land /start CODE at the wrong environment
    (whose Mongo doesn't have the code → 'linking code isn't valid').
    We therefore only auto-register from a *production-style* host, and skip it
    on the ephemeral preview host. Preview devs can still register manually via
    POST /api/telegram/register-webhook if they explicitly need it.
    """
    if not _tg_configured() or not BACKEND_PUBLIC_URL:
        return
    is_preview_host = "preview.emergentagent.com" in BACKEND_PUBLIC_URL
    force = os.environ.get("TELEGRAM_AUTO_REGISTER_WEBHOOK", "").strip().lower() in {"1", "true", "yes"}
    if is_preview_host and not force:
        logger.info("telegram webhook autoregister skipped on preview host (set TELEGRAM_AUTO_REGISTER_WEBHOOK=true to override)")
        return
    try:
        r = await tg_api("setWebhook", {
            "url": f"{BACKEND_PUBLIC_URL}/api/telegram/webhook",
            "secret_token": TELEGRAM_WEBHOOK_SECRET,
            "allowed_updates": ["message", "edited_message", "callback_query"],
        })
        logger.info(f"telegram setWebhook on startup ok={r.get('ok')} {r.get('description', '')}")
    except Exception as e:
        logger.warning(f"telegram webhook autoregister failed: {e}")


# ---------------------------------------------------------------- compliance

class ComplianceIn(BaseModel):
    title: str
    category: str = "permit"
    due_date: str = ""
    expiry_date: str = ""
    project_ids: List[str] = []
    status: str = "pending"  # pending | in_progress | completed
    document_text: str = ""
    attachments: List[Dict[str, Any]] = []

class ComplianceUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    due_date: Optional[str] = None
    expiry_date: Optional[str] = None
    project_ids: Optional[List[str]] = None
    status: Optional[str] = None
    document_text: Optional[str] = None
    renewal_plan: Optional[Dict[str, Any]] = None
    penalty_estimate: Optional[Dict[str, Any]] = None


def _compliance_urgency(due: str) -> tuple[str, Optional[int]]:
    """Return (bucket, days_left) where bucket ∈ overdue/critical/warning/watch/ok/none."""
    if not due:
        return "none", None
    try:
        d = datetime.fromisoformat(due.replace("Z", "+00:00")) if "T" in due else datetime.strptime(due, "%Y-%m-%d")
    except Exception:
        return "none", None
    days = (d.date() - datetime.now(timezone.utc).date()).days
    if days < 0:
        return "overdue", days
    if days <= 7:
        return "critical", days
    if days <= 15:
        return "warning", days
    if days <= 30:
        return "watch", days
    return "ok", days


@api.get("/compliance")
async def list_compliance(user: dict = Depends(get_current_user)):
    return await db.compliance.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/compliance")
async def create_compliance(body: ComplianceIn, user: dict = Depends(get_current_user)):
    doc = {"id": new_id(), "owner_id": user["user_id"], **body.model_dump(),
           "analysis": None, "renewal_plan": None, "penalty_estimate": None,
           "history": [{"action": "created", "at": now_iso(), "note": ""}],
           "created_at": now_iso()}
    await db.compliance.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.patch("/compliance/{item_id}")
async def update_compliance(item_id: str, body: ComplianceUpdate, user: dict = Depends(get_current_user)):
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    if not patch:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await db.compliance.update_one({"id": item_id, "owner_id": user["user_id"]}, {"$set": patch, "$push": {"history": {"action": "updated", "at": now_iso(), "note": ",".join(patch.keys())}}})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return await db.compliance.find_one({"id": item_id, "owner_id": user["user_id"]}, {"_id": 0})

@api.delete("/compliance/{item_id}")
async def delete_compliance(item_id: str, user: dict = Depends(get_current_user)):
    res = await db.compliance.delete_one({"id": item_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found")
    return {"deleted": True}

COMPLIANCE_SYSTEM = """You are a construction compliance analyst. {country_context}
Analyze the given compliance item/document and output JSON:
{{"summary": str, "what_changed": str, "who_is_affected": str, "deadline": str, "expiry_date": "YYYY-MM-DD or empty", "penalties": str,
 "actions_required": [str], "risk_level": "high"|"medium"|"low"}}
Be specific and practical. If the document text is thin, infer from the title and category. If any date (validity/expiry/renewal) is present in the text, return it in expiry_date as ISO."""

@api.post("/compliance/{item_id}/analyze")
async def analyze_compliance(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.compliance.find_one({"id": item_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    ctx = country_ctx(user)
    prompt = (
        f"Title: {item['title']}\nCategory: {item['category']}\nDue date: {item.get('due_date') or 'unknown'}\n"
        f"Document text:\n{(item.get('document_text') or '')[:5000]}"
    )
    analysis = await ai_json(COMPLIANCE_SYSTEM.format(country_context=ctx["context_prompt"]), prompt)
    patch: Dict[str, Any] = {"analysis": analysis}
    if analysis and analysis.get("expiry_date") and not item.get("expiry_date"):
        patch["expiry_date"] = analysis["expiry_date"]
        if not item.get("due_date"):
            patch["due_date"] = analysis["expiry_date"]
    await db.compliance.update_one({"id": item_id}, {"$set": patch, "$push": {"history": {"action": "analyzed", "at": now_iso(), "note": ""}}})
    item.update(patch)
    return item

RENEWAL_SYSTEM = """You are a compliance operations expert for construction. {country_context}
Given a permit/license/registration item, output a JSON RENEWAL PLAN a small contractor can execute today:
{{"docs_needed": [str], "submission_office": str, "fee_estimate": str, "processing_time": str,
 "steps": [{{"title": str, "detail": str, "done": false}}], "portal_url": str}}
Steps must be atomic (1-3 lines each), sequenced, and specific to the country + the item category. Include ~5-8 steps."""

@api.post("/compliance/{item_id}/renew")
async def compliance_renew_plan(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.compliance.find_one({"id": item_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    ctx = country_ctx(user)
    prompt = (
        f"Title: {item['title']}\nCategory: {item['category']}\nDue: {item.get('due_date') or 'unknown'}\n"
        f"Existing analysis (may be empty): {json.dumps(item.get('analysis') or {})[:1200]}"
    )
    plan = await ai_json(RENEWAL_SYSTEM.format(country_context=ctx["context_prompt"]), prompt)
    await db.compliance.update_one({"id": item_id}, {"$set": {"renewal_plan": plan, "status": "in_progress"}, "$push": {"history": {"action": "renewal_plan_generated", "at": now_iso(), "note": ""}}})
    item["renewal_plan"] = plan
    item["status"] = "in_progress"
    return item

PENALTY_SYSTEM = """You compute late-compliance penalties for construction. {country_context}
Given an item + days-overdue, output JSON:
{{"currency": str, "amount_min": number, "amount_max": number, "basis": str,
 "escalation": [{{"days_after_due": int, "penalty": str}}], "worst_case": str}}
Be concrete: cite typical penalty ranges relevant to the country and category. Use the country currency ({currency_code}). If uncertain, give a wide sensible range and mark basis as "typical range – verify with authority"."""

@api.post("/compliance/{item_id}/penalty")
async def compliance_penalty(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.compliance.find_one({"id": item_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    ctx = country_ctx(user)
    bucket, days = _compliance_urgency(item.get("due_date") or item.get("expiry_date") or "")
    days_overdue = -days if (days is not None and days < 0) else 0
    prompt = (
        f"Title: {item['title']}\nCategory: {item['category']}\nDays overdue: {days_overdue}\n"
        f"Country: {ctx['name']}"
    )
    est = await ai_json(PENALTY_SYSTEM.format(country_context=ctx["context_prompt"], currency_code=ctx["currency_code"]), prompt)
    est["days_overdue"] = days_overdue
    if "currency" not in est or not est.get("currency"):
        est["currency"] = ctx["currency_code"]
    await db.compliance.update_one({"id": item_id}, {"$set": {"penalty_estimate": est}, "$push": {"history": {"action": "penalty_estimated", "at": now_iso(), "note": ""}}})
    item["penalty_estimate"] = est
    return item

@api.get("/compliance/dashboard")
async def compliance_dashboard(user: dict = Depends(get_current_user)):
    """Aggregate score + urgency buckets + penalty exposure. Feeds Compliance page hero card."""
    items = await db.compliance.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(1000)
    buckets = {"overdue": [], "critical": [], "warning": [], "watch": [], "ok": [], "none": []}
    penalty_exposure = 0.0
    for it in items:
        b, d = _compliance_urgency(it.get("due_date") or it.get("expiry_date") or "")
        if it.get("status") == "completed":
            buckets["ok"].append({"id": it["id"], "title": it["title"], "days": d, "category": it.get("category")})
            continue
        buckets[b].append({"id": it["id"], "title": it["title"], "days": d, "category": it.get("category")})
        if b == "overdue":
            pe = it.get("penalty_estimate") or {}
            penalty_exposure += float(pe.get("amount_max") or pe.get("amount_min") or 0)
    total = len(items) or 1
    completed = sum(1 for it in items if it.get("status") == "completed")
    overdue = len(buckets["overdue"])
    critical = len(buckets["critical"])
    warning = len(buckets["warning"])
    # Score: start at 100, deduct heavy for overdue, moderate for critical, light for warning
    score = 100 - (overdue * 15) - (critical * 8) - (warning * 4)
    # Bonus for completion rate
    score += int((completed / total) * 10) if total else 0
    score = max(0, min(100, score))
    return {
        "score": score,
        "counts": {k: len(v) for k, v in buckets.items()},
        "totals": {"total": len(items), "completed": completed},
        "penalty_exposure": penalty_exposure,
        "buckets": buckets,
    }


DIGEST_SYSTEM = """You are a construction ops assistant. Write a concise weekly compliance digest (150-220 words, plain text) for a contractor owner. Use short paragraphs and one bullet block of top actions. Cover: overdue items, this-week deadlines, upcoming renewals, penalty exposure, next steps."""

@api.get("/compliance/digest")
async def compliance_digest(user: dict = Depends(get_current_user)):
    dash = await compliance_dashboard(user)
    items = await db.compliance.find({"owner_id": user["user_id"]}, {"_id": 0}).to_list(500)
    ctx = {"score": dash["score"], "counts": dash["counts"], "penalty_exposure": dash["penalty_exposure"],
           "overdue": dash["buckets"]["overdue"][:6], "critical": dash["buckets"]["critical"][:6],
           "warning": dash["buckets"]["warning"][:6], "items": [{"title": it["title"], "category": it.get("category"), "due": it.get("due_date"), "status": it.get("status")} for it in items[:30]]}
    prompt = json.dumps(ctx)[:3800]
    text = await ai_text(DIGEST_SYSTEM, prompt)
    return {"digest": text, "score": dash["score"], "penalty_exposure": dash["penalty_exposure"]}

# ---------------------------------------------------------------- regulation feed

class FeedIn(BaseModel):
    title: str
    source: str = ""
    category: str = "labour"
    region: str = ""
    summary: str = ""

FEED_QUERIES_BY_COUNTRY = {
    "IN": [
        ("GST construction CBIC notification India", "gst"),
        ("BOCW cess construction workers welfare India", "labour"),
        ("labour ministry wages construction notification India", "labour"),
        ("construction site safety scaffolding NBC India", "safety"),
        ("municipal corporation building bylaws permit India", "municipal"),
        ("CPWD tender notice construction India", "tender"),
        ("PWD eProcurement tender construction India", "tender"),
        ("environment clearance construction demolition waste India", "environment"),
        ("building plan approval rules India", "municipal"),
        ("minimum wages notification construction India", "labour"),
    ],
    "AE": [
        ("MOHRE UAE labour ministry construction rules", "labour_card"),
        ("WPS Wage Protection System UAE construction", "wps"),
        ("Emirates ID renewal residents workers UAE", "emirates_id"),
        ("GDRFA ICP UAE residence visa construction workers", "visa"),
        ("Dubai Municipality building permit approval", "municipality_noc"),
        ("Abu Dhabi Municipality DMT construction permit", "municipality_noc"),
        ("UAE Civil Defense NOC construction fire safety", "civil_defense"),
        ("DED trade license renewal UAE construction", "trade_license"),
        ("Dubai construction tender procurement", "tender"),
        ("UAE construction site safety OSH Trakhees", "safety"),
    ],
}
# Kept for any legacy references.
FEED_QUERIES = FEED_QUERIES_BY_COUNTRY["IN"]

def _fetch_feed(query: str, country: str = "IN"):
    ctx = COUNTRY_META.get(country, COUNTRY_META["IN"])
    url = (f"https://news.google.com/rss/search?q={quote(query)}"
           f"&hl={ctx['news_hl']}&gl={ctx['news_gl']}&ceid={ctx['news_ceid']}")
    resp = http_requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return feedparser.parse(resp.content)

@api.get("/feed")
async def list_feed(region: str = "", category: str = "", user: dict = Depends(get_current_user)):
    q: Dict[str, Any] = {"owner_id": user["user_id"]}
    if category:
        q["category"] = category
    docs = await db.reg_feed.find(q, {"_id": 0}).sort("created_at", -1).to_list(300)
    if region:
        r = region.strip().lower()
        def _match(d):
            rv = (d.get("region") or "").lower()
            if rv and (rv == r or r in rv or rv in r):
                return True
            # Fallback: match state/city inside title or summary text.
            hay = ((d.get("title") or "") + " " + (d.get("summary") or "")).lower()
            return r in hay
        docs = [d for d in docs if _match(d)]
    return docs

@api.post("/feed")
async def add_feed(body: FeedIn, user: dict = Depends(get_current_user)):
    doc = {
        "id": new_id(), "owner_id": user["user_id"], **body.model_dump(),
        "published_date": today_str(), "url": None, "verified": False, "impact": None, "created_at": now_iso(),
    }
    await db.reg_feed.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.post("/feed/fetch")
async def fetch_feed(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    country = user_country(user)
    ctx = country_ctx(country)
    queries = FEED_QUERIES_BY_COUNTRY.get(country, FEED_QUERIES_BY_COUNTRY["IN"])
    existing = set(d["url"] for d in await db.reg_feed.find({"owner_id": uid, "url": {"$ne": None}}, {"_id": 0, "url": 1}).to_list(2000))
    results = await asyncio.gather(*[asyncio.to_thread(_fetch_feed, q, country) for q, _ in queries], return_exceptions=True)
    added = 0
    for (query, category), parsed in zip(queries, results):
        if isinstance(parsed, Exception):
            logger.warning(f"Feed query failed [{query}]: {parsed}")
            continue
        for entry in parsed.entries[:2]:
            link = entry.get("link")
            if not link or link in existing:
                continue
            existing.add(link)
            publisher = ""
            try:
                publisher = entry.source.title
            except Exception:
                pass
            title = re.sub(r"\s+-\s+[^-]+$", "", entry.get("title", "")).strip()
            pub = entry.get("published", "")
            try:
                from email.utils import parsedate_to_datetime
                pub = parsedate_to_datetime(entry.published).strftime("%Y-%m-%d")
            except Exception:
                pub = today_str()
            summary = re.sub(r"<[^>]+>", "", entry.get("summary", "")).strip()[:400] or title
            await db.reg_feed.insert_one({
                "id": new_id(), "owner_id": uid, "title": title[:220],
                "source": publisher or f"Google News ({ctx['name']})",
                "category": category, "region": ctx["name"], "summary": summary,
                "published_date": pub, "url": link, "verified": True, "impact": None, "created_at": now_iso(),
            })
            added += 1
    return {"added": added}

IMPACT_SYSTEM = """You analyze how a regulatory/bureaucratic update impacts a specific Indian construction business.
Output JSON:
{"impact_summary": str, "urgency": "high"|"medium"|"low", "affected_projects": [str],
 "recommended_actions": [str], "deadline": "YYYY-MM-DD" or null}
affected_projects must only contain names from the provided project list (or be empty). Be practical and concrete."""

@api.post("/feed/{item_id}/impact")
async def analyze_impact(item_id: str, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    item = await db.reg_feed.find_one({"id": item_id, "owner_id": uid}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Feed item not found")
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(200)
    workers_count = await db.workers.count_documents({"owner_id": uid})
    subs = await db.subcontractors.find({"owner_id": uid}, {"_id": 0, "trade": 1}).to_list(200)
    prompt = (
        f"Company: {user.get('company_name')} — construction contractor, {workers_count} workers, "
        f"trades: {', '.join(set(s.get('trade', '') for s in subs if s.get('trade'))) or 'general civil'}.\n"
        f"Projects: {', '.join(p['name'] + ' (' + (p.get('location') or 'India') + ')' for p in projects) or 'none listed'}\n\n"
        f"Regulatory update:\nTitle: {item['title']}\nCategory: {item['category']}\nSource: {item['source']}\n"
        f"Region: {item.get('region')}\nSummary: {item['summary']}"
    )
    impact = await ai_json(IMPACT_SYSTEM, prompt)
    await db.reg_feed.update_one({"id": item_id}, {"$set": {"impact": impact}})
    item["impact"] = impact
    return item

FEED_TO_COMPLIANCE_CAT = {"labour": "registration", "gst": "registration", "safety": "safety", "municipal": "permit", "tender": "tender", "environment": "permit"}

@api.post("/feed/{item_id}/track")
async def track_feed(item_id: str, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    item = await db.reg_feed.find_one({"id": item_id, "owner_id": uid}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Feed item not found")
    impact = item.get("impact") or {}
    due = impact.get("deadline") or ""
    if due and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(due)):
        due = ""
    analysis = None
    if impact:
        analysis = {
            "summary": impact.get("impact_summary", ""),
            "what_changed": item.get("summary", ""),
            "who_is_affected": ", ".join(impact.get("affected_projects", [])) or "All projects",
            "deadline": impact.get("deadline") or "Not specified",
            "penalties": "",
            "actions_required": impact.get("recommended_actions", []),
            "risk_level": impact.get("urgency", "medium"),
        }
    doc = {
        "id": new_id(), "owner_id": uid, "title": item["title"],
        "category": FEED_TO_COMPLIANCE_CAT.get(item.get("category"), "permit"),
        "due_date": due, "document_text": item.get("summary", ""),
        "attachments": [], "analysis": analysis, "source_url": item.get("url"), "created_at": now_iso(),
    }
    await db.compliance.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.delete("/feed/{item_id}")
async def delete_feed(item_id: str, user: dict = Depends(get_current_user)):
    res = await db.reg_feed.delete_one({"id": item_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Feed item not found")
    return {"ok": True}

# ---------------------------------------------------------------- SOPs

class SopIn(BaseModel):
    title: str = ""
    category: str = "general"
    raw_input: str
    attachments: List[Dict[str, Any]] = []

SOP_SYSTEM = """You convert rough field descriptions/voice transcripts from Indian construction supervisors into structured SOPs.
Output JSON:
{"title": str, "objective": str, "steps": [str], "safety_precautions": [str], "inspection_points": [str],
 "required_tools": [str], "acceptance_criteria": [str], "escalation": str}
Steps must be imperative, sequenced and site-practical. Include IS-code references where relevant."""

@api.get("/sops")
async def list_sops(user: dict = Depends(get_current_user)):
    return await db.sops.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/sops/generate")
async def generate_sop(body: SopIn, user: dict = Depends(get_current_user)):
    prompt = f"Topic: {body.title or 'derive from description'}\nCategory: {body.category}\nRaw description/transcript:\n{body.raw_input[:6000]}"
    content = await ai_json(SOP_SYSTEM, prompt)
    doc = {
        "id": new_id(), "owner_id": user["user_id"], "title": body.title or content.get("title", "SOP"),
        "category": body.category, "raw_input": body.raw_input, "content": content,
        "attachments": body.attachments, "created_at": now_iso(),
    }
    await db.sops.insert_one({**doc})
    doc.pop("_id", None)
    return doc

# ---------------------------------------------------------------- knowledge / org memory

class KnowledgeIn(BaseModel):
    title: str
    content: str
    project_id: Optional[str] = None
    tags: List[str] = []

class AskIn(BaseModel):
    question: str

@api.get("/knowledge")
async def list_knowledge(user: dict = Depends(get_current_user)):
    return await db.knowledge.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(1000)

@api.post("/knowledge")
async def create_knowledge(body: KnowledgeIn, user: dict = Depends(get_current_user)):
    doc = {"id": new_id(), "owner_id": user["user_id"], **body.model_dump(), "created_at": now_iso()}
    await db.knowledge.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.post("/knowledge/ask")
async def ask_knowledge(body: AskIn, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    notes = await db.knowledge.find({"owner_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(200)
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(200)
    pmap = {p["id"]: p["name"] for p in projects}
    corpus = "\n\n".join(
        f"[{n.get('created_at', '')[:10]}] {n['title']}" + (f" (project: {pmap.get(n.get('project_id'), '')})" if n.get("project_id") else "") + f"\n{n['content']}\nTags: {', '.join(n.get('tags', []))}"
        for n in notes
    ) or "No knowledge captured yet."
    system = "You answer questions strictly from the company's captured organizational memory below. If the memory doesn't contain the answer, say so plainly and suggest what to capture. Be concise.\n\nCOMPANY MEMORY:\n" + corpus[:24000]
    answer = await ai_text(system, body.question)
    return {"answer": answer.strip()}

# ---------------------------------------------------------------- assistant

async def _assistant_answer(user: dict, question: str) -> str:
    uid = user["user_id"]
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
    txns = await db.transactions.find({"owner_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(3000)
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(200)
    subs = await db.subcontractors.find({"owner_id": uid}, {"_id": 0}).to_list(200)
    pmap = {p["id"]: p["name"] for p in projects}
    lines = []
    for w in workers:
        wt = [t for t in txns if t["worker_id"] == w["id"]]
        s = ledger_summary(wt)
        lines.append(
            f"- {w['name']} ({w['role']}, ₹{int(w.get('rate') or 0)}/{w.get('rate_type')}, project: {pmap.get(w.get('project_id'), 'unassigned')}): "
            f"earned ₹{int(s['earned'])}, advances ₹{int(s['advances'])}, deductions ₹{int(s['deductions'])}, net payable ₹{int(s['balance'])}"
        )
    sub_lines = []
    if subs:
        sub_ids = [s["id"] for s in subs]
        all_sub_txns = await db.sub_transactions.find({"sub_id": {"$in": sub_ids}}, {"_id": 0}).to_list(20000)
        sub_txns_map: Dict[str, List[dict]] = {}
        for t in all_sub_txns:
            sub_txns_map.setdefault(t.get("sub_id"), []).append(t)
        for s in subs:
            sm = sub_summary(s, sub_txns_map.get(s["id"], []))
            sub_lines.append(f"- {s['name']} ({s.get('firm', '')}, {s.get('trade', '')}): gross ₹{int(sm['gross'])}, paid ₹{int(sm['paid'])}, retention held ₹{int(sm['retention_held'])}, pending ₹{int(sm['pending'])}")
    today = today_str()
    cost_today = sum(t["amount"] for t in txns if t["type"] == "wage" and t.get("date") == today)
    recent = "\n".join(f"- {t.get('date')}: {t['type']} ₹{int(t['amount'])} for {next((w['name'] for w in workers if w['id'] == t['worker_id']), '?')} {('(' + t['note'] + ')') if t.get('note') else ''}" for t in txns[:40])
    system = (
        "You are the AI operations assistant for an Indian construction company on the Karya platform. "
        "Answer strictly from the operational data below. Use ₹ formatting. Be direct and short. Today is " + today + ".\n\n"
        f"PROJECTS: {', '.join(p['name'] for p in projects) or 'none'}\n"
        f"TODAY'S LABOUR COST: ₹{int(cost_today)}\n\nWORKER LEDGERS:\n" + ("\n".join(lines) or "none") +
        "\n\nSUBCONTRACTOR LEDGERS:\n" + ("\n".join(sub_lines) or "none") +
        "\n\nRECENT TRANSACTIONS:\n" + (recent or "none")
    )
    answer = await ai_text(system[:28000], question)
    return answer.strip()


@api.post("/assistant/ask")
async def assistant_ask(body: AskIn, user: dict = Depends(get_current_user)):
    return {"answer": await _assistant_answer(user, body.question)}

# ---------------------------------------------------------------- dashboard

@api.get("/dashboard/stats")
async def dashboard_stats(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(200)
    txns = await db.transactions.find({"owner_id": uid}, {"_id": 0}).to_list(5000)
    att = await db.attendance.find({"owner_id": uid}, {"_id": 0}).to_list(5000)
    comp = await db.compliance.find({"owner_id": uid}, {"_id": 0}).to_list(500)
    subs = await db.subcontractors.find({"owner_id": uid}, {"_id": 0}).to_list(200)

    today = today_str()
    present_today = sum(a.get("count", 1) for a in att if a.get("date") == today)
    cost_today = sum(t["amount"] for t in txns if t["type"] == "wage" and t.get("date") == today)
    total_paid = sum(t["amount"] for t in txns if t["type"] == "payment")
    total_adv = sum(t["amount"] for t in txns if t["type"] == "advance")
    pending = 0
    for w in workers:
        s = ledger_summary([t for t in txns if t["worker_id"] == w["id"]])
        pending += max(0, s["balance"])

    tdate = datetime.now(timezone.utc).date()
    score = 100
    alerts = []
    for c in comp:
        if not c.get("due_date"):
            continue
        try:
            due = datetime.strptime(c["due_date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        days = (due - tdate).days
        if days < 0:
            score -= 25
        elif days <= 7:
            score -= 10
        elif days <= 30:
            score -= 5
        if days <= 30:
            alerts.append({"id": c["id"], "title": c["title"], "due_date": c["due_date"], "category": c["category"], "_days": days})
    alerts.sort(key=lambda a: a["_days"])
    for a in alerts:
        a.pop("_days")

    trend = []
    for i in range(6, -1, -1):
        d = (tdate - timedelta(days=i)).strftime("%Y-%m-%d")
        trend.append({
            "date": d[5:],
            "cost": sum(t["amount"] for t in txns if t["type"] == "wage" and t.get("date") == d),
            "present": sum(a.get("count", 1) for a in att if a.get("date") == d),
        })

    project_spend = []
    for p in projects:
        wids = [w["id"] for w in workers if w.get("project_id") == p["id"]]
        spend = sum(t["amount"] for t in txns if t["worker_id"] in wids and t["type"] == "wage")
        project_spend.append({"name": p["name"], "spend": spend})

    sub_pending_total, retention_total, dues = 0, 0, []
    for s in subs:
        st = await db.sub_transactions.find({"sub_id": s["id"]}, {"_id": 0}).to_list(2000)
        sm = sub_summary(s, st)
        sub_pending_total += max(0, sm["pending"])
        retention_total += sm["retention_held"]
        dues.append({"name": s["name"], "paid": sm["paid"], "pending": sm["pending"]})
    dues.sort(key=lambda d: -d["pending"])

    missing_docs = sum(1 for w in workers if not all(w.get("onboarding", {}).get(k) for k in ONBOARDING_KEYS))

    return {
        "totals": {
            "workers": len(workers), "projects": len(projects), "present_today": present_today,
            "labour_cost_today": cost_today, "pending_settlements": pending, "total_paid": total_paid,
            "total_advances": total_adv, "compliance_health": max(0, score),
            "subcontractor_pending": sub_pending_total, "subcontractors": len(subs),
            "retention_held": retention_total, "workers_missing_docs": missing_docs,
        },
        "compliance_alerts": alerts[:8],
        "trend": trend,
        "project_spend": project_spend,
        "subcontractor_dues": dues[:5],
    }

# ---------------------------------------------------------------- notifications

class DismissIn(BaseModel):
    key: str

@api.get("/notifications")
async def notifications(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    dismissed = set(d["key"] for d in await db.dismissed_notifications.find({"owner_id": uid}, {"_id": 0, "key": 1}).to_list(2000))
    out = []
    tdate = datetime.now(timezone.utc).date()
    comp = await db.compliance.find({"owner_id": uid}, {"_id": 0}).to_list(500)
    for c in comp:
        if not c.get("due_date"):
            continue
        try:
            due = datetime.strptime(c["due_date"], "%Y-%m-%d").date()
        except ValueError:
            continue
        days = (due - tdate).days
        if days > 30:
            continue
        if days < 0:
            sev, msg = "critical", f"Overdue by {-days} day(s)"
        elif days <= 7:
            sev, msg = "critical", f"Due in {days} day(s)"
        elif days <= 14:
            sev, msg = "warning", f"Due in {days} days"
        else:
            sev, msg = "info", f"Due in {days} days"
        key = f"comp-{c['id']}-{c['due_date']}"
        out.append({"key": key, "title": c["title"], "message": msg, "severity": sev, "due_date": c["due_date"], "link": "/compliance", "dismissed": key in dismissed})
    feed = await db.reg_feed.find({"owner_id": uid, "impact.urgency": "high"}, {"_id": 0}).to_list(200)
    for f in feed:
        key = f"feed-{f['id']}"
        out.append({"key": key, "title": f["title"][:90], "message": "High-urgency regulatory impact on your business", "severity": "warning", "due_date": None, "link": "/feed", "dismissed": key in dismissed})
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
    no_ins = [w for w in workers if not w.get("onboarding", {}).get("insurance")]
    incomplete = [w for w in workers if not all(w.get("onboarding", {}).get(k) for k in ONBOARDING_KEYS)]
    if no_ins:
        key = f"workers-insurance-{len(no_ins)}"
        out.append({"key": key, "title": f"{len(no_ins)} worker(s) without insurance cover", "message": "Uninsured workers on site are a liability risk", "severity": "critical", "due_date": None, "link": "/workforce", "dismissed": key in dismissed})
    if incomplete:
        key = f"workers-docs-{len(incomplete)}"
        out.append({"key": key, "title": f"{len(incomplete)} worker(s) with incomplete onboarding", "message": "Documents / induction pending", "severity": "warning", "due_date": None, "link": "/workforce", "dismissed": key in dismissed})
    order = {"critical": 0, "warning": 1, "info": 2}
    out.sort(key=lambda n: order.get(n["severity"], 3))
    return {"unread": sum(1 for n in out if not n["dismissed"]), "notifications": out}

@api.post("/notifications/dismiss")
async def dismiss_notification(body: DismissIn, user: dict = Depends(get_current_user)):
    await db.dismissed_notifications.update_one(
        {"owner_id": user["user_id"], "key": body.key},
        {"$set": {"owner_id": user["user_id"], "key": body.key, "at": now_iso()}}, upsert=True,
    )
    return {"ok": True}

# ---------------------------------------------------------------- insights

@api.get("/insights")
async def insights(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(200)
    txns = await db.transactions.find({"owner_id": uid}, {"_id": 0}).to_list(5000)
    att = await db.attendance.find({"owner_id": uid}, {"_id": 0}).to_list(5000)
    comp = await db.compliance.find({"owner_id": uid}, {"_id": 0}).to_list(500)
    subs = await db.subcontractors.find({"owner_id": uid}, {"_id": 0}).to_list(200)

    tdate = datetime.now(timezone.utc).date()
    last7 = [(tdate - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
    present7 = sum(a.get("count", 1) for a in att if a.get("date") in last7)
    expected = max(1, len(workers) * 7)
    absenteeism = max(0, min(100, round(100 - present7 / expected * 100))) if workers else 0
    ls_level = "high" if absenteeism > 60 else "medium" if absenteeism > 30 else "low"

    overrun_rows, max_pct = [], 0
    for p in projects:
        wids = [w["id"] for w in workers if w.get("project_id") == p["id"]]
        spend = sum(t["amount"] for t in txns if t["worker_id"] in wids and t["type"] == "wage")
        budget = p.get("budget") or 0
        pct = round(spend / budget * 100, 1) if budget > 0 else 0
        max_pct = max(max_pct, pct)
        overrun_rows.append({"name": p["name"], "spend": spend, "budget": budget, "labour_pct_of_budget": pct})
    co_level = "high" if max_pct > 20 else "medium" if max_pct > 12 else "low"

    overdue = 0
    for c in comp:
        try:
            if c.get("due_date") and datetime.strptime(c["due_date"], "%Y-%m-%d").date() < tdate:
                overdue += 1
        except ValueError:
            pass
    delay_score = (absenteeism / 100) * 50 + min(overdue, 4) * 12.5
    dr_level = "high" if delay_score > 60 else "medium" if delay_score > 30 else "low"

    scorecards = []
    for s in subs:
        st = await db.sub_transactions.find({"sub_id": s["id"]}, {"_id": 0}).to_list(2000)
        sm = sub_summary(s, st)
        gross = sm["gross"] or 1
        penalty_ratio = sm["deductions"] / gross
        progress = min(1.0, sm["paid"] / sm["net_payable"]) if sm["net_payable"] > 0 else 0
        score = max(5, min(100, round(100 - penalty_ratio * 250 - (1 - progress) * 15)))
        rating = "A" if score >= 80 else "B" if score >= 60 else "C"
        scorecards.append({"id": s["id"], "name": s["name"], "trade": s.get("trade", ""), "score": score, "rating": rating, "deductions": sm["deductions"], "pending": sm["pending"]})
    scorecards.sort(key=lambda x: -x["score"])

    return {
        "has_data": bool(workers or projects or txns or att or comp or subs),
        "predictions": {
            "labour_shortage": {"level": ls_level, "metric": f"{absenteeism}% absenteeism", "detail": f"{present7} attendance marks across the last 7 days against ~{expected} expected worker-days." if workers else "Add workers to enable absenteeism tracking."},
            "cost_overrun": {"level": co_level, "metric": f"{max_pct}% labour/budget", "detail": "Highest labour-spend share of project budget across active projects." if projects else "Add project budgets to enable burn tracking."},
            "delay_risk": {"level": dr_level, "metric": f"{overdue} overdue items", "detail": "Combined signal from absenteeism and overdue compliance deadlines." if (workers or comp) else "Add workers or compliance deadlines to score delay risk."},
        },
        "subcontractor_scorecards": scorecards,
        "project_overrun": overrun_rows,
    }

@api.get("/insights/briefing")
async def insights_briefing(user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    data = await insights(user)
    workers_count = await db.workers.count_documents({"owner_id": uid})
    if workers_count == 0:
        return {"ai_summary": ""}
    system = "You are a construction operations risk analyst. Given operational signals, produce 3-5 short bullet lines (each starting with '- ') of the most important risks and one-line recommended actions. No preamble."
    prompt = json.dumps(data["predictions"]) + "\nProject burn: " + json.dumps(data["project_overrun"]) + "\nSubcontractor scorecards: " + json.dumps(data["subcontractor_scorecards"][:6])
    try:
        summary = await ai_text(system, prompt)
    except HTTPException:
        return {"ai_summary": ""}
    return {"ai_summary": summary.strip()}

# ---------------------------------------------------------------- daily reports
# (moved to routes/reports.py)

# ---------------------------------------------------------------- exports (pdf/docx/xlsx)
from exports import build_pdf, build_docx, build_xlsx, Section as ExportSection, MIME as EXPORT_MIME, safe_filename
from fastapi.responses import Response


def money(n) -> str:
    """Country-agnostic fallback; overridden per-request inside export endpoints."""
    return f"₹{int(n or 0):,}"


def _money_fn(user: dict):
    """Return a country-aware money formatter closure for a request."""
    return lambda n: money_str(n, user)


def _export_response(fmt: str, data: bytes, filename_stem: str) -> Response:
    if fmt not in EXPORT_MIME:
        raise HTTPException(status_code=400, detail="format must be pdf, docx or xlsx")
    fname = safe_filename(filename_stem, fmt)
    return Response(
        content=data,
        media_type=EXPORT_MIME[fmt],
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@api.get("/reports/{report_id}/export")
async def export_daily_report(report_id: str, format: str = "pdf", user: dict = Depends(get_current_user)):
    money = _money_fn(user)
    rec = await db.daily_reports.find_one({"id": report_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Report not found")
    c = rec.get("content") or {}
    title = c.get("title") or "Daily Site Report"
    subtitle = f"{rec.get('project_name') or 'Site'} · {rec.get('report_date') or ''}"
    if rec.get("location"):
        subtitle += f" · {rec['location']}"

    # Same-day attendance & wage totals for this project (adds operational context).
    q_att = {"owner_id": user["user_id"], "date": rec.get("report_date")}
    q_tx = {"owner_id": user["user_id"], "date": rec.get("report_date"), "type": "wage"}
    if rec.get("project_id"):
        q_att["project_id"] = rec["project_id"]
    att_docs = await db.attendance.find(q_att, {"_id": 0}).to_list(2000)
    present_today = sum(a.get("count", 1) for a in att_docs)
    tx_docs = await db.transactions.find(q_tx, {"_id": 0}).to_list(2000)
    if rec.get("project_id"):
        # Filter wage txns to workers belonging to this project.
        project_workers = await db.workers.find({"owner_id": user["user_id"], "project_id": rec["project_id"]}, {"_id": 0, "id": 1}).to_list(2000)
        pw_ids = {w["id"] for w in project_workers}
        tx_docs = [t for t in tx_docs if t.get("worker_id") in pw_ids]
    wage_today = sum(t["amount"] for t in tx_docs)

    sections = []
    if c.get("summary"):
        sections.append(ExportSection(heading="Summary", paragraphs=[c["summary"]]))
    if c.get("weather"):
        sections.append(ExportSection(heading="Weather", paragraphs=[c["weather"]]))
    if c.get("work_completed"):
        sections.append(ExportSection(heading="Work Completed", bullets=list(c["work_completed"])))
    if c.get("manpower"):
        sections.append(ExportSection(heading="Manpower", paragraphs=[c["manpower"]]))
    # Operational panel (attendance + spend for the day on this project).
    sections.append(ExportSection(
        heading="Attendance & Spend (this day)",
        table=[["Metric", "Value"],
               ["Workers present", str(present_today)],
               ["Wage cost", money(wage_today)],
               ["Attendance entries", str(len(att_docs))]],
    ))
    if c.get("materials_used"):
        sections.append(ExportSection(heading="Materials Used", bullets=list(c["materials_used"])))
    if c.get("issues_delays"):
        sections.append(ExportSection(heading="Issues / Delays", bullets=list(c["issues_delays"])))
    if c.get("safety_observations"):
        sections.append(ExportSection(heading="Safety Observations", bullets=list(c["safety_observations"])))
    if c.get("next_steps"):
        sections.append(ExportSection(heading="Next Steps", bullets=list(c["next_steps"])))
    if rec.get("notes_text"):
        sections.append(ExportSection(heading="Original Field Notes", paragraphs=[rec["notes_text"]]))

    if format in ("pdf", "docx"):
        # Attach photos (up to 4) only for PDF/DOCX.
        photo_bytes: List[bytes] = []
        for p in (rec.get("photos") or [])[:4]:
            if (p.get("content_type") or "").startswith("image/") and p.get("path"):
                try:
                    data, _ = await asyncio.to_thread(get_object, p["path"])
                    photo_bytes.append(data)
                except Exception as e:
                    logger.warning(f"Report export: photo fetch failed: {e}")
        if photo_bytes:
            sections.append(ExportSection(heading="Photos", images=photo_bytes))

    stem = f"Daily Report - {rec.get('project_name') or 'Site'} - {rec.get('report_date') or ''}"
    if format == "xlsx":
        rows = [["Field", "Value"], ["Title", title], ["Subtitle", subtitle]]
        for s in sections:
            for p in s.paragraphs:
                rows.append([s.heading or "", p])
            for b in s.bullets:
                rows.append([s.heading or "", f"- {b}"])
            if s.table:
                for r in s.table[1:]:
                    rows.append(r)
        data = build_xlsx(title, [{"name": "Report", "rows": rows}])
    elif format == "docx":
        data = build_docx(title, subtitle, sections)
    else:
        data = build_pdf(title, subtitle, sections)
    return _export_response(format, data, stem)


@api.get("/workers/{worker_id}/ledger/export")
async def export_worker_ledger(worker_id: str, format: str = "pdf", user: dict = Depends(get_current_user)):
    money = _money_fn(user)
    worker = await db.workers.find_one({"id": worker_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not worker:
        raise HTTPException(status_code=404, detail="Worker not found")
    txns = await db.transactions.find({"worker_id": worker_id, "owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(5000)
    s = ledger_summary(txns)
    project_name = "—"
    if worker.get("project_id"):
        p = await db.projects.find_one({"id": worker["project_id"], "owner_id": user["user_id"]}, {"_id": 0})
        if p:
            project_name = p["name"]

    title = f"Settlement Ledger — {worker['name']}"
    subtitle = f"{worker.get('role', '')} · {money(worker.get('rate') or 0)}/{worker.get('rate_type', '')} · Project: {project_name}"

    summary_table = [
        ["Metric", "Amount"],
        ["Earned", money(s["earned"])],
        ["Advances", money(s["advances"])],
        ["Deductions", money(s["deductions"])],
        ["Paid", money(s["paid"])],
        ["Net Payable", money(s["balance"])],
    ]
    txn_table = [["Date", "Type", "Amount", "Note"]] + [
        [t.get("date", ""), t.get("type", ""), money(t.get("amount", 0)), t.get("note", "")]
        for t in txns
    ]
    sections = [
        ExportSection(heading="Summary", table=summary_table),
        ExportSection(heading="Transactions", table=txn_table if len(txn_table) > 1 else [["Date", "Type", "Amount", "Note"], ["", "No entries", "", ""]]),
    ]
    stem = f"Ledger - {worker['name']}"
    if format == "xlsx":
        data = build_xlsx(title, [
            {"name": "Summary", "rows": summary_table},
            {"name": "Transactions", "rows": txn_table if len(txn_table) > 1 else [txn_table[0], ["", "No entries", "", ""]]},
        ])
    elif format == "docx":
        data = build_docx(title, subtitle, sections)
    else:
        data = build_pdf(title, subtitle, sections)
    return _export_response(format, data, stem)


@api.get("/payroll/export")
async def export_settlements(format: str = "xlsx", user: dict = Depends(get_current_user)):
    """Full settlements table across every worker (multi-sheet xlsx / summary table pdf/docx)."""
    money = _money_fn(user)
    uid = user["user_id"]
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).sort("created_at", -1).to_list(2000)
    txns = await db.transactions.find({"owner_id": uid}, {"_id": 0}).to_list(20000)
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(500)
    pmap = {p["id"]: p["name"] for p in projects}

    header = ["Worker", "Trade", "Project", "Rate", "Earned", "Advances", "Deductions", "Paid", "Net Payable"]
    rows: List[list] = [header]
    for w in workers:
        wt = [t for t in txns if t.get("worker_id") == w["id"]]
        s = ledger_summary(wt)
        rows.append([
            w.get("name", ""),
            w.get("role", ""),
            pmap.get(w.get("project_id"), "—"),
            f"Rs.{int(w.get('rate') or 0):,}/{w.get('rate_type', '')}",
            money(s["earned"]),
            money(s["advances"]),
            money(s["deductions"]),
            money(s["paid"]),
            money(s["balance"]),
        ])
    title = "Payroll Settlements"
    subtitle = f"{len(workers)} workers · exported {today_str()}"
    if format == "xlsx":
        # Include a second sheet with the raw transactions ledger.
        tx_rows = [["Date", "Worker", "Type", "Amount", "Note"]]
        wmap = {w["id"]: w["name"] for w in workers}
        for t in txns:
            tx_rows.append([
                t.get("date", ""),
                wmap.get(t.get("worker_id"), "?"),
                t.get("type", ""),
                money(t.get("amount", 0)),
                t.get("note", ""),
            ])
        data = build_xlsx(title, [
            {"name": "Settlements", "rows": rows},
            {"name": "Transactions", "rows": tx_rows},
        ])
    elif format == "docx":
        data = build_docx(title, subtitle, [ExportSection(table=rows)])
    else:
        data = build_pdf(title, subtitle, [ExportSection(table=rows)])
    return _export_response(format, data, "Payroll Settlements")


@api.get("/insights/export")
async def export_insights(format: str = "pdf", user: dict = Depends(get_current_user)):
    money = _money_fn(user)
    data = await insights(user)
    briefing = await insights_briefing(user)
    preds = data.get("predictions", {}) or {}
    title = "Predictive Insights"
    subtitle = f"Exported {today_str()}"

    pred_rows = [["Risk", "Level", "Metric", "Detail"]]
    for k, meta in preds.items():
        pred_rows.append([k.replace("_", " ").title(), meta.get("level", "-"), meta.get("metric", ""), meta.get("detail", "")])

    sc_rows = [["Subcontractor", "Trade", "Score", "Grade", "Deductions", "Pending"]]
    for s in data.get("subcontractor_scorecards", []) or []:
        sc_rows.append([s.get("name", ""), s.get("trade", ""), s.get("score", 0), s.get("rating", ""), money(s.get("deductions", 0)), money(s.get("pending", 0))])

    burn_rows = [["Project", "Labour Spend", "Budget", "% of Budget"]]
    for p in data.get("project_overrun", []) or []:
        burn_rows.append([p.get("name", ""), money(p.get("spend", 0)), money(p.get("budget", 0)), f"{p.get('labour_pct_of_budget', 0)}%"])

    ai_lines = [l for l in (briefing.get("ai_summary") or "").split("\n") if l.strip()]

    if format == "xlsx":
        out = build_xlsx(title, [
            {"name": "Predictions", "rows": pred_rows},
            {"name": "Subcontractors", "rows": sc_rows},
            {"name": "Project Burn", "rows": burn_rows},
            {"name": "AI Briefing", "rows": [["Insight"]] + [[l] for l in ai_lines]},
        ])
    else:
        sections = [
            ExportSection(heading="Risk Predictions", table=pred_rows),
            ExportSection(heading="Subcontractor Scorecards", table=sc_rows if len(sc_rows) > 1 else [sc_rows[0], ["No data", "", "", "", "", ""]]),
            ExportSection(heading="Project Labour Burn", table=burn_rows if len(burn_rows) > 1 else [burn_rows[0], ["No data", "", "", ""]]),
        ]
        if ai_lines:
            sections.append(ExportSection(heading="AI Briefing", bullets=ai_lines))
        if format == "docx":
            out = build_docx(title, subtitle, sections)
        else:
            out = build_pdf(title, subtitle, sections)
    return _export_response(format, out, "Predictive Insights")


@api.get("/compliance/export")
async def export_compliance(format: str = "pdf", user: dict = Depends(get_current_user)):
    items = await db.compliance.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("due_date", 1).to_list(2000)
    header = ["Title", "Category", "Due Date", "Status", "Notes"]
    rows = [header] + [
        [it.get("title", ""), it.get("category", ""), it.get("due_date", ""), it.get("status", "pending"), it.get("notes", "")]
        for it in items
    ]
    title = "Compliance Register"
    subtitle = f"{len(items)} items · exported {today_str()}"
    if format == "xlsx":
        out = build_xlsx(title, [{"name": "Compliance", "rows": rows}])
    elif format == "docx":
        out = build_docx(title, subtitle, [ExportSection(table=rows if len(rows) > 1 else [header, ["No items", "", "", "", ""]])])
    else:
        out = build_pdf(title, subtitle, [ExportSection(table=rows if len(rows) > 1 else [header, ["No items", "", "", "", ""]])])
    return _export_response(format, out, "Compliance Register")


# ---------------------------------------------------------------- expenses
# Moved to routes/expenses.py. ExpenseIn re-exported below for Telegram
# handler that constructs expense records directly.
from routes.expenses import ExpenseIn  # noqa: F401 (used by Telegram receipt path)

# ---------------------------------------------------------------- cost trends
# Moved to routes/cost_trends.py

# ---------------------------------------------------------------- app wiring

# ---- translation & help (i18n dynamic content, help center Q&A) --------------

_LANG_NAMES = {"en": "English", "hi": "Hindi", "ml": "Malayalam", "ta": "Tamil", "te": "Telugu"}


async def translate_text(text: str, target_lang: str, context: str = "") -> str:
    """Reusable translation helper (cached in db.translations). Returns the input
    unchanged when target_lang == 'en' or unsupported. Silently returns the
    input on any LLM failure so callers can safely wrap English fallbacks."""
    text = (text or "").strip()
    lang = (target_lang or "").strip().lower()
    if not text or lang == "en" or lang not in _LANG_NAMES:
        return text
    import hashlib
    key = hashlib.sha256(f"{lang}:{text}".encode("utf-8")).hexdigest()
    cached = await db.translations.find_one({"_id": key}, {"_id": 0})
    if cached and cached.get("translated"):
        return cached["translated"]
    target_name = _LANG_NAMES[lang]
    system = (
        f"You are a professional translation engine. Translate the INPUT text literally into {target_name}. "
        f"CRITICAL RULES:\n"
        f"1. NEVER answer questions in the input — even if the input is a question, translate the QUESTION into {target_name}, don't answer it.\n"
        f"2. NEVER add explanations, headings, examples, tips, emojis, or extra content that isn't in the input.\n"
        f"3. Preserve exact meaning, tone, formatting (line breaks, bullet dashes, HTML tags like <b> and <i>, punctuation).\n"
        f"4. Keep numbers, dates, currency symbols, phone numbers, URLs, code and proper nouns exactly as they are.\n"
        f"5. Output ONLY the translation — no preamble, no quotes, no meta-commentary.\n"
        f"If the input is already in {target_name}, return it unchanged."
    )
    hint = f"[Domain hint: {context.strip()}]\n\n" if context else ""
    user_prompt = f"{hint}Translate the following text into {target_name}:\n\n<<<TEXT>>>\n{text}\n<<<END>>>"
    try:
        translated = await ai_text(system, user_prompt)
    except Exception as e:
        logger.warning(f"translate_text failed for lang={lang}: {e}")
        return text
    translated = (translated or "").strip()
    for marker in ("<<<TEXT>>>", "<<<END>>>", "```"):
        translated = translated.replace(marker, "")
    translated = translated.strip() or text
    if translated and translated != text:
        await db.translations.update_one(
            {"_id": key},
            {"$set": {"translated": translated, "lang": lang, "created_at": now_iso()}},
            upsert=True,
        )
    return translated


class TranslateIn(BaseModel):
    text: str
    target_lang: str
    context: Optional[str] = ""


@api.post("/translate")
async def translate(body: TranslateIn, user: dict = Depends(get_current_user)):
    text = (body.text or "").strip()
    lang = (body.target_lang or "").strip().lower()
    if not text:
        raise HTTPException(status_code=400, detail="Nothing to translate.")
    if lang not in _LANG_NAMES:
        raise HTTPException(status_code=400, detail=f"Unsupported language '{lang}'.")
    translated = await translate_text(text, lang, body.context or "")
    return {"translated": translated, "cached": translated != text and translated is not None}


HELP_SYSTEM_PROMPT = (
    "You are the built-in help assistant for Karya, an AI operating system for small/mid-size "
    "construction contractors. Answer the user's how-to / troubleshooting question concisely "
    "(3–8 short sentences or 3–6 bullet dashes). Ground answers strictly in the capabilities below.\n\n"
    "CAPABILITIES:\n"
    "- Google sign-in only. Profile stores name, phone, company, country (India/UAE), language.\n"
    "- Workforce: projects, workers (trade, wage rate: daily/hourly/monthly/contract/piece), attendance, advances.\n"
    "- Payroll & Settlements: net-payable ledger per worker; settlements as cash/bank/UPI/WPS.\n"
    "- Daily Reports: AI writes from voice notes + photos; auto-send on WhatsApp via Twilio (sandbox or approved BSP number).\n"
    "- SOP Generator: activity-specific standard operating procedures with materials, safety, QC.\n"
    "- Compliance Agent: country-seeded checklist (IN: BOCW, GST, CLRA, ESIC/EPFO; AE: DED, MOHRE, EID, WPS, Civil Defense). AI penalty analysis.\n"
    "- Regulation Feed: live news + updates for the user's country.\n"
    "- Predictive Insights: labour-shortage / cost-overrun / delay-risk + subcontractor scorecards.\n"
    "- Subcontractors: contract value, retention %, deductions, pending balance.\n"
    "- Expenses: manual entries + Telegram-forwarded receipts (AI extracts vendor, amount, category).\n"
    "- Org Memory: durable notes + AI Q&A over saved knowledge.\n"
    "- Telegram bot @karya_ops_bot: link via 6-char code in Profile. Send text, voice notes, receipts, photos, PDFs. AI executes commands (advance, payment, attendance, tasks) and routes media (worker file / receipt / compliance / daily report / note). Voice notes get spoken TTS replies.\n"
    "- WhatsApp: Twilio-powered. Phone verification uses Twilio Verify (Profile → Verify phone)."
)


async def help_answer(question: str, lang: str = "en") -> str:
    lang_name = _LANG_NAMES.get(lang, "English")
    system = HELP_SYSTEM_PROMPT + f"\n\nReply in {lang_name}. If the user asks something Karya doesn't do, say so briefly and suggest the closest workflow."
    try:
        answer = await ai_text(system, question)
    except HTTPException:
        raise
    return (answer or "").strip()


class HelpAskIn(BaseModel):
    question: str


@api.post("/help/ask")
async def help_ask(body: HelpAskIn, user: dict = Depends(get_current_user)):
    question = (body.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="Ask a question.")
    lang = (user.get("language") or "en").lower()
    answer = await help_answer(question, lang)
    return {"answer": answer, "lang": lang}


# ---- proactive telegram pings ------------------------------------------------
# User-configurable morning briefing / compliance-deadline / payroll-reminder
# nudges sent via the linked Telegram bot. Runs as an in-process asyncio loop
# (wakes every 5 min), dedupes per-day via db.ping_log.

_DEFAULT_TZ_BY_COUNTRY = {"IN": "Asia/Kolkata", "AE": "Asia/Dubai"}

_PING_TYPES = ("morning_briefing", "compliance_alerts", "payroll_reminder")

_DEFAULT_NOTIFICATIONS = {
    "timezone": "Asia/Kolkata",
    # All three ping types are opt-in — user must enable them from Profile page.
    "morning_briefing": {"enabled": False, "time": "08:00"},
    "compliance_alerts": {"enabled": False},
    "payroll_reminder": {"enabled": False, "time": "09:00", "days": [1, 5]},
}


def _notifications_for(user: dict) -> Dict[str, Any]:
    """Merge user's saved notification prefs onto sensible defaults."""
    saved = user.get("notifications") or {}
    merged = {
        "timezone": saved.get("timezone") or _DEFAULT_TZ_BY_COUNTRY.get(user.get("country") or "IN", "Asia/Kolkata"),
        "morning_briefing": {**_DEFAULT_NOTIFICATIONS["morning_briefing"], **(saved.get("morning_briefing") or {})},
        "compliance_alerts": {**_DEFAULT_NOTIFICATIONS["compliance_alerts"], **(saved.get("compliance_alerts") or {})},
        "payroll_reminder": {**_DEFAULT_NOTIFICATIONS["payroll_reminder"], **(saved.get("payroll_reminder") or {})},
    }
    return merged


class NotificationsIn(BaseModel):
    # Kept as a re-export marker; the model + endpoints live in routes/telegram_prefs.py.
    timezone: Optional[str] = None
    morning_briefing: Optional[Dict[str, Any]] = None
    compliance_alerts: Optional[Dict[str, Any]] = None
    payroll_reminder: Optional[Dict[str, Any]] = None


# GET/PUT /telegram/notifications moved to routes/telegram_prefs.py


async def _ping_already_sent(uid: str, ping_type: str, day_key: str) -> bool:
    return bool(await db.ping_log.find_one({"user_id": uid, "type": ping_type, "day": day_key}))


async def _mark_ping_sent(uid: str, ping_type: str, day_key: str):
    await db.ping_log.update_one(
        {"user_id": uid, "type": ping_type, "day": day_key},
        {"$set": {"sent_at": now_iso()}},
        upsert=True,
    )


def _localtime_now(tz_name: str) -> Optional[datetime]:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    try:
        return datetime.now(ZoneInfo(tz_name))
    except (ZoneInfoNotFoundError, Exception):
        return None


def _within_window(now_local: datetime, hhmm: str, minutes: int = 6) -> bool:
    """True when the local clock is within `minutes` minutes AFTER hhmm."""
    try:
        h, m = hhmm.split(":")
        target = now_local.replace(hour=int(h), minute=int(m), second=0, microsecond=0)
    except Exception:
        return False
    delta = (now_local - target).total_seconds()
    return 0 <= delta < minutes * 60


async def _build_morning_briefing(user: dict) -> str:
    uid = user["user_id"]
    ctx = country_ctx(user)
    workers_total = await db.workers.count_documents({"owner_id": uid})
    projects_total = await db.projects.count_documents({"owner_id": uid})
    # Pending compliance within 14 days.
    today = date.today()
    horizon = (today + timedelta(days=14)).isoformat()
    comp_upcoming = await db.compliance.count_documents({
        "owner_id": uid, "status": {"$ne": "done"},
        "due_date": {"$gte": today.isoformat(), "$lte": horizon},
    })
    # Pending settlements = total balance owed to workers (accrued - paid - adv - deduct).
    txns = await db.transactions.find({"owner_id": uid}, {"_id": 0, "type": 1, "amount": 1}).to_list(20000)
    summary = ledger_summary(txns)
    pending = max(0, summary["balance"])
    day_name = today.strftime("%A, %d %b")
    lines = [
        f"☀️ <b>Good morning{', ' + user.get('name') if user.get('name') else ''}</b>",
        f"<i>{day_name}</i>",
        "",
        f"👷 {workers_total} worker{'' if workers_total == 1 else 's'} across {projects_total} project{'' if projects_total == 1 else 's'}",
        f"⏳ {comp_upcoming} compliance deadline{'' if comp_upcoming == 1 else 's'} in the next 14 days",
        f"💰 {money_str(pending, user)} pending settlements to workers",
    ]
    lines.append("")
    lines.append("Send <b>/report</b> for today's site briefing, or forward a receipt/photo any time.")
    return "\n".join(lines)


async def _build_compliance_pings(user: dict, now_local: datetime) -> List[tuple[str, str]]:
    """Returns [(ping_key, message)] for each compliance item hitting the D-3/D-1/D-0 window today."""
    uid = user["user_id"]
    today = now_local.date().isoformat()
    d1 = (now_local.date() + timedelta(days=1)).isoformat()
    d3 = (now_local.date() + timedelta(days=3)).isoformat()
    out = []
    cursor = db.compliance.find({
        "owner_id": uid,
        "status": {"$ne": "done"},
        "due_date": {"$in": [today, d1, d3]},
    }, {"_id": 0})
    async for item in cursor:
        due = item.get("due_date")
        if due == today:
            urgency, emoji = "TODAY", "🚨"
        elif due == d1:
            urgency, emoji = "tomorrow", "⚠️"
        else:
            urgency, emoji = "in 3 days", "🔔"
        ping_key = f"compliance:{item['id']}:{due}"
        msg = (
            f"{emoji} <b>Compliance due {urgency}</b>\n"
            f"<b>{item.get('title') or 'Untitled'}</b>"
            + (f"\nCategory: {item.get('category')}" if item.get("category") else "")
            + f"\nDue: <b>{due}</b>"
            + (f"\n<i>{item.get('notes')}</i>" if item.get("notes") else "")
        )
        out.append((ping_key, msg))
    return out


async def _build_payroll_reminder(user: dict) -> Optional[str]:
    uid = user["user_id"]
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
    if not workers:
        return None
    txns = await db.transactions.find({"owner_id": uid}, {"_id": 0}).to_list(20000)
    txns_by_worker: Dict[str, list] = {}
    for t in txns:
        txns_by_worker.setdefault(t.get("worker_id"), []).append(t)
    total_pending = 0.0
    top_lines: List[tuple[str, float]] = []
    for w in workers:
        s = ledger_summary(txns_by_worker.get(w["id"], []))
        if s["balance"] > 0:
            total_pending += s["balance"]
            top_lines.append((w.get("name") or "Worker", s["balance"]))
    if total_pending <= 0:
        return None
    top_lines.sort(key=lambda kv: -kv[1])
    top = top_lines[:5]
    lines = [
        "💸 <b>Payroll dues reminder</b>",
        f"Total pending: <b>{money_str(total_pending, user)}</b> across {len(top_lines)} worker{'' if len(top_lines) == 1 else 's'}",
        "",
        "<b>Top balances:</b>",
    ]
    for name, amt in top:
        lines.append(f"• {name} — {money_str(amt, user)}")
    if len(top_lines) > len(top):
        lines.append(f"…and {len(top_lines) - len(top)} more.")
    lines.append("\nSend <b>/pay Ramesh 8000</b> or open the Payroll page to settle.")
    return "\n".join(lines)


async def _send_ping(user: dict, ping_type: str, message: str, dedup_key: str):
    """Send `message` via Telegram and log to db.ping_log. Also localises to user's language.

    Idempotent: if a ping with the same (user_id, type, dedup_key) was already logged
    we skip the send entirely so retries/direct callers can't produce duplicates.
    """
    chat_id = user.get("telegram_chat_id")
    if not chat_id:
        return
    if await _ping_already_sent(user["user_id"], ping_type, dedup_key):
        return
    try:
        # Propagate user's language so tg_send auto-translates long messages.
        token = _TG_USER_LANG.set(user.get("language") or "en")
        try:
            await tg_send(int(chat_id), message)
        finally:
            _TG_USER_LANG.reset(token)
        await _mark_ping_sent(user["user_id"], ping_type, dedup_key)
    except Exception as e:
        logger.warning(f"ping {ping_type} to {user['user_id']} failed: {e}")


async def _run_pings_for_user(user: dict, now_utc: datetime):
    prefs = _notifications_for(user)
    tz_name = prefs["timezone"]
    now_local = _localtime_now(tz_name)
    if not now_local:
        return
    day_key = now_local.date().isoformat()

    # Morning briefing
    mb = prefs.get("morning_briefing") or {}
    if mb.get("enabled") and _within_window(now_local, mb.get("time") or "08:00"):
        if not await _ping_already_sent(user["user_id"], "morning_briefing", day_key):
            msg = await _build_morning_briefing(user)
            await _send_ping(user, "morning_briefing", msg, day_key)

    # Compliance alerts (D-3, D-1, D-0). Only fire once per (item, due_date).
    ca = prefs.get("compliance_alerts") or {}
    if ca.get("enabled"):
        # Fire once per day, at ~09:00 local time (same window logic).
        if _within_window(now_local, "09:00"):
            pings = await _build_compliance_pings(user, now_local)
            for ping_key, message in pings:
                if not await _ping_already_sent(user["user_id"], "compliance_alerts", f"{day_key}:{ping_key}"):
                    await _send_ping(user, "compliance_alerts", message, f"{day_key}:{ping_key}")

    # Payroll reminder — on selected weekdays at scheduled time.
    pr = prefs.get("payroll_reminder") or {}
    if pr.get("enabled"):
        weekday = now_local.isoweekday()  # 1..7
        days = pr.get("days") or [1, 5]
        if weekday in days and _within_window(now_local, pr.get("time") or "09:00"):
            if not await _ping_already_sent(user["user_id"], "payroll_reminder", day_key):
                msg = await _build_payroll_reminder(user)
                if msg:
                    await _send_ping(user, "payroll_reminder", msg, day_key)


_PING_LOOP_INTERVAL_SEC = 300  # 5 minutes
_PING_TASK: Optional[asyncio.Task] = None


async def _ping_scheduler_loop():
    logger.info("Telegram ping scheduler started (interval=%ss)", _PING_LOOP_INTERVAL_SEC)
    while True:
        try:
            if _tg_configured():
                # Only process users who linked Telegram — cheap indexed filter.
                cursor = db.users.find({"telegram_chat_id": {"$exists": True, "$ne": None}}, {"_id": 0})
                async for user in cursor:
                    try:
                        await _run_pings_for_user(user, datetime.now(timezone.utc))
                    except Exception as e:
                        logger.warning(f"ping run for {user.get('user_id')} failed: {e}")
        except Exception as e:
            logger.warning(f"ping loop iteration failed: {e}")
        await asyncio.sleep(_PING_LOOP_INTERVAL_SEC)



@api.get("/")
async def root():
    return {"status": "ok", "service": "Karya API"}

# Mount extracted routers
from routes.reports import build_router as _build_reports_router, Deps as _ReportsDeps
api.include_router(_build_reports_router(_ReportsDeps(
    db=db,
    get_current_user=get_current_user,
    new_id=new_id,
    now_iso=now_iso,
    today_str=today_str,
    get_object=get_object,
    ai_json=ai_json,
    image_content_cls=ImageContent,
    twilio_client=_twilio_client,
    twilio_from=TWILIO_WHATSAPP_FROM,
    twilio_rest_exception=TwilioRestException,
    build_signed_file_url=build_signed_file_url,
    backend_public_url=BACKEND_PUBLIC_URL,
    logger=logger,
)))

from routes.contact import build_router as _build_contact_router, Deps as _ContactDeps
api.include_router(_build_contact_router(_ContactDeps(
    db=db,
    new_id=new_id,
    now_iso=now_iso,
    rate_limit=rate_limit,
    tg_configured=_tg_configured,
    tg_send=tg_send,
    tg_user_lang=_TG_USER_LANG,
    company_legal_name=COMPANY_LEGAL_NAME,
    app_name=APP_NAME,
    contact_email=CONTACT_EMAIL,
    website="https://karyaai.app",
    logger=logger,
)))

from routes.attendance import build_router as _build_attendance_router
api.include_router(_build_attendance_router(_attendance_deps()))

from routes.cost_trends import build_router as _build_cost_trends_router, Deps as _CostTrendsDeps
api.include_router(_build_cost_trends_router(_CostTrendsDeps(
    db=db, get_current_user=get_current_user, country_ctx=country_ctx,
)))

from routes.expenses import build_router as _build_expenses_router, Deps as _ExpensesDeps
api.include_router(_build_expenses_router(_ExpensesDeps(
    db=db,
    get_current_user=get_current_user,
    new_id=new_id,
    now_iso=now_iso,
    today_str=today_str,
    country_ctx=country_ctx,
    money_str=money_str,
    rate_limit=rate_limit,
    put_object=put_object,
    extract_text=extract_text,
    ai_json=ai_json,
    image_content_cls=ImageContent,
    receipt_system=RECEIPT_SYSTEM,
    app_name=APP_NAME,
    logger=logger,
)))

from routes.telegram_prefs import build_router as _build_tg_prefs_router, Deps as _TgPrefsDeps
api.include_router(_build_tg_prefs_router(_TgPrefsDeps(
    db=db, get_current_user=get_current_user, notifications_for=_notifications_for,
)))

app.include_router(api)


# --- Security middleware -----------------------------------------------------

# CORS: default to explicit env allowlist; fall back to preview/prod Emergent domains
# via allow_origin_regex. When CORS_ORIGINS=* is set (recommended for Emergent
# deploys) we widen to any origin but automatically disable credentials so
# browsers don't reject the response. When a specific list is provided we keep
# credentials on so cookies + Authorization headers flow correctly.
_CORS_ENV = (os.environ.get("CORS_ORIGINS") or "").strip()
_CORS_ORIGINS = [o.strip() for o in _CORS_ENV.split(",") if o.strip()] if _CORS_ENV else []
_CORS_WILDCARD = "*" in _CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _CORS_WILDCARD else _CORS_ORIGINS,
    allow_origin_regex=None if _CORS_WILDCARD else r"https://([a-z0-9-]+\.)?(preview\.emergentagent\.com|emergent\.host|emergent\.sh|karyaai\.app)$",
    allow_credentials=not _CORS_WILDCARD,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Session-Token"],
    expose_headers=["Content-Length", "Content-Type"],
    max_age=86400,
)


@app.middleware("http")
async def _security_headers(request: Request, call_next):
    """Attach industry-standard security headers to every response.

    The frontend is served on karyaai.app + Emergent preview domains — none of
    which need to be embedded in third-party frames, so we default to DENY. We
    also disable the browser MIME-sniffer and turn on Referrer-Policy.
    """
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(self), geolocation=()")
    response.headers.setdefault(
        "Strict-Transport-Security",
        "max-age=31536000; includeSubDomains",
    )
    # A restrictive but functional CSP for the API. The React app is served from
    # a different host so this only protects direct API responses (rare misuse
    # vector but cheap to add).
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'none'; frame-ancestors 'none'; base-uri 'none';",
    )
    return response


# Payload size guard — the ingress caps at ~30MB but we also protect the app
# from oversized JSON bodies that would hog memory before the endpoint runs.
_MAX_BODY_BYTES = int(os.environ.get("MAX_REQUEST_BYTES", "26214400"))  # 25 MiB


@app.middleware("http")
async def _reject_oversize(request: Request, call_next):
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > _MAX_BODY_BYTES:
        return Response(
            content='{"detail":"Request body too large"}',
            status_code=413,
            media_type="application/json",
        )
    return await call_next(request)


@app.on_event("startup")
async def startup():
    try:
        await asyncio.to_thread(init_storage)
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed (will retry on first use): {e}")
    # Dedup index for ping_log so we never send the same ping twice on retry.
    try:
        await db.ping_log.create_index([("user_id", 1), ("type", 1), ("day", 1)], unique=True)
    except Exception as e:
        logger.warning(f"ping_log index create failed: {e}")
    # Kick off the proactive Telegram ping scheduler.
    global _PING_TASK
    if _PING_TASK is None or _PING_TASK.done():
        _PING_TASK = asyncio.create_task(_ping_scheduler_loop())
