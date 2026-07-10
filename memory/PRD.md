# Clerkworks.OS — AI Operating System for Construction

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
1. Add real voice-first input (Whisper STT) feeding the existing command parser.
2. Add file uploads + object storage for compliance documents and SOP media.
3. Deadline notification engine for compliance alerts.
