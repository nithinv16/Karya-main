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
- backend/.env recreated: MONGO_URL local, DB_NAME=karya_db_v2 (NEW db), EMERGENT_LLM_KEY=sk-emergent-192096dD6E97559Fa0, TELEGRAM_BOT_TOKEN + TELEGRAM_WEBHOOK_SECRET=karya-tg-hook-7f3a9c2e, BACKEND_PUBLIC_URL/CORS = https://telegram-helper-bot.preview.emergentagent.com
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

## Iteration 26 (2026-07) — Cost Trends & Budget vs Actual
1. **`GET /api/cost-trends`** — aggregates cost across three streams (expenses, labour wages/bonuses, subcontractor payments/advances/extra_work) into time buckets. Query params: `period` (week/month/quarter/year, default month), `project_id` (optional filter). Returns:
   - `buckets`: `[{key, label, expenses, labour, subs, total}]` sorted by time.
   - `projects`: `[{id, name, budget, actual, remaining, percent, expenses, labour, subs, status}]` (status: no_budget | ok <80% | warn 80–100% | over >100%).
   - `overall`: `{budget, actual, unassigned, percent}` and `has_data` boolean.
   - Unassigned expenses (no project_id) are called out separately.
2. **Expenses now project-attributable** — `ExpenseIn` gained `project_id: Optional[str]`; `POST /api/expenses` persists it; Telegram-forwarded receipts default to `None`. Existing expenses continue to work.
3. **CostTrendsPanel (`/app/frontend/src/components/CostTrendsPanel.js`)** — reusable panel with:
   - Period toggle (Weekly/Monthly/Quarterly/Yearly) + range toggle (All time / Last 3/6/12) + project filter.
   - Stacked recharts ComposedChart (Expenses/Labour/Subs) with an optional dashed green `ReferenceLine` for the per-period budget (only shown when a single project is selected).
   - Horizontal recharts BarChart of Budget vs Actual per project (colours: green ok, amber warn, red over).
   - Per-project rollup rows with progress bars, remaining/overrun call-outs, and an "Unassigned" card when relevant.
   - `dense` prop hides the outer title (used inside the Workforce dialog).
4. **Mounted on `/expenses`** (top of page) with `<CostTrendsPanel />` (All-projects view).
5. **Per-project modal on Workforce** — every project card has a "View cost trends" button that opens a dialog with `<CostTrendsPanel projectId={p.id} dense />` (title = project name).
6. **Expense form** — "Attach to project (optional)" select added; row list shows project name for attributed expenses.

Testing (iteration_26.json): 14/14 new backend tests pass, all frontend flows verified, iter25 regression 21/22 (only failure is the intentional Telegram-webhook 503 in preview env).



## Backlog / Next

## Iteration 27–28 (2026-07) — Proactive Telegram pings, TG localization, server-side Expense search
1. **Proactive Telegram pings** with per-user settings (`GET/PUT /api/telegram/notifications`):
   - Types: `morning_briefing` (default 08:00 local), `compliance_alerts` (D-3/D-1/D-0 fired around 09:00), `payroll_reminder` (Mon+Fri 09:00, weekday-configurable).
   - Storage: `user.notifications = { timezone, morning_briefing, compliance_alerts, payroll_reminder }`. Defaults merged on read, timezone defaults from country (IN→Asia/Kolkata, AE→Asia/Dubai).
   - Dedupe: unique index on `db.ping_log(user_id, type, day)`; `_send_ping` also checks `_ping_already_sent` before hitting Telegram (idempotent).
   - Scheduler: in-process `_ping_scheduler_loop()` launched via `asyncio.create_task` on startup, wakes every 5 minutes, iterates users with `telegram_chat_id`, uses ZoneInfo for local time + a 6-minute window match.
   - Messages built by `_build_morning_briefing`, `_build_compliance_pings`, `_build_payroll_reminder` (all use HTML-formatted Telegram text, currency-aware via `money_str`).
2. **Telegram replies localized to user's language** — `tg_send` now translates outgoing text when `_TG_USER_LANG` context is non-`en` AND `len(text) >= 40`. Short confirmations ("OK", "✅ Recorded", command echoes) stay English. Both webhook handlers (`callback_query` and `message`) set `_TG_USER_LANG` right after resolving the linked user, so translation flows through all downstream sends including pings.
3. **Server-side full-text search on Expenses** — `GET /api/expenses?q=` now uses MongoDB `$regex` (case-insensitive) on `vendor + summary` with `re.escape` so `.`, `*`, etc. are literal. Adds `limit` (default 500, clamped [1, 2000]) and `offset` params + `count` field in response. `limit=0` correctly clamps to 1 (was returning 500 by mistake — fixed in iter28).
4. **New frontend component** `TelegramNotifications` (`/app/frontend/src/components/TelegramNotifications.js`) mounted below TelegramConnect on Profile — timezone select, three toggle rows with inline time pickers and weekday buttons. Every change fires PUT and shows a toast.

Testing: `iteration_28.json` — 23/23 tests pass (17 iter27 suite + 6 focused refix). Both prior iter27 bugs (limit=0 clamp; _send_ping idempotency) fully resolved.


- P1: Downloadable PDF Help Center for offline distribution to site supervisors.
- P1: Expose Karya's grounded Help AI inside `/help` on the Telegram bot (answers in user's language, /start overview).
- P2: Proactive Telegram pings (compliance deadlines, payroll dues, morning briefings).
- P2: Split server.py (~3110 lines) into modules — Telegram (~700), Expenses (~60), Cost Trends (~150), Translate/Help (~120), Twilio (~150) are all extraction candidates.
- P2: Route more Telegram bot replies through the user's saved language (currently replies are English).
- P2: Server-side full-text search on Expenses once >500 receipts (currently client-side substring).
- P2: Ask user which project when forwarding a receipt via Telegram (currently attached to no project by default).
- P2: `limit` param + max-bucket cap on `/api/cost-trends` for accounts with many years of data.
- P2: Replace preview-host substring match with dedicated `IS_PREVIEW` env flag (brittle if domain changes).
- P2: WhatsApp (Twilio) still inactive — needs real Twilio creds.

## Iteration 30 (2026-07) — Attendance register, Contact form, company identity
1. **Attendance register** — new `/attendance` page in the web app under Workforce with per-worker present / half-day / absent toggles, bulk "Mark all present", and a Quick Headcount form for supervisors who don't track by name. Backed by new endpoints:
   - `GET /api/attendance` (list with date range/project/worker filters)
   - `GET /api/attendance/roster?date=&project_id=` (roster grid with unmarked default)
   - `POST /api/attendance/mark` (upsert one row per worker/date)
   - `POST /api/attendance/bulk` (batch marks)
   - `POST /api/attendance/headcount` (aggregate N-workers-at-project row)
   - `DELETE /api/attendance/{id}`
   Nav entry added to sidebar; localized keys in en/hi/ta/te/ml.
2. **Telegram `/attendance` command** with three parse paths: `/attendance 12 Site A` (headcount by fuzzy project name), `/attendance Ramesh present` (per-worker mark; supports present/absent/half day), `/attendance` alone → today's summary. When user has 2+ projects and no name given, the bot replies with an inline-keyboard project picker; callback `att_head|<count>|<project_id>` records the headcount.
3. **Company identity & Contact form** — new public pages/endpoints:
   - `GET /api/company-info` → `{legal_name:"SIXN8 Technologies Private Ltd", support_email:"admin@dukaaon.in", product_name, website}`.
   - `POST /api/contact` (public, IP-rate-limited 5/5min): validates name/email/message, saves to `db.contact_submissions`, and quietly relays the submission via Telegram to the ops-owner's chat_id.
   - `/contact` page renders a clean form with SIXN8 + support-email side panel; login-page footer now shows SIXN8 attribution + Blog/Contact/admin@dukaaon.in links.
4. **NithinV16 secret delivery pipeline** — the Telegram webhook silently watches `msg.from.username` on every inbound update; when it matches `CONTACT_TG_USERNAME` (case-insensitive) the chat_id is cached in `db.system_config` under key `contact_chat_id`. Contact submissions then send-to that chat_id. The handle is stored **only** in `backend/.env` (never surfaced in any API response, HTML source, or JS bundle — testing agent verified zero leak).
5. **Structured data update** — Organization schema on the landing page now advertises SIXN8 Technologies + admin@dukaaon.in with a `ContactPoint` entry; sitemap.xml includes `/contact`.

Testing: `iteration_30.json` — **20/20 backend + 3/3 frontend flows pass**, zero critical/minor issues, no NithinV16 leak.





## Iteration 32 (2026-07) — server.py extraction + N+1 fixes
1. **Routes extracted** into `backend/routes/*` — each module exposes a `Deps` dataclass + `build_router(deps)` factory:
   - `routes/contact.py` — `/company-info` + `/contact`.
   - `routes/attendance.py` — 5 endpoints + reusable `mark_attendance_core` / `headcount_attendance_core` helpers that the Telegram `/attendance` handler still calls via shims in server.py.
   - `routes/cost_trends.py` — `/cost-trends`.
   - `routes/expenses.py` — list/create/upload-receipt/delete.
   - `routes/telegram_prefs.py` — GET/PUT `/telegram/notifications`.
   Result: `backend/server.py` dropped from **4063 → 3525 lines** (~13% reduction). "<2000 lines" not fully achieved because the Telegram webhook + ping scheduler (~950 lines combined) intentionally left in place — extracting them safely needs a follow-up session (ContextVars, callbacks, startup lifecycle are tangled).
2. **N+1 query fixes** in `list_subs` and `_assistant_answer`: replaced per-sub `db.sub_transactions.find` with a single `$in` bulk query.
3. **Test alignment** — `test_iteration29.py::test_cors_via_asgi_app` now branches on `CORS_ORIGINS==*` wildcard mode.

Testing: iteration_32.json — 23/23 refactor tests pass, 100% success on new suite.

