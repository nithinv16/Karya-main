# Clerkworks.OS — AI Operating System for Construction

## Changelog
- 2026-02 (e): Shipped 4 features — (1) Twilio WhatsApp auto-send on Daily Reports (client/subs/labour/extra audience picker + per-report toggle + resend from detail modal); (2) top-nav "Signed in as {name}" chip fades in on /dashboard mount for ~6s; (3) "Copy diagnostics" link on the login error banner; (4) VoiceButton wired into AIAssistant chat. Also added first-run Profile Onboarding page (name/phone/company/role/address/default_client_phone) with `profile_complete` guard on all protected routes. Backend endpoints added: `PUT /api/auth/profile`, `POST /api/reports/{id}/whatsapp`; ProjectIn gains `client_phone`; ReportGenIn gains `whatsapp_send/audience/extra_numbers`. Verified 10/10 backend + 9/9 frontend (iteration_12.json). Twilio creds still needed — add TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN + TWILIO_WHATSAPP_FROM to `/app/backend/.env` to actually deliver messages.
- 2026-02 (d): Fixed cross-origin CORS block. Emergent's ingress rewrites `Access-Control-Allow-Origin` to `*`, which prohibits credentialed cookies. Switched auth to `Authorization: Bearer <token>` stored in `localStorage.karya_session_token`. Cookie path retained for same-origin. Verified 7/7 scenarios (iteration_11.json).
- 2026-02 (c): Added error transparency so future auth failures no longer silently bounce. Backend now returns `detail = "emergent_<code>: <body>"` and logs the full session_id. Login page shows a `[data-testid=auth-error-banner]` when `?auth_error=...` is present. Verified 5/5 (iteration_10.json).
- 2026-02 (b): Second fix for post-login redirect — root cause was React StrictMode double-mounting AuthCallback in dev, causing the one-time Emergent `session_id` to be POSTed twice: first call succeeded, second returned 401 (user_data_not_found) and its `window.location.replace('/')` overwrote the success redirect to `/dashboard`. Fix: module-scoped `let inFlight = false;` guard outside the component so only the first mount performs the exchange. Backend now also logs the Emergent response body on non-200. Verified 3/3 scenarios (iteration_9.json).
- 2026-02 (a): AuthCallback switched from `setUser + history.replaceState + navigate('/dashboard')` to hard `window.location.replace('/dashboard')`.

## Original Problem Statement
Build an AI-native operating system for the construction industry (India) solving informal workforce management, operational knowledge capture, compliance tracking, and process standardization. Six pillars: Workforce Intelligence, Compliance Intelligence (AI Bureaucracy Agent), Dynamic SOP Generation, Organizational Knowledge Management, Voice-First Operations, and Project Intelligence. Construction is the entry vertical; long-term vision is an operating backbone for fragmented/informal project-based economies.

## User Choices (v1)
- Scope: broad MVP touching all six pillars.
- AI model: agent's choice → Claude Sonnet 4.6 via Emergent LLM key.
- Voice: typed natural-language commands for now (real voice deferred).
- Auth: Emergent-managed Google login.
- Design: unique custom design (Swiss/high-contrast, orange accent, Cabinet Grotesk + IBM Plex Sans, Phosphor icons, sharp grid-border "control room" aesthetic).

## Architecture
- Backend: FastAPI (`/app/backend/server.py`), all routes under `/api`. MongoDB via motor. AI via `emergentintegrations` LlmChat (anthropic claude-sonnet-4-6) with a retry wrapper for transient proxy "budget exceeded" errors. Data scoped per company by `owner_id == user_id`.
- Auth: Emergent Google OAuth — `/api/auth/session` exchanges session_id, httpOnly cookie `session_token`, `/api/auth/me`, `/api/auth/logout`. `get_current_user` accepts cookie or Bearer.
- Frontend: React (CRA + craco, `@` alias), react-router, @tanstack/react-query, recharts, sonner, shadcn/ui, Phosphor icons. AuthContext + protected routes + AuthCallback hash handling.

## Implemented (2026-06-29)
### Iteration 1 — Core platform (all six pillars)
- Workforce Intelligence, Payroll & Settlements, NL Command Bar, AI Ops Assistant, Compliance Agent (AI analysis), Dynamic SOP Generation, Org Memory (Q&A), Project Intelligence dashboard, demo seed. Backend 16/16 + frontend 100% passed.

### Iteration 2 — Voice, Uploads, Notifications
- Real voice input: browser mic (MediaRecorder) → `/api/voice/transcribe` (OpenAI Whisper `whisper-1` via Emergent key) → command parser. Language selector for Hindi/Tamil/Malayalam/Kannada/Telugu/Marathi/Bengali/English/Auto. Mic on command bar (auto-runs command) and SOP generator (dictate procedure). STT has transient-error retry.
- File/PDF uploads via Emergent object storage: `/api/files/upload` (+ `/api/files/{path}` download with cookie/Bearer/`?auth=`). PDF/txt text auto-extracted to prefill compliance AI analysis. Attachments on compliance items and SOP source media. App prefix `clerkworks`, refs stored in `files` collection (soft-delete).
- Proactive deadline notifications: header bell + `/api/notifications` computing compliance due-date alerts (overdue/≤7d critical, ≤14d warning, ≤30d info) with per-user dismiss (`/api/notifications/dismiss`). Tested: 13/13 new-feature backend tests + frontend flows passed.

### Iteration 3 — Subcontractor Contract Ledger
- New `Subcontractors` module modeling informal subcontract economics: contract value, extra/additional work, owner-supplied material recovered, deductions/penalties, retention held (% of gross), retention release, and running payments/advances. `sub_summary()` computes net_payable = (contract + extra) − material − deductions − retention_held; pending = net_payable − paid.
- Endpoints: `/api/subcontractors` (GET/POST), `/api/subcontractors/{id}` (GET/DELETE, cascades sub_transactions), `/api/subcontractors/{id}/transactions` (POST, rejects ≤0). Collections: `subcontractors`, `sub_transactions`.
- Dashboard surfaces Subcontractor Dues + Retention Held tiles and a dues widget; AI assistant grounded on subcontractor ledger ("How much do I owe Sai Labour Suppliers?"). Demo seed adds 3 subcontractors with realistic ledgers. Tested: 18/18 backend + 100% frontend, no issues.

### Iteration 7 — Full platform rebuild + Daily Report Generator (2026-07-10)
- Fork arrived with the ENTIRE backend missing (only frontend committed to git). Rebuilt `/app/backend/server.py` from scratch to match the frontend API contract + this PRD: auth (Emergent Google OAuth, cookie+Bearer), workforce/projects, transactions/ledgers, subcontractor contract ledger, NL command parser (Claude), compliance agent + AI analyze, live RSS regulation feed + impact + track-to-compliance, SOP generator, org memory Q&A, ops assistant, dashboard stats, notifications (compliance deadlines + high-urgency feed + onboarding gaps, per-user dismiss), predictive insights + AI briefing, Whisper voice transcription, object-storage file uploads with PDF/txt text extraction. New Emergent LLM key configured; .env files recreated.
- **NEW: Daily Report Generator** (`/reports`, nav "Daily Reports"): field team uploads site photos + records a voice note (Whisper) + captures location (manual or browser geolocation) → Claude Sonnet 4.6 (vision) writes a professional daily report (title, summary, work completed, manpower, materials, issues/delays, safety observations, next steps). Endpoints: `POST /api/reports/generate` (photos passed as base64 ImageContent), `GET/DELETE /api/reports(/{id})`. Report archive + detail modal with photos.
- Login copy updated (live-data only, no demo). Tested: 36/36 backend + 100% frontend (iteration_7.json), zero issues. Verified Claude actually reads photo content in reports.

### Iteration 6 — Live-data-only + more official connectors + regulation→compliance
- **Removed ALL demo/sample data**: deleted `/api/seed/demo` and the AI "scan" (fabricated) feed. App runs on LIVE data only. UI scrubbed of "Load demo data" and "demo" copy; Dashboard empty state now guides real setup + live feed.
- **More official source connectors** (10 live RSS queries via Google News India, surfacing CBIC/GST, CPWD & state PWD & eProcurement tenders, BOCW/labour, NBC safety, municipal bylaws, environment/C&D). `POST /api/feed/fetch` pulls real, source-linked, deduped items (verified=true). Note: source links are Google News redirect URLs that resolve to the official issuer/publisher; publisher name shown on each card.
- **Regulation → Compliance**: `POST /api/feed/{id}/track` converts a live feed item into a tracked Compliance item (category mapping, deadline parsed from AI impact, analysis carried over, source URL embedded for audit). UI "Track in Compliance" button after impact analysis.
- Insights resilient on empty workspace. Tested: 10/10 backend + 100% frontend, no blockers (2 optional polish notes: resolve Google News redirect to direct publisher URL; async impact analysis).

### Iteration 5 — Rebrand to "Karya", proactive notifications, verified feeds, predictive insights
- Renamed product to **Karya** ("work gets done") across Login, sidebar, browser title.
- Notification bell now aggregates 3 sources with deep links: compliance deadlines (/compliance), high-urgency regulatory impacts (/feed), and onboarding gaps — workers without insurance (critical) / incomplete docs (warning) (/workforce). Dismiss persists.
- Real verified RSS connectors: `POST /api/feed/fetch` pulls live, source-linked construction-regulation updates (Google News India incl. PIB/gov publishers) via feedparser, deduped by URL, marked verified=true; AI scan retained as clearly-labelled "AI-curated draft". Feed cards show Verified badge + "Read original source" link.
- Predictive Insights page (`/insights`): heuristic labour-shortage / cost-overrun / delay-risk signals (absenteeism clamped 0-100), labour-spend-vs-budget table, subcontractor scorecards (score + A/B/C grade from deductions & progress), and a lazy-loaded AI Risk Briefing (`/api/insights/briefing`, non-blocking so page paints in ~0.2s). Tested: 12/12 backend + 100% frontend, no critical/minor blockers.

### Iteration 4 — Onboarding checklist, smarter voice intents, Bureaucracy Feed
- Per-worker onboarding compliance checklist (ID/Aadhaar, work agreement, safety induction, site access, insurance/WC, bank/UPI) — `onboarding` per worker, `POST /api/workers/{id}/onboarding`, ratio button + dialog in Workforce, `workers_missing_docs` + "Docs Pending" dashboard tile.
- Smarter NL command intents: `log_work_days` ("Rajesh worked 8 days" → 8 attendance + wage = days×rate) and `complete_task` ("Karthik completed 200 sqft tiling" → wage = qty×rate by rate_type + knowledge note). Works via typed and voice command bar.
- Autonomous Bureaucracy/Regulation Feed: AI agent curates construction-relevant labour/GST/safety/municipal/tender/environment updates (`POST /api/feed/scan`), per-item AI impact analysis vs company profile (`POST /api/feed/{id}/impact` → affected projects, urgency, recommended actions), manual add + delete. New "Regulation Feed" page. Demo seed adds 4 items. Collection: `reg_feed`. Tested: 16/16 backend + 100% frontend, no issues.

## Personas
- Builder/contractor owner (dashboards, settlements, compliance health).
- Site supervisor / labour contractor (command bar, attendance, advances — low digital literacy, field use).
- Project/office manager (org memory, SOPs, compliance).

## Backlog
- P0: Real voice input (browser mic → Whisper STT → command pipeline) in 7 Indian languages.
- P1: Document/file upload (object storage) for compliance PDFs & SOP source media; OCR.
- P1: Proactive compliance notifications (email/WhatsApp) on approaching deadlines.
- P1: Attendance via QR / mobile check-in; crew/shift management.
- P2: Predictive analytics (labour shortage, cost overrun, delay risk); subcontractor scorecards.
- P2: Multi-user roles per company (supervisor vs owner) + invitations.
- P2: WhatsApp integration for command intake.

## Next Tasks
1. Share/export Daily Reports (PDF export, WhatsApp share link to client).
2. Multi-user roles per company (field employee vs owner) + invitations, so field staff submit reports from their own logins.
3. Email/WhatsApp delivery of compliance deadline notifications.
4. Reverse-geocode report location (lat/long → address).
