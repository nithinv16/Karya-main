import os
import io
import re
import json
import uuid
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
from emergentintegrations.llm.openai import OpenAISpeechToText

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

app = FastAPI(title="Karya API")
api = APIRouter(prefix="/api")

ONBOARDING_KEYS = ["id_collected", "contract_signed", "induction_done", "site_access", "insurance", "bank_details"]
EARN_TYPES = ["wage", "payment", "bonus"]
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

async def ai_text(system: str, prompt: str, images: Optional[list] = None) -> str:
    last_err = None
    for attempt in range(3):
        try:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"karya-{uuid.uuid4().hex[:10]}",
                system_message=system,
            ).with_model("anthropic", "claude-sonnet-4-6")
            msg = UserMessage(text=prompt, file_contents=images) if images else UserMessage(text=prompt)
            resp = await chat.send_message(msg)
            return resp if isinstance(resp, str) else str(resp)
        except Exception as e:
            last_err = e
            logger.warning(f"AI attempt {attempt + 1} failed: {e}")
            await asyncio.sleep(1.5 * (attempt + 1))
    raise HTTPException(status_code=502, detail=f"AI temporarily unavailable: {last_err}")

async def ai_json(system: str, prompt: str, images: Optional[list] = None) -> dict:
    for attempt in range(2):
        raw = await ai_text(system, prompt + "\nRespond with ONLY a valid JSON object, no prose.", images)
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
        raise HTTPException(status_code=401, detail="Invalid session_id")
    data = resp.json()
    user = await db.users.find_one({"email": data["email"]}, {"_id": 0})
    if not user:
        user = {
            "user_id": f"user_{uuid.uuid4().hex[:12]}",
            "email": data["email"],
            "name": data.get("name", ""),
            "picture": data.get("picture", ""),
            "company_name": f"{(data.get('name') or 'My').split()[0]}'s Construction Co.",
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
    return user

@api.get("/auth/me")
async def auth_me(user: dict = Depends(get_current_user)):
    return user

@api.post("/auth/logout")
async def logout(request: Request, response: Response):
    token = request.cookies.get("session_token")
    if token:
        await db.user_sessions.delete_one({"session_token": token})
    response.delete_cookie("session_token", path="/", secure=True, samesite="none")
    return {"ok": True}

# ---------------------------------------------------------------- projects & workers

class ProjectIn(BaseModel):
    name: str
    location: str = ""
    client: str = ""
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
    return {"earned": earned, "advances": advances, "deductions": deductions, "balance": earned - advances - deductions}

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
    out = []
    for s in subs:
        txns = await db.sub_transactions.find({"sub_id": s["id"]}, {"_id": 0}).to_list(2000)
        out.append({**s, "summary": sub_summary(s, txns)})
    return out

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
async def download_file(path: str, request: Request, auth: Optional[str] = Query(None)):
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

# ---------------------------------------------------------------- voice

@api.post("/voice/transcribe")
async def voice_transcribe(file: UploadFile = File(...), language: str = Form("auto"), user: dict = Depends(get_current_user)):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty audio")
    buf = io.BytesIO(data)
    buf.name = file.filename or "clip.webm"
    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    kwargs = {}
    if language and language != "auto":
        kwargs["language"] = language
    last_err = None
    for attempt in range(3):
        try:
            buf.seek(0)
            resp = await stt.transcribe(file=buf, model="whisper-1", response_format="json", **kwargs)
            return {"text": (resp.text or "").strip()}
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.2 * (attempt + 1))
    raise HTTPException(status_code=502, detail=f"Transcription failed: {last_err}")

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
    uid = user["user_id"]
    workers = await db.workers.find({"owner_id": uid}, {"_id": 0}).to_list(1000)
    projects = await db.projects.find({"owner_id": uid}, {"_id": 0}).to_list(500)
    prompt = (
        f"Known workers: {', '.join(w['name'] for w in workers) or 'none'}\n"
        f"Known projects: {', '.join(p['name'] for p in projects) or 'none'}\n"
        f"Command: {body.text}"
    )
    try:
        parsed = await ai_json(COMMAND_SYSTEM, prompt)
    except HTTPException:
        return {"applied": False, "summary": "Couldn't reach the AI parser. Try again."}
    intent = parsed.get("intent", "unknown")

    def rupees(n):
        return f"₹{int(n or 0):,}"

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
            "amount": amount, "note": parsed.get("note") or f"Via command: {body.text[:80]}",
            "date": today_str(), "created_at": now_iso(),
        })
        return {"applied": True, "summary": f"Recorded {intent} of {rupees(amount)} for {worker['name']}."}

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
        return {"applied": True, "summary": f"Logged {days} day(s) for {worker['name']} — wage {rupees(wage)}."}

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
                "amount": wage, "note": f"Task: {parsed.get('note') or body.text[:80]}", "date": today_str(), "created_at": now_iso(),
            })
        await db.knowledge.insert_one({
            "id": new_id(), "owner_id": uid, "title": f"Task completed — {worker['name']}",
            "content": body.text, "project_id": worker.get("project_id"), "tags": ["task", "command"],
            "created_at": now_iso(),
        })
        return {"applied": True, "summary": f"Logged task for {worker['name']}" + (f" — wage {rupees(wage)}." if wage > 0 else ".")}

    return {"applied": False, "summary": "I couldn't understand that command. Try e.g. \"Ramesh took an advance of ₹5000\"."}

# ---------------------------------------------------------------- compliance

class ComplianceIn(BaseModel):
    title: str
    category: str = "permit"
    due_date: str = ""
    document_text: str = ""
    attachments: List[Dict[str, Any]] = []

@api.get("/compliance")
async def list_compliance(user: dict = Depends(get_current_user)):
    return await db.compliance.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.post("/compliance")
async def create_compliance(body: ComplianceIn, user: dict = Depends(get_current_user)):
    doc = {"id": new_id(), "owner_id": user["user_id"], **body.model_dump(), "analysis": None, "created_at": now_iso()}
    await db.compliance.insert_one({**doc})
    doc.pop("_id", None)
    return doc

COMPLIANCE_SYSTEM = """You are a compliance analyst for Indian construction businesses (permits, licenses, BOCW, GST, labour laws, municipal approvals, tenders, insurance).
Analyze the given compliance item/document and output JSON:
{"summary": str, "what_changed": str, "who_is_affected": str, "deadline": str, "penalties": str,
 "actions_required": [str], "risk_level": "high"|"medium"|"low"}
Be specific and practical for a small/mid contractor. If the document text is thin, infer from the title and category."""

@api.post("/compliance/{item_id}/analyze")
async def analyze_compliance(item_id: str, user: dict = Depends(get_current_user)):
    item = await db.compliance.find_one({"id": item_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    prompt = (
        f"Title: {item['title']}\nCategory: {item['category']}\nDue date: {item.get('due_date') or 'unknown'}\n"
        f"Document text:\n{(item.get('document_text') or '')[:5000]}"
    )
    analysis = await ai_json(COMPLIANCE_SYSTEM, prompt)
    await db.compliance.update_one({"id": item_id}, {"$set": {"analysis": analysis}})
    item["analysis"] = analysis
    return item

# ---------------------------------------------------------------- regulation feed

class FeedIn(BaseModel):
    title: str
    source: str = ""
    category: str = "labour"
    region: str = ""
    summary: str = ""

FEED_QUERIES = [
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
]

def _fetch_feed(query: str):
    url = f"https://news.google.com/rss/search?q={quote(query)}&hl=en-IN&gl=IN&ceid=IN:en"
    resp = http_requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    return feedparser.parse(resp.content)

@api.get("/feed")
async def list_feed(user: dict = Depends(get_current_user)):
    return await db.reg_feed.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(300)

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
    existing = set(d["url"] for d in await db.reg_feed.find({"owner_id": uid, "url": {"$ne": None}}, {"_id": 0, "url": 1}).to_list(2000))
    results = await asyncio.gather(*[asyncio.to_thread(_fetch_feed, q) for q, _ in FEED_QUERIES], return_exceptions=True)
    added = 0
    for (query, category), parsed in zip(FEED_QUERIES, results):
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
                "id": new_id(), "owner_id": uid, "title": title[:220], "source": publisher or "Google News (India)",
                "category": category, "region": "India", "summary": summary,
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

@api.post("/assistant/ask")
async def assistant_ask(body: AskIn, user: dict = Depends(get_current_user)):
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
    for s in subs:
        st = await db.sub_transactions.find({"sub_id": s["id"]}, {"_id": 0}).to_list(2000)
        sm = sub_summary(s, st)
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
    answer = await ai_text(system[:28000], body.question)
    return {"answer": answer.strip()}

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
        "predictions": {
            "labour_shortage": {"level": ls_level, "metric": f"{absenteeism}% absenteeism", "detail": f"{present7} attendance marks across the last 7 days against ~{expected} expected worker-days."},
            "cost_overrun": {"level": co_level, "metric": f"{max_pct}% labour/budget", "detail": "Highest labour-spend share of project budget across active projects." if projects else "Add project budgets to enable burn tracking."},
            "delay_risk": {"level": dr_level, "metric": f"{overdue} overdue items", "detail": "Combined signal from absenteeism and overdue compliance deadlines."},
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

# ---------------------------------------------------------------- daily reports (NEW)

class ReportGenIn(BaseModel):
    project_id: Optional[str] = None
    location: str = ""
    notes_text: str = ""
    photo_ids: List[str] = []
    report_date: Optional[str] = None

REPORT_SYSTEM = """You write professional daily site reports for construction & maintenance companies in India.
You receive field notes (often a rough voice-note transcript), site photos, a location and a date.
Study the photos carefully — describe visible work, progress, equipment, materials and any safety issues you can see.
Output JSON:
{"title": str, "summary": str, "weather": str|null, "work_completed": [str], "manpower": str,
 "materials_used": [str], "issues_delays": [str], "safety_observations": [str], "next_steps": [str]}
Keep it factual and professional — this report goes to the client/management. If a field is unknown, use an empty list or null."""

@api.post("/reports/generate")
async def generate_report(body: ReportGenIn, user: dict = Depends(get_current_user)):
    uid = user["user_id"]
    if not body.notes_text.strip() and not body.photo_ids:
        raise HTTPException(status_code=400, detail="Provide field notes or at least one photo")
    project = None
    if body.project_id:
        project = await db.projects.find_one({"id": body.project_id, "owner_id": uid}, {"_id": 0})
    photos = []
    images = []
    for fid in body.photo_ids[:4]:
        rec = await db.files.find_one({"id": fid, "owner_id": uid, "is_deleted": False}, {"_id": 0})
        if not rec:
            continue
        photos.append(rec)
        if (rec.get("content_type") or "").startswith("image/"):
            try:
                data, _ = await asyncio.to_thread(get_object, rec["path"])
                images.append(ImageContent(image_base64=base64.b64encode(data).decode()))
            except Exception as e:
                logger.warning(f"Photo fetch failed: {e}")
    rdate = body.report_date or today_str()
    prompt = (
        f"Project: {project['name'] if project else 'Not specified'}"
        + (f" ({project.get('location')}, client: {project.get('client')})" if project else "") + "\n"
        f"Report date: {rdate}\nLocation: {body.location or 'Not specified'}\n"
        f"Field notes / voice transcript:\n{body.notes_text.strip() or '(none — rely on the photos)'}\n"
        f"Photos attached: {len(images)}"
    )
    content = await ai_json(REPORT_SYSTEM, prompt, images=images or None)
    doc = {
        "id": new_id(), "owner_id": uid, "project_id": body.project_id,
        "project_name": project["name"] if project else None,
        "location": body.location, "notes_text": body.notes_text,
        "report_date": rdate, "photos": photos, "content": content, "created_at": now_iso(),
    }
    await db.daily_reports.insert_one({**doc})
    doc.pop("_id", None)
    return doc

@api.get("/reports")
async def list_reports(user: dict = Depends(get_current_user)):
    return await db.daily_reports.find({"owner_id": user["user_id"]}, {"_id": 0}).sort("created_at", -1).to_list(500)

@api.get("/reports/{report_id}")
async def get_report(report_id: str, user: dict = Depends(get_current_user)):
    rec = await db.daily_reports.find_one({"id": report_id, "owner_id": user["user_id"]}, {"_id": 0})
    if not rec:
        raise HTTPException(status_code=404, detail="Report not found")
    return rec

@api.delete("/reports/{report_id}")
async def delete_report(report_id: str, user: dict = Depends(get_current_user)):
    res = await db.daily_reports.delete_one({"id": report_id, "owner_id": user["user_id"]})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Report not found")
    return {"ok": True}

# ---------------------------------------------------------------- app wiring

@api.get("/")
async def root():
    return {"status": "ok", "service": "Karya API"}

app.include_router(api)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.environ.get("CORS_ORIGINS", "*").split(",")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def startup():
    try:
        await asyncio.to_thread(init_storage)
        logger.info("Object storage initialized")
    except Exception as e:
        logger.error(f"Storage init failed (will retry on first use): {e}")
