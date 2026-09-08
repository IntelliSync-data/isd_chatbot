# Contract: Shared inbound webhook (Facebook channel)

**Base path**: `/isd_chatbot/webhook`  
**Auth**: `public`, CSRF off (existing). Facebook POSTs are authenticated by `X-Hub-Signature-256`, not Odoo session.  
**Channel split**: query `merchant=facebook` or `merchant=zalo` only. Do not use `channel=`.

Website widget routes (`/chatbot/api/chat`, `/chatbot/api/submit_info`) are unchanged.

Related: [data-model.md](../data-model.md)

---

## 1. Subscription check

Meta calls this when staff paste the receive address into the App / Page webhook settings.

```
GET /isd_chatbot/webhook?merchant=facebook&hub.mode=subscribe&hub.verify_token=<phrase>&hub.challenge=<opaque>
```

| Condition | Status | Body |
|---|---|---|
| Facebook enabled AND `hub.verify_token` equals configured verify phrase AND `hub.mode=subscribe` | 200 | raw `hub.challenge`, `Content-Type: text/plain` |
| Channel off, phrase mismatch, missing phrase, or `hub.mode` ≠ `subscribe` | 403 | empty |
| `merchant` missing/unknown (even if hub.* present) | 200 | empty (log only; do not echo a challenge) |

Side effect: one `chatbot.webhook.log` row. No conversation.

---

## 2. Inbound Page events

```
POST /isd_chatbot/webhook?merchant=facebook
Content-Type: application/json
X-Hub-Signature-256: sha256=<hex(hmac_sha256(app_secret, raw_body))>
```

### 2.1 Authenticity

Compute HMAC-SHA256 of the **raw** body with `isd_chatbot.facebook_app_secret`. Compare to the header digest using a constant-time compare.

| Condition | HTTP | Chat? | Log status |
|---|---|---|---|
| Signature missing or mismatch | 200 | no | `error` |
| Facebook disabled or Page token unset | 200 | no | `ignored` |
| Signature ok | 200 | if text events | `processed` or `ignored` per event |

### 2.2 Body (accepted subset)

```json
{
  "object": "page",
  "entry": [
    {
      "id": "PAGE_ID",
      "messaging": [
        {
          "sender": { "id": "PSID" },
          "recipient": { "id": "PAGE_ID" },
          "timestamp": 1710000000000,
          "message": {
            "mid": "m_unique",
            "text": "visitor text",
            "is_echo": false
          }
        }
      ]
    }
  ]
}
```

Process each `entry.messaging` item independently:

| Event | Action |
|---|---|
| `message.text` present, not echo, length 1–5000, optional `page_id` matches recipient | `FacebookChatbotServiceAdapter.chat(text, session_id="facebook:<PSID>", source_code=facebook, facebook_sender_id=PSID, external_message_id=mid)` |
| `message.is_echo` true | ignore |
| no `message.text` (image, sticker, postback, delivery, read) | ignore |
| empty / whitespace / >5000 chars | reject write; no inquiry |
| `mid` already on `chatbot.message.external_message_id` | ignore (no second conversation/inquiry) |
| `object` ≠ `page` | ignore |

Staff fields in the JSON (`assigned_user_id`, `state`, `crm_lead_id`, …) are ignored.

### 2.3 Success side effects (text event)

- User + bot `chatbot.message` on a Facebook-sourced conversation.
- If name + email or phone extracted: one `customer.inquiry`, conversation `ended`, end message sent to Graph.
- Outbound: see §3.

---

## 3. Outbound reply (adapter → Graph)

Not an Odoo route. The adapter calls Facebook:

```
POST https://graph.facebook.com/v21.0/me/messages
Authorization: Bearer <page_access_token>
Content-Type: application/json

{
  "recipient": { "id": "<PSID>" },
  "messaging_type": "RESPONSE",
  "message": { "text": "<bot reply>" }
}
```

| Graph outcome | Product behavior |
|---|---|
| 200 | done |
| OAuth error **190** | refresh via §4, resend once; second failure → log, no further retry |
| any other error | log on webhook row; conversation/inquiry unchanged; no retry |

---

## 4. Page access refresh

```
GET https://graph.facebook.com/v21.0/oauth/access_token
  ?grant_type=fb_exchange_token
  &client_id=<app_id>
  &client_secret=<app_secret>
  &fb_exchange_token=<current_page_token>
```

On success, persist `isd_chatbot.facebook_page_access_token`. On failure, Manager pastes a new token in Settings.

---

## 5. Coexistence with Zalo

```
POST /isd_chatbot/webhook?merchant=zalo
```

Must still reach `ZaloChatbotServiceAdapter` (not Facebook). A `merchant=facebook` body must never be sent to Zalo OA.

CORS on this route may stay `*` (Meta is server-to-server). Widget CORS (`isd_chatbot.cors_origins`) is unrelated.

---

## 6. What this contract does not expose

- No public read/list/update of conversations or inquiries.
- No Facebook fields on `/api/inquiry` beyond the existing `source_code=facebook` documentation.
- Widget `/chatbot/widget.js` must not contain Page tokens, app secret, or verify phrase.
