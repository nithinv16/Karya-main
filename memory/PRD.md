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
- iteration_21.json (2026-07, bug fix): 9/9 backend pytest pass — Telegram webhook race-condition fix (preview↔production) verified end-to-end.
- Regression suite: /app/backend/tests/test_iteration20_telegram.py, /app/backend/tests/test_iteration21_telegram_link_race.py
- QA creds: Bearer test_session_karya1 (see memory/test_credentials.md)

## Bug Fixes (2026-07)
- **Telegram "That linking code isn't valid" bug**: A Telegram bot has ONE global webhook. Preview + Production backends were both auto-registering it on startup, so codes generated in one env's isolated Mongo were validated by the OTHER env's backend → "invalid code". Fix:
  - `_tg_autoregister_webhook` now SKIPS on preview host (`preview.emergentagent.com`); override via `TELEGRAM_AUTO_REGISTER_WEBHOOK=true`.
  - `POST /api/telegram/link/code` now atomically re-claims the webhook for the calling backend, guaranteeing `/start CODE` lands where the code lives.
  - "invalid code" reply is now actionable (tells user to regenerate on the same Karya URL they signed up on).
  - `_handle_tg_start` also tolerates whitespace / `@botusername` prefixes on the code arg.

## Iteration 22 batch (2026-07)
1. **Service worker bug (`sw.js:1 Failed to convert value to 'Response'`)**: old SW returned `undefined` from `respondWith` when both network and cache misses happened (e.g. deployed 502s on `/reports`, SOP generator). Rewrote `/app/frontend/public/sw.js` to `karya-v3` cache, always resolves to a real `Response`, adds offline HTML fallback for navigation requests.
2. **Twilio WhatsApp "From number not valid"**: `TWILIO_WHATSAPP_FROM=""` (empty env var) was overriding the sandbox default because `os.environ.get("X", "default")` returns `""` — not the default — when `X` is present but empty. Fixed with `(os.environ.get(...) or "").strip() or default`.
3. **Twilio Verify (phone OTP) added**: new endpoints `POST /api/profile/phone/verify/start`, `POST /api/profile/phone/verify/check`, `GET /api/profile/phone/verify/status`. Sets `users.phone_verified=true` + `phone_verified_at` on approval. Gracefully returns 503 when `TWILIO_VERIFY_SERVICE_SID` isn't configured. Frontend: new `PhoneVerify` component mounted on Profile page.
4. **Predictive Insights empty state**: `/api/insights` now returns `has_data: bool`; UI renders an empty-state CTA card (linking to Workforce + Subcontractors) when the user has no workers/projects/attendance/etc — no more fake risk metrics.
5. **Demo/mock data removed**: The compliance starter kit seeded on first country selection (BOCW Cess, WPS, etc.) is legitimate regulatory content, not demo data — retained. No other hardcoded mock values found in dashboard/reports/payroll — everything is data-driven.

## Testing
- iteration_20.json: 12/12 backend + all frontend flows.
- iteration_21.json: 9/9 backend — Telegram webhook race-condition fix verified.
- iteration_22.json (2026-07): 10/10 backend — phone verify graceful 503, TWILIO_WHATSAPP_FROM default normalization, insights has_data flag, telegram + dashboard regressions.
- Regression suite: `/app/backend/tests/test_iteration20_telegram.py`, `test_iteration21_telegram_link_race.py`, `test_iteration22_phone_verify_insights.py`.

## Configuration required for full functionality
- `TWILIO_ACCOUNT_SID` / `TWILIO_AUTH_TOKEN` — enables WhatsApp send + phone verify.
- `TWILIO_VERIFY_SERVICE_SID` (new) — create a Verify service at https://console.twilio.com → Verify → Services, paste the `VA...` SID here to enable phone OTP.
- `TWILIO_WHATSAPP_FROM` — leave empty for sandbox (`whatsapp:+14155238886`) or set to your approved WhatsApp Business number.

## Iteration 23 (2026-07) — Help Center + Multi-language platform
1. **Help & Documentation** — new route `/help` (nav: "Help & Docs"). Sectioned, searchable articles across Getting Started · Workforce · Payroll · Reports · SOPs · Compliance · Telegram · WhatsApp · Insights · Org Memory · Subcontractors. Each article has a Translate button. Top-of-page "Ask a question" box → `POST /api/help/ask` (grounded on Karya capabilities, replies in the user's chosen language).
2. **Multi-language i18n** (English, Hindi, Malayalam, Tamil, Telugu) —
   - Pre-translated UI shell dictionaries at `/app/frontend/src/lib/locales/{en,hi,ml,ta,te}.json`.
   - Provider + `useI18n()` at `/app/frontend/src/lib/i18n.js`, wired into `App.js` (`I18nBinder` reads `user.language` from AuthContext).
   - AppLayout nav, mobile bottom bar, More sheet, Ask AI, Sign out — all translated.
   - Profile page: new 5-tile language selector, instant switch + persists to `PUT /api/auth/profile`.
3. **On-demand AI translation** — `POST /api/translate` (Emergent LLM Key), with SHA-256 cached translations in `db.translations`. Reusable `TranslateButton` component appears below Help articles and can be dropped onto any dynamic content (report bodies, SOPs, feed).

## Iteration 24 (2026-07) — Telegram voice-out via OpenAI TTS
When a user sends a voice note to the Telegram bot, the bot's replies are now also spoken back as opus voice messages (OpenAI TTS `tts-1`, voice `nova`). Implementation uses a `ContextVar _TG_SPEAK` that propagates through async chains — `_handle_tg_voice` flips it on with token/reset, and every downstream `tg_send()` mirrors as speech via `tg_speak() → tg_send_voice()`. HTML/markdown stripped via `_for_tts()`. Failure-resilient: TTS errors swallowed with log warning. 12/12 tests pass.

## Iteration 25 (2026-07) — Expenses page + Language PATCH + Telegram report picker + Translate everywhere
1. **Expenses page** (`/expenses`, nav item between Reports and Insights). Backend: `GET /api/expenses` (search + category + total + by-category rollup), `POST /api/expenses` (manual), `DELETE /api/expenses/{id}`. Receipts forwarded to Telegram (existing flow) auto-populate here.
2. **PATCH /api/auth/profile/language** — lightweight endpoint that validates against `{en,hi,ml,ta,te}` and updates only `user.language`. Profile page's `pickLanguage()` now uses this (previously sent the full `ProfileIn` payload, which 422'd for partial profiles).
3. **Telegram `/report` project picker** — refactored `_handle_tg_report_command`: 0 or 1 projects → runs as before. 2+ projects → sends inline keyboard listing up to 8 recent projects + "— No project —" fallback. New `report_pick|<pid>` callback_query dispatches to shared `_generate_and_send_report()`.
4. **`TranslateButton` wired everywhere it matters** — DailyReports detail modal, SOP details, and every Feed article now have the button (Help + AI answers had it from iter 23).

22/22 backend tests pass. Regressions across iter 20–24 all green.

## Backlog / Next
- P1: Expenses page in web UI (receipts currently visible via Org Memory; db.expenses has structured data)
- P1: Let user pick project when generating /report from Telegram (currently most-recent project)
- P2: Telegram notifications push (compliance deadlines, payroll dues)
- P2: Split server.py into modules (~2545 lines) — Telegram surface (~700 lines) is a good extraction candidate.
- P2: WhatsApp (Twilio) still inactive — needs real Twilio creds
- P2: Replace preview-host substring match with dedicated `IS_PREVIEW` env flag (brittle if domain changes)
