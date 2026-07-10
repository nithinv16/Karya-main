# Test Credentials — Karya

Auth is Emergent-managed Google OAuth (no app passwords).

## Test API session (created for QA)
- user_id: `test-user-karya1`
- email: `qa.karya@example.com`
- session_token (Bearer): `test_session_karya1`
- DB: `karya_database`, collections `users` / `user_sessions`

### Browser testing
Set `localStorage.karya_session_token = "test_session_karya1"` on the frontend origin, then visit `/dashboard`. (Cookie fallback also still works for same-origin.)

### API testing
```
curl -H "Authorization: Bearer test_session_karya1" \
  https://karya-setup.preview.emergentagent.com/api/auth/me
```

See /app/auth_testing.md for creating fresh sessions.
