# Data Model: Facebook Messenger Channel

**Feature**: `001-facebook-messenger`  
**Date**: 2026-08-23

No new models. Facebook is a channel adapter over existing conversation / inquiry / source / webhook-log / settings.

## Entities

### inquiry.source

Existing. Selection already includes `facebook`.

| Field | Change |
|---|---|
| `code` | No change to selection. Seed row `facebook` / name `Facebook` / sequence `4`. |
| `active` | Default true on the seed row. |

**Validation**: `code` unique (existing SQL constraint).

**Upgrade**: `noupdate="1"` data record `inquiry_source_facebook` plus `_get_default_sources` so older DBs that skip XML still get the row on a defensive call.

### chatbot.conversation

Existing.

| Field | Usage |
|---|---|
| `session_id` | `facebook:<PSID>` for this channel. |
| `source_id` | Forced to `inquiry.source` `facebook` by the adapter. |
| `status` | `active` → `ended` when inquiry is created (existing `ChatbotService.chat()`). Ended row is never reopened (FR-022). |
| `customer_inquiry_id` | Set when inquiry is created. |
| `user_ip` / `user_agent` | From the webhook request (existing kwargs). |

**Identity**: One **active** conversation per `session_id`. Next inbound from the same PSID after `ended` creates a new conversation.

### chatbot.message

Existing, plus one field.

| Field | Change |
|---|---|
| `external_message_id` | **New** `Char`, index, copy=False. Facebook `message.mid`. Empty for website/Zalo unless those adapters start setting it later. |
| `message_type` | Unchanged: `user` / `bot`. |
| `content` | Visitor text or bot reply. |
| `conversation_id` | Unchanged. |

**Validation**: Before create-from-webhook, search `external_message_id = mid`. If found, skip (FR-014). Prefer a SQL unique constraint on `external_message_id` where not null if the DB/Odoo version makes a filtered unique practical; otherwise application-level search is the gate.

**Do not** store Graph tokens on messages.

### customer.inquiry

Existing. No new fields.

| Field | Usage |
|---|---|
| `message` | Immutable original visitor text (Principle I). |
| `source_id` | Copied from conversation (`facebook`). Never overwritten later. |
| `conversation_id` | Link to the Facebook conversation. |
| `name` / `email` / `phone` | From shared `parse_user_info`. |
| `state` | Starts `new`. Chat does not promote (FR-017). |
| `assigned_user_id` | Not set by Facebook intake (FR-020). |

**Validation**: Existing constraint — name implied by create path; at least email or phone. Public create must ignore assignee / CRM / state from the payload.

### chatbot.config / res.config.settings / ir.config_parameter

Triplicated config stays. New Facebook keys live on settings + `ir.config_parameter`; `chatbot.config._sync_config_parameters()` mirrors them like Zalo.

| Settings field | Parameter | Type |
|---|---|---|
| `chatbot_facebook_enabled` | `isd_chatbot.facebook_enabled` | bool, default false |
| `chatbot_facebook_page_id` | `isd_chatbot.facebook_page_id` | char |
| `chatbot_facebook_page_access_token` | `isd_chatbot.facebook_page_access_token` | secret char |
| `chatbot_facebook_app_id` | `isd_chatbot.facebook_app_id` | char |
| `chatbot_facebook_app_secret` | `isd_chatbot.facebook_app_secret` | secret char |
| `chatbot_facebook_verify_token` | `isd_chatbot.facebook_verify_token` | secret char |

Read helpers on `chatbot.config` (`_get_facebook_*`, `_set_facebook_page_access_token`, `_is_facebook_enabled`) — same style as `_get_zalo_oa_api_token`.

**Validation**: Secrets never in widget JS or XML defaults. Enable false unless a Manager turns it on.

### chatbot.webhook.log

Existing, plus optional channel.

| Field | Change |
|---|---|
| `merchant` | **New** `Char` (or Selection `zalo` / `facebook` / empty). From query `merchant` only. |
| `status` | `received` → `processed` / `error` / `ignored`. |
| `event_type` / `webhook_type` | From payload when present (`object`, messaging type). |
| `error_message` / `processing_notes` | Signature failures, Graph errors, skip reasons. |
| `json_data` | Raw body (existing). Do not write tokens into notes. |

Manager-only read remains. Public ACL stays create-only.

## Relationships

```text
Facebook Page event
    → chatbot.webhook.log (1 per HTTP call)
    → 0..n chatbot.conversation (session facebook:<PSID>, source facebook)
        → chatbot.message* (user mid + bot reply)
        → customer.inquiry? (when name + email|phone)
            → source_id = facebook
```

## State transitions

```text
conversation.status:
  (none) --inbound visitor text, channel on--> active
  active --name + email|phone--> ended
  ended  --later text from same PSID--> new active (new row)

inquiry.state:
  created as new only
  (no Facebook-driven saved_to_crm / booked)
```

## Invariants

1. Facebook intake never writes `assigned_user_id`, `crm_lead_id`, `state`, or manager flags from the caller.
2. `customer.inquiry.message` is not updated by analysis or by the bot reply.
3. Source on conversation/inquiry is set once to Facebook and not replaced.
4. Disabled / unauthenticated / unknown-`merchant` calls create at most a webhook log row.
5. Users still see only assigned inquiries; Managers see all. No record-rule change.
