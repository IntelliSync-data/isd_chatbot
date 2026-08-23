# Implementation Plan: Facebook Messenger Channel

**Branch**: `001-facebook-messenger` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-facebook-messenger/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

Add Facebook Page inbox as a third chatbot channel on the existing inquiry hub. Visitors get the same Q&A and contact-collection rules as the website widget and Zalo; completed contacts become Facebook-sourced `customer.inquiry` records. Staff enable the channel in Chatbot Settings and subscribe Meta to the **shared** receive address `/isd_chatbot/webhook?merchant=facebook`.

Technical approach: a `FacebookChatbotServiceAdapter` beside `ZaloChatbotServiceAdapter`, factory-selected when `merchant=facebook`. The webhook dispatcher splits Zalo vs Facebook on query `merchant` only (do not add `channel=`). Facebook GET echoes `hub.challenge`; POST requires `X-Hub-Signature-256`. Outbound text goes to Graph `v21.0/me/messages`. No general send retry; on OAuth error 190, one `fb_exchange_token` refresh and one resend.

## Technical Context

**Language/Version**: Python 3.10+ (Odoo 18 runtime)

**Primary Dependencies**: Odoo 18 (`base`, `crm`, `calendar`, `mail`, `web`, `survey`, `openeducat_core`); existing `requests`; `spacy` (already required). No new pip package. Facebook Graph HTTP only — no official Facebook SDK.

**Storage**: Existing PostgreSQL via Odoo ORM (`chatbot.conversation`, `chatbot.message`, `customer.inquiry`, `inquiry.source`, `chatbot.webhook.log`, `ir.config_parameter`)

**Testing**: New Odoo `tests/` (`HttpCase` / `TransactionCase`, Graph mocked). Until that harness is green, spec Manual Verification is the constitution gate.

**Target Platform**: Odoo 18.0 addon `isd_chatbot` on Linux deploy hosts (`vfo`, `bloompod`, `ehub-demo`); public HTTPS for Meta callbacks

**Project Type**: Single Odoo application addon (not a standalone web app)

**Performance Goals**: Visitor sees the Messenger reply in under 10 seconds on a healthy network, ≥95% of 20 consecutive Q&A texts (SC-001)

**Constraints**: Public POST must validate length (≤5000) and Facebook authenticity; secrets only in `ir.config_parameter`; `sudo()` only at the webhook boundary; no ThreadPoolExecutor + `request.env`; Facebook isolated from Zalo/widget failures; default channel **off**

**Scale/Scope**: One Facebook Page per database; text-only v1; shared webhook + one new adapter; ~12 production files + new `tests/`

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Pre-design | Post-design |
|---|---|---|
| **I. Inquiry-First** | Pass — Facebook uses `ChatbotService.chat()`; inquiry only when name + email or phone; `message` immutable; no auto CRM/booking | Pass — data-model and contract create `customer.inquiry` only on that path; FR-017 recorded |
| **II. Least-Privilege** | Pass — no record-rule change; Users still `assigned_user_id = user.id`; hide-buttons unused | Pass — no new Public read/write/unlink; webhook log stays Manager-read / Public-create; secrets in config params |
| **III. Public Surface Safety** | Pass if GET verify + HMAC + validator + no secrets in widget | Pass — contract requires signature, 5000-char cap, ignore staff fields, widget unchanged |
| **IV. Integration Isolation** | Pass — new adapter, not inlined into inquiry | Pass — Graph failures log and stop; one 190 refresh only; Zalo path not reused for Facebook payloads |
| **V. Odoo Addon Integrity** | Pass — register views/data/tests in manifest load order | Pass — seed source in `data/inquiry_source_data.xml`; new fields upgrade-safe; `_()` on user strings |
| **Tests for public POST / inquiry promotion** | Fail today (no `tests/`) — **must add** | Pass plan — `tests/` listed in structure and quickstart |

**New public behavior**: Same `/isd_chatbot/webhook` (`auth='public'`). Justified: Meta must call a public HTTPS URL; Zalo already uses this route. Complexity is the Facebook handshake + HMAC, not a second anonymous CRUD API.

**New `sudo()`**: Only inside the existing public webhook / adapter boundary, scoped to conversation, message, inquiry create, config token read/write, webhook log. No staff-wizard `sudo()`.

No unjustified gate failures. Complexity table not required.

## Project Structure

### Documentation (this feature)

```text
specs/001-facebook-messenger/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── facebook-webhook.md
├── spec.md
└── checklists/requirements.md
```

### Source Code (repository root)

```text
controllers/main.py                 # merchant= dispatch, GET verify, HMAC, no thread env
services/chatbot_service.py         # FacebookChatbotServiceAdapter + factory
services/dtos/chat_response_dto.py  # unchanged unless send meta needed
models/chatbot_config.py            # facebook getters/setters + _sync_config_parameters
models/res_config_settings.py       # settings fields
models/chatbot_conversation.py      # chatbot.message.external_message_id
models/inquiry_source.py            # seed facebook in _get_default_sources
models/webhook_log.py               # optional merchant field
data/inquiry_source_data.xml        # inquiry_source_facebook
views/a_res_config_settings_views.xml
views/chatbot_config_views.xml
__manifest__.py                     # no new Odoo depends
tests/__init__.py
tests/test_facebook_webhook.py
tests/test_facebook_channel.py
```

**Structure Decision**: Stay a single Odoo addon. Channel code lives in `services/` + the existing public controller, not a new module.

## Complexity Tracking

> No constitution violations requiring justification.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| — | — | — |

## Phase 0: Research

See [research.md](./research.md). All Technical Context items resolved; no remaining NEEDS CLARIFICATION.

Highlights: shared webhook + `merchant=`; Facebook-shaped parser; HMAC + GET challenge; `facebook:<PSID>` sessions; `external_message_id` dedup; Graph v21.0 send; one 190 refresh; in-request processing; seed Facebook source; add `tests/`.

## Phase 1: Design

- [data-model.md](./data-model.md) — no new models; source seed; message mid; settings keys; conversation lifecycle
- [contracts/facebook-webhook.md](./contracts/facebook-webhook.md) — GET verify, POST HMAC, Graph send/refresh, Zalo coexistence
- [quickstart.md](./quickstart.md) — upgrade, settings, handshake, Q&A, inquiry, isolation, tests

## Implementation sketch (for `/speckit-tasks`, not executed here)

1. Seed `inquiry.source` `facebook` and add `external_message_id` + settings/config keys + Settings UI (enable + secrets + copyable URL).
2. `FacebookChatbotServiceAdapter`: force source, set `external_message_id` on the user message, send Graph text, refresh-on-190 once.
3. Factory: `provider in ('facebook',)`.
4. Webhook: resolve `merchant` only; GET verify; POST HMAC; parse `entry.messaging`; sync dispatch; mark log status. Do not use `ThreadPoolExecutor` with `request.env` for Facebook; route Zalo through the same sync dispatcher so the shared address stays consistent.
5. Tests + manual cases in spec.

## Post-design Constitution Check

Gates still pass. Public surface is the existing webhook with a stricter Facebook branch. Inquiry promotion is unchanged and still staff-only. Tests are part of done, not optional.
