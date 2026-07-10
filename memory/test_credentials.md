# Test Credentials — Karya

Auth is Emergent-managed Google OAuth (no app passwords).

## Test API session (created for QA)
- user_id: `test-user-karya1`
- email: `qa.karya@example.com`
- session_token (Bearer or `session_token` cookie): `test_session_karya1`
- DB: `test_database`, collections `users` / `user_sessions`

Use: `curl -H "Authorization: Bearer test_session_karya1" https://5a4dc3f8-621c-43ea-88bc-ebe27ab496fc.preview.emergentagent.com/api/auth/me`

For browser testing set cookie `session_token=test_session_karya1` (domain: 5a4dc3f8-621c-43ea-88bc-ebe27ab496fc.preview.emergentagent.com, path=/, Secure, HttpOnly, SameSite=None).

See /app/auth_testing.md for creating fresh sessions.
