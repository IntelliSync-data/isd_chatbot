# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

The repo root **is** the Odoo 18 addon `isd_chatbot` (manifest name **ISD Chatbot**, LGPL-3, `application: True`). It is not a standalone Python app. Author: ISD Company. Remote: `IntelliSync-data/isd_chatbot`.

Inbound leads land on `customer.inquiry` first; CRM / Calendar / Survey / OpenEduCat are explicit later promotions. Project governance lives in `.specify/memory/constitution.md` (v1.0.0). Feature work follows Spec Kit: `/speckit-specify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`. `.specify/` and `.claude/` are gitignored.

## Commands

There is no Makefile, `requirements.txt`, or linter config. Tests live under `tests/` (`@tagged('isd_chatbot')`). Development happens against a running Odoo 18 with this directory on the addons path.

```bash
# Install / upgrade the module (paths vary per host; see Deploy)
odoo-bin -c /path/to/odoo.conf -d <db> -u isd_chatbot --stop-after-init --no-http

# Refresh Apps list then upgrade (used in CI)
echo "env['ir.module.module'].update_list(); env.cr.commit()" | odoo-bin shell -c /path/to/odoo.conf -d <db> --no-http

# Interactive shell
odoo-bin shell -c /path/to/odoo.conf -d <db> --no-http
```

After a first copy into addons: restart Odoo, then Apps → install **ISD Chatbot**.

Python extras (not vendored here). Manifest requires `spacy`. README pins `spacy==3.8.7` plus `en_core_web_sm-3.8.0`; Settings default language model is `vi_core_news_lg`.

```bash
pip install spacy==3.8.7
```

No in-repo test command. New record-rule, public POST, or inquiry-promotion behavior needs tests under `tests/` (or listed manual cases in the spec) per the constitution.

## Architecture

```
Website / Zalo / Facebook / REST client
        │
        ▼
controllers/  (auth='public')
        │  validate via chatbot.security.validator
        ▼
services/chatbot_service.py   ← not imported from __init__.py
        │  ChatbotServiceFactory.get_service(provider)
        ▼
chatbot.conversation + chatbot.message
        │  parse_user_info (OpenAI if enabled) then spaCy Q&A
        ▼
customer.inquiry   ← system of record
        │
        ├── action_save_to_crm  → res.partner + crm.lead
        ├── action_booking      → calendar.event (Discuss videocall) + mail
        ├── action_analyze_message → chatbot.openai.service (writes analyzed_*)
        └── action_invite_user  → survey.user_input / op.student
```

**Chat path.** Widget is **not** an asset bundle (the `web.assets_frontend` block in `__manifest__.py` is commented out). `GET /chatbot/widget.js` is a string assembled in `controllers/main.py` from `ir.config_parameter`. The widget POSTs JSON `{ "params": { "message", "session_id", ... } }` to `/chatbot/api/chat` and `/chatbot/api/submit_info`. CORS is built from `isd_chatbot.cors_origins` (empty → `*`).

`ChatbotService.chat()` always tries `chatbot.config.parse_user_info()` first. Name plus email **or** phone creates an inquiry, sets conversation `status='ended'`, and returns the configured end message. Otherwise `get_chatbot_response()` scores the message against active `chatbot.config` Q&A rows with spaCy (per-line patterns, per-row threshold). Extracted/submitted datetimes are treated as `Asia/Ho_Chi_Minh` and stored naive UTC.

`ChatbotServiceFactory.get_service()` returns `ZaloChatbotServiceAdapter` when `provider='zalo'` (forces `source_code='zalo'`, replies via Zalo OA, refreshes token on error `-216`) and `FacebookChatbotServiceAdapter` when `provider='facebook'` (forces `source_code='facebook'`, session `facebook:<PSID>`, replies via Graph `v21.0/me/messages`, one `fb_exchange_token` refresh on OAuth 190). The website chat route always uses the default service with `source_code='chatbot'`.

Shared inbound address `GET|POST /isd_chatbot/webhook?merchant=zalo|facebook` (ignore `channel=`). Facebook GET echoes `hub.challenge` when the verify phrase matches; POST requires `X-Hub-Signature-256`. Disabled or unconfigured Facebook does not chat. Widget `m.me` link is independent of the inbox channel.

**Inquiry hub.** States: `new` → `saved_to_crm` → `booked`. Field `message` is the raw input and must stay immutable; analysis writes `analyzed_message` / `analyzed` / `analysis_date` / `analysis_log`. Save-to-CRM and Booking require `assigned_user_id` (otherwise `inquiry.assign.wizard`). Booking requires email + `consultation_datetime`, calls Save-to-CRM if needed, and refuses if `calendar_event_id` is already set. Constraint: at least email or phone.

**Config is triplicated.** Staff UI is `res.config.settings`. Values persist as `ir.config_parameter` keys `isd_chatbot.*`. `chatbot.config._sync_config_parameters()` is the read path used by OpenAI/Zalo/NLP. Q&A patterns are rows on `chatbot.config`, not settings fields. Hide-Analyze / Hide-Save-to-CRM / Hide-Invite-User are UX flags only — they do not change ACL.

**Other public HTTP.**

| Route | Role |
|---|---|
| `GET /chatbot/widget.js` | Embeddable widget |
| `POST /chatbot/api/chat`, `/chatbot/api/submit_info` | Widget chat + form |
| `GET /chatbot/snippet` | Integration HTML |
| `* /isd_chatbot/webhook` | Shared inbound dump + Zalo/Facebook dispatch (`merchant=`) |
| `/api/inquiry` CRUD + `/analyze` | Public REST, `cors='*'`, `sudo()` |

`/api/inquiry` accepts `assigned_user_email` on create and can GET/list/PUT/DELETE inquiries with no auth. Treat changes there as security-sensitive.

**ACL.** Groups (each implies the one below): Guest → User → Editor → Manager (`security/security.xml`). Users see only `assigned_user_id = user.id`; Managers see all. Public ACL is create-only on inquiry/conversation/message. Webhook logs and statistics menus are Manager-only. `sudo()` is concentrated in public controllers and the chat service.

**Odoo depends:** `base`, `crm`, `calendar`, `mail`, `web`, `survey`, `openeducat_core`. OpenAI is optional and must no-op when disabled/unset.

## Deploy

Push to a customer branch; GitHub Actions SSH-deploys, runs `-u isd_chatbot`, restarts `odoo`.

| Branch | Workflow | Addons dest | `odoo-bin` as |
|---|---|---|---|
| `vfo` | `.github/workflows/vfo.yml` | `/opt/custom-addons/isd_chatbot` | `odoo` |
| `bloompod` | `.github/workflows/bloompod.yml` | `~/custom-addons/isd_chatbot` | `ubuntu` |
| `ehub-demo` | `.github/workflows/ehub-demo.yml` | syncs `~/ehub-demo` from a different clone (`openeducat`) | restart only |

Secrets are per-host (`VFO_*`, `BLOOMPOD_*`, `EHUB_DEMO_*`). Bloompod rsync excludes `views/menu_items_override.xml.*` and `__manifest__.py.*`. `main` has no deploy workflow.

## Embed

```html
<script src="http://your-odoo-domain.com/chatbot/widget.js"></script>
```
