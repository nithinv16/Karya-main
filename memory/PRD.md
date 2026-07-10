# Karya — AI OS for Construction

## Original Problem Statement
Fetch the Karya-main repo into the environment and update .env / credentials (Google Auth, MongoDB URL, OpenAI key, Stripe key) to use current Emergent keys.

## Setup Performed (2026-01)
- Codebase (Karya-main) was already present in `/app` (connected via GitHub in Emergent UI).
- Created `/app/backend/.env`:
  - `MONGO_URL=mongodb://localhost:27017` (Emergent pre-configured local Mongo)
  - `DB_NAME=karya_database`
  - `EMERGENT_LLM_KEY=sk-emergent-eAcDc5409F4B1Fb9eE` (Universal Key — powers OpenAI/Claude/Gemini via emergentintegrations)
  - `CORS_ORIGINS` + `BACKEND_PUBLIC_URL` = current preview URL
  - `STRIPE_API_KEY=sk_test_emergent` (Emergent test key)
  - Twilio vars left blank (optional; WhatsApp features inactive until user provides them)
- Created `/app/frontend/.env`:
  - `REACT_APP_BACKEND_URL=https://voice-to-docs-6.preview.emergentagent.com`
- Restarted supervisor: backend + frontend RUNNING, `/api/` returns 200, landing page renders.

## Auth
Uses Emergent-managed Google OAuth (session-based via `demobackend.emergentagent.com/auth/v1/env/oauth/session-data`). No app-level OAuth client keys required.

## Next Action Items
- User to sign in via "Continue with Google" to seed a real user and test end-to-end flows (workers, reports, SOPs, voice ops).
- If WhatsApp reporting is needed, add real `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_WHATSAPP_FROM` to `/app/backend/.env`.
- Optional: run testing subagent for regression once user confirms which features must be validated.

## Backlog / Future
- Wire real Stripe usage if billing is planned (currently `stripe` package installed but not used in code).
