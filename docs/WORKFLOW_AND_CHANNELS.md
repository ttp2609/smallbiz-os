# Workflow & Channels — kỹ thuật Demo V0.2

## Workflow graph schema

```json
{
  "name": "Welcome lead",
  "enabled": true,
  "nodes": [
    {"id":"start","type":"trigger_sms","x":60,"y":80,"config":{}},
    {"id":"gate","type":"condition_consent","x":310,"y":80,"config":{}},
    {"id":"send","type":"action_sms","x":560,"y":80,"config":{"text":"Hi {{first_name}}!"}}
  ],
  "edges": [
    {"from":"start","to":"gate","branch":"next"},
    {"from":"gate","to":"send","branch":"yes"}
  ]
}
```

Supported types: `trigger_sms`, `trigger_missed`, `trigger_booking`, `condition_consent`, `condition_keyword`, `action_sms`, `action_ai`, `action_tag`, `action_handoff`, `action_log`.

- **One trigger per workflow.** DAG only, no cycles, max 25 nodes/40 edges; one outgoing edge per branch. Condition uses `yes`/`no`, other nodes use `next`.
- Template text `{{first_name}}` and `{{business_name}}` only.
- API: `GET/POST /api/workflows`, `PUT/DELETE /api/workflows/{id}`, `POST /api/workflows/{id}/test` with `{contact_id,text}`. All endpoints validate logged-in business; updates require Owner.
- `test` is **dry_run**, no SMS, AI network call or CRM mutation. Engine writes event logs when an enabled flow runs during actual events.
- Demo SMS/missed-call events also trigger the workflow runner. If Twilio Live is active, those synthetic events only dry-run workflows. Actual signed Twilio inbound SMS can trigger real actions.
- Default sample workflow is disabled. V0.1 legacy preset automation is independent; enabling both may cause multiple text-backs for the same event. Review and disable redundant rules.

## SMS dispatch

- `mock` is default. Twilio Live requires `SMALLBIZ_ENABLE_LIVE_SMS=1` set **before the server starts**, plus valid SID, token, sender number and SMS mode switch by workspace Owner.
- Outbound SMS blocked without `contacts.consent_sms`, or with invalid E.164. Raw credentials never sent to browser. Mark STOP and other opt-outs to disable consent.
- Signed inbound `POST /api/hooks/twilio/sms` checks Twilio `X-Twilio-Signature`, matches To with the configured Twilio number, checks duplicate `MessageSid`, creates contact (without assumed consent) and message.
- Outbound `StatusCallback` route: `POST /api/hooks/twilio/status`, signed, updates queue/sent/delivered/failed states by Twilio MessageSid.
- Telephony and application SMS are **not free**. Registration/consent are not implemented automatically.

## Voice

- UI Voice Lab: `POST /api/voice/speak` synthesizes gTTS/Edge-TTS MP3 for the logged-in business. Audio files cached locally and cleaned after aging; no speech recording storage in browser lab.
- Browser STT is Web Speech API when available. Does not depend on selected TTS.
- Twilio turn-based Voice AI: `POST /api/hooks/twilio/voice` → `Gather(speech, language)` → `POST /api/hooks/twilio/voice/turn` with `SpeechResult` → AI Chat Completions → TTS MP3 short-lived URL → Twilio `Play`. Greeting fallback to Twilio `Say` if online TTS fails. Conversation ends after 8 turns.
- Public audio URLs are unguessable 12-minute tokens; setup requires `SMALLBIZ_PUBLIC_BASE_URL=https://...` and publicly routable HTTPS. Twilio speech recognition and phone calls can cost money.
- Real voice conversations, latency, supported locale combinations and real-device playback have **not been verified**. This is not streaming speech-to-speech.

## Production blockers

Replace demo credentials/session handling, add HTTPS hardening/CSRF and brute-force protections, explicit consent audit records, A2P onboarding, delivery retries and queue orchestration, DB migrations, secret management separated from app files, logs/monitoring, provider error handling, rate limiting, PII retention controls, workflow execution idempotency under failures, WebSocket streaming if low latency is needed, and integration E2E tests against real Twilio/LLM accounts.
