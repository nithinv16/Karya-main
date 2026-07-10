# Karya — AI OS for Construction

## Original Problem Statement
Karya-main repo (construction ops platform: workforce, payroll, subcontractors, daily reports, compliance, SOPs, org memory; Emergent Google OAuth). Latest request (2026-06):
1. Connect platform to Telegram like OpenClaw — users send voice/images/details/receipts; AI processes and asks what to do (e.g. photo of a labourer → "upload it under the labor's name").
2. Enhance UI/UX.
3. Mobile-friendly — feel exactly like a mobile app (PWA installable).

## User Choices
- Telegram bot token provided by user (@karya_ops_bot)
- OpenAI GPT (gpt-4o via Emergent Universal Key) for Telegram media processing
- Per-user linking via code shown in web app (Profile page)
- Responsive mobile-app UI + PWA
- Replace all Emergent keys with new one + NEW database

## Environment (2026-06, fork)
- backend/.env recreated: MONGO_URL local, DB_NAME=karya_db_v2 (NEW db), EMERGENT_LLM_KEY=sk-emergent-192096dD6E97559Fa0, TELEGRAM_BOT_TOKEN + TELEGRAM_WEBHOOK_SECRET=karya-tg-hook-7f3a9c2e, BACKEND_PUBLIC_URL/CORS = https://63eb8f53-e1d3-4702-9386-8e98d5fd8498.preview.emergentagent.com
- frontend/.env recreated with matching REACT_APP_BACKEND_URL

## What's Implemented (this session)
### Telegram conversational agent (server.py)
- Webhook auto-registered on startup (`_tg_autoregister_webhook`), secret-header validated
- Link flow: Profile → Connect Telegram → 6-char code → /start CODE (deep link supported)
- Text commands via `_execute_command` (add worker, advance, payment, attendance, log days, tasks — multi-language)
- Conversational fallback: unknown text answered from operational data (`_assistant_answer`)
- Voice notes → Whisper transcription → command execution
- Pending-media agent: photos/PDFs stored in object storage → bot asks "what should I do?" with inline keyboard (Daily report / Worker file / Receipt / Compliance / Note / Discard) OR routes free-text/caption instructions via gpt-4o router
  - worker_file: attaches to worker.documents (asks "which worker?" if unclear)
  - receipt: gpt-4o vision parses receipt → db.expenses + knowledge note
  - daily_report: telegram_wip draft → /report generates the daily report
  - compliance: creates item + AI analysis
  - knowledge: saves to Org Memory
- callback_query handling for inline buttons
- Fixed pre-existing bugs: `body.text` refs in `_execute_command`, corrupt trailing line in startup handler

### Frontend
- TelegramConnect.js card on Profile: code generation, deep link, live polling until linked, unlink
- AppLayout.js mobile overhaul: bottom tab bar (Home/Workforce/Reports/Payroll/More), More slide-up sheet (all modules + profile + signout), mobile AI FAB, safe-area insets, press micro-animations
- Workforce.js: worker documents list (Telegram uploads) in worker dialog
- PWA: manifest.json, sw.js (cache strategy), icons 192/512, apple/mobile meta tags, SW registration
- index.css: mobile polish (16px inputs to prevent iOS zoom, tap targets, sheet/fade animations, Emergent badge repositioned on mobile)

## Testing
- iteration_20.json: 12/12 backend pytest pass, all frontend flows pass (mobile nav, sheet, FAB, Telegram card, desktop regression)
- Regression suite: /app/backend/tests/test_iteration20_telegram.py
- QA creds: Bearer test_session_karya1 (see memory/test_credentials.md)

## Backlog / Next
- P1: Expenses page in web UI (receipts currently visible via Org Memory; db.expenses has structured data)
- P1: Let user pick project when generating /report from Telegram (currently most-recent project)
- P2: Telegram notifications push (compliance deadlines, payroll dues)
- P2: Split server.py into modules (~2500 lines)
- P2: WhatsApp (Twilio) still inactive — needs real Twilio creds
