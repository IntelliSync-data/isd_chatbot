# Research: Facebook Messenger Channel

**Feature**: `001-facebook-messenger`  
**Date**: 2026-08-23

## 1. Channel adapter vs second hub

**Decision**: Add `FacebookChatbotServiceAdapter(ChatbotService)` and register it on `ChatbotServiceFactory.get_service(provider='facebook')`. Reuse `ChatbotService.chat()` for Q&A, contact extraction, inquiry create, and conversation end.

**Rationale**: Matches Zalo, constitution IV (Integration Isolation), and FR-001 / FR-002. Inquiry-first rules stay in one place.

**Alternatives considered**:
- Inline Facebook send/receive in `customer.inquiry` — forbidden by constitution IV.
- Separate Facebook conversation model — duplicates the hub; rejected.
- Call Graph from the controller only — would fork Q&A/inquiry rules.

## 2. Shared receive address and `merchant=` split

**Decision**: Keep `GET|POST /isd_chatbot/webhook`. Staff register:

- Facebook: `{web.base.url}/isd_chatbot/webhook?merchant=facebook`
- Zalo: `{web.base.url}/isd_chatbot/webhook?merchant=zalo`

Resolve the platform from query `merchant` only (`zalo` or `facebook`). Unknown or missing `merchant` → log only, do not chat. Do not read or require `channel=`.

**Rationale**: Clarification (updated): keep the existing Zalo query name. A second name (`channel=`) would force staff to re-register Zalo and split the contract.

**Alternatives considered**:
- Dedicated `/isd_chatbot/webhook/facebook` — cleaner handshake, rejected by clarification.
- New query `channel=` as the canonical split, `merchant=` as alias — discarded; user kept `merchant` only.

## 3. Facebook inbound shape vs current parser

**Decision**: When `merchant=facebook`, parse Meta’s Page payload, not the current Zalo-shaped `payload.message.text` / `payload.sender.id`.

Canonical inbound (text):

```json
{
  "object": "page",
  "entry": [
    {
      "id": "<PAGE_ID>",
      "messaging": [
        {
          "sender": { "id": "<PSID>" },
          "recipient": { "id": "<PAGE_ID>" },
          "message": {
            "mid": "m_...",
            "text": "hello",
            "is_echo": false
          }
        }
      ]
    }
  ]
}
```

Walk `entry[*].messaging[*]`. Process only items with `message.text` and without `message.is_echo`. Ignore deliveries, reads, postbacks, stickers, attachments, and echoes (FR-013, FR-023 still replies to visitor texts only).

**Rationale**: Facebook nests events; the current webhook parser would see empty text/sender and never chat.

**Alternatives considered**: Normalize all channels to one generic envelope in v1 — extra abstraction, no second channel beyond Facebook this feature.

## 4. Subscription check (GET) and authenticity (POST)

**Decision**:

- **GET** `merchant=facebook` with `hub.mode=subscribe`: if Facebook is enabled and `hub.verify_token` equals the configured verify phrase, return **200** with body = `hub.challenge` (`text/plain`). Otherwise **403** and no conversation.
- **POST** `merchant=facebook`: require header `X-Hub-Signature-256: sha256=<hex>`. Compute `HMAC-SHA256(app_secret, raw_body)` and compare with `hmac.compare_digest`. Fail → mark log `error`, do not chat, return **200** (avoid Meta retry storms) unless the request is the GET handshake.

Always persist a `chatbot.webhook.log` row first (existing behavior) with `merchant` copied from the query.

**Rationale**: Meta will not finish Page subscription without the GET echo. Unsigned POSTs must not create inquiries (FR-009, Principle III). Returning 200 on rejected POST matches today’s “webhooks expect 200” practice and SC-004.

**Alternatives considered**:
- Verify-token only, no signature — fails FR-009 and is trivial to spoof.
- 403 on bad POST signature — Meta retries, noisy logs.

## 5. Session identity and ended-conversation restart

**Decision**: `session_id = "facebook:" + PSID`. `_get_or_create_conversation` already opens a new row when no **active** session exists, so an ended Facebook thread naturally becomes a new conversation (FR-022). Adapter forces `source_code='facebook'`.

Prefix avoids colliding with a Zalo OA user id stored as a raw `session_id`.

**Rationale**: Spec: same person after end → new conversation; two people → two sessions.

**Alternatives considered**: Raw PSID as session_id — collision risk with Zalo. Reopen ended conversation — rejected in clarify.

## 6. Dedup of Meta redeliveries

**Decision**: Add optional `external_message_id` on `chatbot.message` (indexed). Before `chat()`, if a message with that `mid` exists, skip. Unique when set (`UNIQUE` where not null, or search-before-create).

**Rationale**: FR-014 / SC-005. Meta redelivers. Content+timestamp matching is weak.

**Alternatives considered**: Dedup only in webhook log — logs are purged by cron (30 days) and are not the conversation key.

## 7. Outbound send and token refresh

**Decision**: After `super().chat()`, POST text to Graph:

`POST https://graph.facebook.com/v21.0/me/messages`  
Bearer = Page access token  
Body: `{ "recipient": { "id": PSID }, "messaging_type": "RESPONSE", "message": { "text": <bot> } }`

Pin Graph **v21.0** in one constant on the adapter (not a staff setting in v1).

On Graph error **190** (invalid/expired OAuth token): exchange once

`GET https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=<app_id>&client_secret=<app_secret>&fb_exchange_token=<current>`

Save the new token via `ir.config_parameter` (same pattern as Zalo `_set_zalo_oa_api_tokens`), resend **once**. Any other error, or a second 190: do not retry; write failure onto the webhook log (`error_message` / `processing_notes`); leave conversation/inquiry unchanged (FR-015).

If exchange is impossible (missing app id/secret, or Facebook refuses to exchange a non-exchangeable Page token), treat as terminal failure — Manager pastes a new token.

**Rationale**: Clarifications: no general retry; one refresh+resend on dead access (Zalo parity). Facebook has no OA-style refresh_token; `fb_exchange_token` is the supported analogue.

**Alternatives considered**:
- General N retries — rejected in clarify.
- Manager-only “resend last reply” — out of scope.
- Unversioned `graph.facebook.com/me/messages` — version drift.

## 8. Enable switch and credentials

**Decision**: New `ir.config_parameter` keys, edited only in Chatbot Settings (and mirrored on `chatbot.config` like Zalo):

| Key | Role |
|---|---|
| `isd_chatbot.facebook_enabled` | On/off (default false) |
| `isd_chatbot.facebook_page_id` | Optional filter; ignore events whose recipient ≠ this Page |
| `isd_chatbot.facebook_page_access_token` | Secret |
| `isd_chatbot.facebook_app_id` | Token exchange |
| `isd_chatbot.facebook_app_secret` | Signature + exchange |
| `isd_chatbot.facebook_verify_token` | GET handshake |

Disabled or missing token/secret/verify phrase: no chat, GET verify fails. Widget `m.me` link unchanged (FR-012).

Show a read-only copy hint in Settings: base URL + `/isd_chatbot/webhook?merchant=facebook`.

**Rationale**: FR-006–FR-008, Principle II (secrets in config params). Default off so upgrade does not start answering a Page until a Manager opts in.

**Alternatives considered**: Enable automatically when a token is present — surprising production behavior.

## 9. Request threading

**Decision**: Process Facebook (and the shared dispatcher for Zalo) **on the HTTP request**, after the log row is created. Do **not** copy `ThreadPoolExecutor` + `request.env` onto Facebook.

**Rationale**: Odoo `Environment` / cursor are not thread-safe. Meta allows ~20s to 200; spaCy + one Graph POST fit. Constitution: adapter failure must leave consistent state — easier in-request.

**Alternatives considered**: Keep background threads for “fast 200” — data-loss and cursor bugs. Cron drain of webhook logs — extra moving part, not required.

## 10. Inquiry source seed

**Decision**: Add `inquiry.source` data row `code=facebook` (noupdate) and include it in `_get_default_sources`. Selection already has `('facebook', 'Facebook')`.

**Rationale**: FR-010 / SC-006. Code exists; row does not.

## 11. Tests (constitution)

**Decision**: Add `tests/` HttpCase + TransactionCase. No in-repo harness exists; this feature’s public POST and inquiry-create path **must** ship tests.

Cover: GET verify success/fail/disabled; POST bad signature; POST text → Facebook conversation + bot reply (Graph mocked); name+contact → one inquiry; mid replay → one inquiry; `merchant` missing → no chat; `merchant=zalo` still routes to Zalo adapter (mocked send); disabled Facebook → no conversation.

**Rationale**: Constitution Specification & Quality Workflow.

## 12. Observability

**Decision**: Reuse `chatbot.webhook.log` (Manager-only). Set `status` to `processed` / `error` / `ignored`, `event_type` from payload, `processing_notes` for skip reasons (echo, no text, bad signature, disabled, unknown merchant), `error_message` for Graph failures. Optional stored `merchant` char for filters.

No new staff inbox or Discuss notification in this feature (deferred from clarify).

**Rationale**: FR-015 “staff can see the failure”; menu already exists.
