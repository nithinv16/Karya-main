# Test Credentials — Karya

Auth is Emergent-managed Google OAuth (no app passwords).

## Test API session (QA)
- user_id: `test-user-karya1`
- email: `qa.karya@example.com`
- session_token (Bearer): `test_session_karya1`
- DB: `karya_db_v2` (NEW database), collections `users` / `user_sessions`

### Browser testing
Set `localStorage.karya_session_token = "test_session_karya1"` on the frontend origin, then visit `/dashboard`.

### API testing
```
curl -H "Authorization: Bearer test_session_karya1" \
  https://telegram-helper-bot.preview.emergentagent.com/api/auth/me
```

## Telegram
- Bot: @karya_ops_bot (token in /app/backend/.env TELEGRAM_BOT_TOKEN)
- Webhook secret header: `X-Telegram-Bot-Api-Secret-Token: karya-tg-hook-7f3a9c2e`
- Webhook URL: {BACKEND_PUBLIC_URL}/api/telegram/webhook (auto-registered on startup)
- QA linked chat_id: 999000111 (fake chat — sendMessage to it fails silently, handlers still run)
- Simulate updates by POSTing Telegram update JSON to the webhook with the secret header.
