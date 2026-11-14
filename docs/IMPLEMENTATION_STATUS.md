# Implementation status — local 2026-11-14

- CRM, Inbox, Calendar, authentication, multi-business isolation and legacy automations remain available.
- Built-in AI: encrypted provider configuration, business facts/FAQ/history, owner reply guidance and SMS/WhatsApp auto-reply. Base prompt restricts invented facts and unconfirmed bookings. These are model instructions, not a deterministic output policy; Built-in AI has no booking tools.
- SMS: Twilio outbound with live environment gate and consent checks; signed inbound/status hooks and STOP. Demo events retain mock delivery.
- WhatsApp: encrypted credentials, verification GET, signed inbound POST, separate conversations, text replies, STOP/START, deduplication and 24-hour service window based on inbound timestamp. No templates, media handling or delivery/read receipt synchronization. Graph version must match the configured Meta app; not verified against a live account.
- Phone calls: Dial staff first; busy/no-answer/failed/canceled uses selected AI/SMS/end fallback. SMS respects consent/live gate and deduplicates CallSid. Mock does not claim actual delivery. Voice remains turn-based Gather/LLM/TTS, with an eight-turn cap.
- UI: seven AI/channel tabs; owner-only configuration; keyboard navigation, mobile layouts and saved-tab retention.
- Startup adds integration columns, contacts.consent_whatsapp and whatsapp_sessions. Back up database and encryption key before updating an existing installation. Local QA uses temporary databases and keys.

## Validation

- Backend unittest suite: 33 tests, external provider requests mocked.
- Python compile and JavaScript syntax checks; Node VM template smoke.
- Playwright with local Edge: 7 pages at 390/740/1024/1440 px, settings saves, channel tabs, keyboard/modal behavior, mobile inbox, workflow, tenant switching and staff controls.
- No live Meta/Twilio/LLM/TTS validation in this update. No production deployment or live credential changes performed.
- Payments, streaming voice, automatic Built-in AI booking, production queue/retries and production hardening remain outside this implementation.
