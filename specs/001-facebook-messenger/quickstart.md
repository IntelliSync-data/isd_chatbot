# Quickstart: Facebook Messenger Channel

**Feature**: `001-facebook-messenger`  
**Date**: 2026-08-23

Validate the channel against a running Odoo 18 with `isd_chatbot` on the addons path. This is a runbook, not the implementation.

Contracts: [facebook-webhook.md](./contracts/facebook-webhook.md)  
Data: [data-model.md](./data-model.md)

## Prerequisites

- Odoo 18 database with **ISD Chatbot** installed/upgraded (`-u isd_chatbot`).
- Chatbot Manager user.
- Meta App + Page you control (or a request inspector that can send the GET/POST shapes in the contract).
- Page access token, App ID, App secret, and a verify phrase you choose.
- Public HTTPS base URL (or a tunnel) if you want Meta itself to call you. Local tests can POST the contract payloads directly.

## 1. Upgrade and seed

```bash
odoo-bin -c /path/to/odoo.conf -d <db> -u isd_chatbot --stop-after-init --no-http
```

**Expect**: Apps list shows the module upgraded. Inquiry Sources includes **Facebook** without a manual create (FR-010).

## 2. Settings

Chatbot → Settings:

1. Enable Facebook.
2. Enter Page ID, Page access token, App ID, App secret, verify phrase.
3. Copy receive address: `{web.base.url}/isd_chatbot/webhook?merchant=facebook`.
4. Save. Confirm the public embed script (`/chatbot/widget.js`) does **not** contain those secrets.
5. Leave the widget Messenger link as-is if already set — it must still open `m.me`.

**Expect**: Values persist after reload. Facebook stays independent of Zalo fields.

## 3. Subscription check

```http
GET /isd_chatbot/webhook?merchant=facebook&hub.mode=subscribe&hub.verify_token=<your-phrase>&hub.challenge=abc123
```

**Expect**: `200`, body `abc123`.

Repeat with a wrong phrase and with Facebook disabled.

**Expect**: `403`, no new conversation.

## 4. Q&A text (Graph may be mocked in tests)

POST the sample body in the contract with a valid `X-Hub-Signature-256` (HMAC-SHA256 of the raw body with the App secret) and a `mid` you have not used.

Use a visitor text that matches an active Q&A row.

**Expect** (SC-001 / US1):

- Conversation `session_id` = `facebook:<PSID>`, source Facebook, status active.
- User message + bot answer stored.
- Graph `me/messages` called once with that answer (or the test double records one send).
- Reply reaches Messenger in a live test in under 10 seconds.

## 5. Inquiry from contact text

POST another signed event whose text contains a name and an email or phone.

**Expect** (SC-002 / US2):

- Exactly one inquiry, source Facebook, original text intact, conversation ended.
- Visitor received the configured end message.
- Chatbot User who is not assigned does not see the inquiry; Manager does.

## 6. Replay, junk, and isolation

| Action | Expect |
|---|---|
| POST the same `mid` again | Still one inquiry / one user message |
| Image / sticker / echo (`is_echo: true`) | No inquiry; receive address still 200 |
| POST without a valid signature | No conversation |
| POST with no `merchant` | Log only, no chat |
| Disable Facebook, POST a valid signed text | Zero new conversations; website widget chat still works |
| Same PSID after the inquiry ended | New conversation; previous inquiry unchanged |
| Zalo URL `?merchant=zalo` | Still Zalo-sourced, not Facebook |

## 7. Send / access failure

Force Graph to fail (invalid token in a staging DB).

**Expect**:

- Non-190 error: no retry; inquiry/conversation consistent; Manager sees the failure on the webhook log.
- Error 190: one token exchange + one resend; second failure stops.

## 8. Automated stand-in

After `tests/` exist (constitution):

```bash
odoo-bin -c /path/to/odoo.conf -d <test-db> --test-enable --stop-after-init -i isd_chatbot --no-http
# or, once installed:
odoo-bin -c /path/to/odoo.conf -d <test-db> --test-enable --stop-after-init -u isd_chatbot --test-tags=isd_chatbot --no-http
```

**Expect**: Facebook webhook / inquiry cases in `tests/` pass. Until they land, the table in spec **Manual Verification** is the gate.
