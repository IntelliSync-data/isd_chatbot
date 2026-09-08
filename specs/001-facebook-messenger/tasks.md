---
description: "Task list for Facebook Messenger channel implementation"
---

# Tasks: Facebook Messenger Channel

**Input**: Design documents from `/specs/001-facebook-messenger/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Included. Constitution requires tests for new public POST behavior and inquiry promotion. Write the listed tests first and confirm they fail before implementation.

**Organization**: Tasks are grouped by user story so each story can be implemented, tested, and demoed independently after the foundation.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1–US5 from spec.md
- Every task includes an exact file path

## Path Conventions

Addon root is the repo root (`controllers/`, `models/`, `services/`, `views/`, `data/`, `tests/`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Test package so later story tests have a home. No new Python dependencies.

- [x] T001 Create Odoo test package `tests/__init__.py` (import later test modules as they are added)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared config, source seed, message mid, webhook channel split, and adapter/factory hook. Required before any story.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 [P] Seed inquiry source `facebook` in `data/inquiry_source_data.xml` and `models/inquiry_source.py` `_get_default_sources`
- [x] T003 [P] Add indexed `external_message_id` on `chatbot.message` in `models/chatbot_conversation.py`
- [x] T004 [P] Add `merchant` on `chatbot.webhook.log` in `models/webhook_log.py`
- [x] T005 Add Facebook config keys (`facebook_enabled` default false, page id, page token, app id, app secret, verify token) with password-safe settings fields, `chatbot.config` getters/setters, and `_sync_config_parameters` in `models/res_config_settings.py` and `models/chatbot_config.py`
- [x] T006 Add `FacebookChatbotServiceAdapter` (force `source_code='facebook'`, session `facebook:<PSID>`) and register `provider=='facebook'` on `ChatbotServiceFactory` in `services/chatbot_service.py`
- [x] T007 Refactor `/isd_chatbot/webhook` in `controllers/main.py`: resolve query `merchant` only (`zalo` / `facebook`; ignore `channel=`); persist log `merchant`; unknown/missing merchant logs only; Facebook disabled, **unsigned**, or **enabled-but-unconfigured** (missing page token or app secret) does not chat or send; dispatch Zalo/Facebook **synchronously** (do not pass `request.env` into `ThreadPoolExecutor`); Facebook payload parse/send comes in US1

**Checkpoint**: Foundation ready — settings exist, factory returns a Facebook adapter, webhook splits channels without creating Facebook conversations yet

---

## Phase 3: User Story 1 - Visitor chats with the Facebook Page (Priority: P1) 🎯 MVP

**Goal**: Enabled Facebook Page texts run through the shared Q&A core and the visitor gets a plain-text Messenger reply. Conversation tagged Facebook. Bot still replies if staff also wrote in the thread (do not add a pause).

**Independent Test**: Signed POST of a known Q&A text with `merchant=facebook` creates a Facebook-sourced conversation with user+bot messages and one Graph send (mocked). Disabled, unsigned, or enabled-but-unconfigured credentials create nothing. Website widget chat still works.

### Tests for User Story 1

- [x] T008 [P] [US1] Add failing HttpCase `@tagged('isd_chatbot')`: signed Facebook text → conversation + bot reply; disabled **or enabled-but-unconfigured** → no conversation; widget `POST /chatbot/api/chat` still answers in `tests/test_facebook_webhook.py`
- [x] T009 [P] [US1] Add failing TransactionCase: adapter stamps source `facebook` and session `facebook:<PSID>` in `tests/test_facebook_channel.py`

### Implementation for User Story 1

- [x] T010 [US1] Parse Meta `entry[].messaging[]` text events (not Zalo `payload.message` shape) in `controllers/main.py`
- [x] T011 [US1] Call Facebook adapter `chat()` with PSID, `external_message_id=mid`, and existing 5000-character / empty validation in `controllers/main.py` and `services/chatbot_service.py`
- [x] T012 [US1] After `super().chat()`, POST bot text to `https://graph.facebook.com/v21.0/me/messages` (`messaging_type=RESPONSE`) in `services/chatbot_service.py`

**Checkpoint**: US1 works alone — a test Page text gets the same Q&A answer as the widget

---

## Phase 4: User Story 2 - Complete contact details become a Facebook inquiry (Priority: P1)

**Goal**: Name plus email or phone creates one Facebook inquiry, ends the conversation, sends the end message. Same PSID after end starts a new conversation. Visibility rules unchanged.

**Independent Test**: Signed POST containing name+email creates exactly one Facebook-sourced inquiry; name-only does not; a later message from the same PSID is a new conversation.

### Tests for User Story 2

- [x] T013 [P] [US2] Add failing tests for name+contact → one inquiry, name-only → missing-contact and no inquiry, ended PSID → new conversation, User cannot read unassigned inquiry in `tests/test_facebook_channel.py`

### Implementation for User Story 2

- [x] T014 [US2] Confirm adapter uses shared `ChatbotService.chat()` so inquiry create, immutable `message`, source copy, and end message stay in one path in `services/chatbot_service.py`
- [x] T015 [US2] Confirm `_get_or_create_conversation` only matches `status='active'` so an ended `facebook:<PSID>` opens a new row in `services/chatbot_service.py`

**Checkpoint**: US1 + US2 — Facebook can produce a staff-visible inquiry without CRM auto-promotion

---

## Phase 5: User Story 3 - Staff connect and verify the Facebook Page (Priority: P1)

**Goal**: Managers enter Facebook secrets in Chatbot Settings, toggle the channel, copy the shared receive URL with `merchant=facebook`, and complete Meta’s GET subscription check.

**Independent Test**: GET verify succeeds with matching phrase while enabled and returns 403 when disabled or phrase mismatches. Secrets do not appear in `/chatbot/widget.js`.

### Tests for User Story 3

- [x] T016 [P] [US3] Add failing GET verify tests (200 challenge, 403 bad phrase, 403 disabled, no challenge when `merchant` missing) in `tests/test_facebook_webhook.py`

### Implementation for User Story 3

- [x] T017 [US3] Handle GET `hub.mode=subscribe` for `merchant=facebook` (plain-text challenge or 403) in `controllers/main.py`
- [x] T018 [P] [US3] Add Facebook Settings block (enable, page id, token, app id, secret, verify phrase, password widgets) in `views/a_res_config_settings_views.xml`
- [x] T019 [P] [US3] Mirror Facebook fields under Partner Settings in `views/chatbot_config_views.xml`
- [x] T020 [US3] Show copyable receive address `{web.base.url}/isd_chatbot/webhook?merchant=facebook` in `models/res_config_settings.py` and `views/a_res_config_settings_views.xml`

**Checkpoint**: A Manager can finish Meta subscription without touching Zalo fields

---

## Phase 6: User Story 4 - Staff distinguish Facebook inquiries (Priority: P2)

**Goal**: After upgrade, Facebook is a first-class source. Staff filter inquiries/conversations by Facebook.

**Independent Test**: Source list includes Facebook with no manual create. Website, Zalo, and Facebook inquiries filter correctly.

### Tests for User Story 4

- [x] T021 [P] [US4] Add failing test that `inquiry.source` code `facebook` exists and a Facebook inquiry is returned only when filtering that source in `tests/test_facebook_channel.py`

### Implementation for User Story 4

- [x] T022 [US4] Ensure inquiry and conversation list/search show `source_id` and work for the seeded Facebook source in `views/customer_inquiry_views.xml` and `views/chatbot_conversation_views.xml`

**Checkpoint**: Staff can tell Facebook leads from Zalo and website

---

## Phase 7: User Story 5 - Failed or hostile traffic does not corrupt the queue (Priority: P2)

**Goal**: Bad signatures, replays, non-text events, missing channel, and Graph failures do not duplicate inquiries or take down other channels. No send retry except one refresh+resend on Graph OAuth 190.

**Independent Test**: Replay same `mid` → one inquiry. Image/echo → no inquiry. Unsigned POST → no conversation. Non-190 Graph error → no retry. 190 → one exchange and one resend.

### Tests for User Story 5

- [x] T023 [P] [US5] Add failing HttpCase for bad signature, replayed `mid`, missing `merchant`, non-text/echo, disabled channel in `tests/test_facebook_webhook.py`
- [x] T024 [P] [US5] Add failing adapter tests for Graph non-190 (no retry) and 190 (refresh once, resend once, stop) in `tests/test_facebook_channel.py`

### Implementation for User Story 5

- [x] T025 [US5] Skip `chat()` when `external_message_id` already exists — check in `FacebookChatbotServiceAdapter.chat()` in `services/chatbot_service.py` before `super().chat()`
- [x] T026 [US5] Ignore echoes, attachments, postbacks, deliveries, page-id mismatch, and any client-supplied assignee/state/CRM fields; mark log `ignored` in `controllers/main.py`
- [x] T027 [US5] Implement Graph error handling: no retry except OAuth 190 → `fb_exchange_token` once, save token via `chatbot.config`, resend once, then stop in `services/chatbot_service.py`
- [x] T028 [US5] Set webhook log `status` (`processed` / `error` / `ignored`), `processing_notes`, and `error_message` (no secrets) in `controllers/main.py`

**Checkpoint**: Hostile and failure paths leave the inquiry hub consistent

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Coexistence, docs, and the constitution test run

- [x] T029 [P] Document Facebook adapter, `merchant=` split, and shared webhook in `CLAUDE.md`
- [x] T030 [P] Add Zalo coexistence tests (`merchant=zalo` still uses Zalo adapter; Facebook body never sent to Zalo; `channel=` is ignored) in `tests/test_facebook_webhook.py`
- [x] T031 Audit `/chatbot/widget.js` assembly so no Facebook secrets leak, and disabling Facebook does **not** remove a configured Messenger `m.me` link, in `controllers/main.py`
- [ ] T032 Run `specs/001-facebook-messenger/quickstart.md` automated slice (`odoo-bin --test-enable -u isd_chatbot --test-tags=isd_chatbot`) and record any remaining manual Meta checks
- [x] T033 [P] Add failing HttpCase `@tagged('isd_chatbot')`: Facebook off, `widget_messenger_link` set → `/chatbot/widget.js` still contains that `m.me` URL in `tests/test_facebook_webhook.py`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US1 (Phase 3)**: Depends on Phase 2 — MVP
- **US2 (Phase 4)**: Depends on Phase 2; uses US1 chat path
- **US3 (Phase 5)**: Depends on Phase 2; Settings/GET can proceed in parallel with US1 if staffed
- **US4 (Phase 6)**: Depends on Phase 2 seed (T002); richer after US2 creates inquiries
- **US5 (Phase 7)**: Depends on Phase 2 HMAC + US1 parse/send
- **Polish (Phase 8)**: After the stories you intend to ship

### User Story Dependencies

- **US1 (P1)**: After foundation only
- **US2 (P1)**: After foundation; practically after US1 `chat()` wiring
- **US3 (P1)**: After foundation (config keys); GET/UI independent of Graph send
- **US4 (P2)**: After foundation seed; demo after US2
- **US5 (P2)**: After US1 send path (refresh tests need T012)

### Within Each User Story

- Tests first and failing
- Models/config before services before webhook behavior
- Story checkpoint before the next priority if working sequentially

### Parallel Opportunities

- T002, T003, T004, T005 in parallel during Phase 2
- T008 and T009 together (US1 tests)
- T018 and T019 together (two view files)
- T023 and T024 together (US5 tests)
- T029 and T030 together
- After Phase 2, US3 Settings UI (T018–T020) can run beside US1 parse/send if two people; avoid dual edits to `controllers/main.py`

---

## Parallel Example: User Story 1

```bash
# Tests first:
Task: "Failing HttpCase signed Facebook text in tests/test_facebook_webhook.py"
Task: "Failing adapter session/source test in tests/test_facebook_channel.py"

# Then sequential on shared files:
Task: "Parse messaging texts in controllers/main.py"
Task: "Wire chat() + mid in controllers/main.py and services/chatbot_service.py"
Task: "Graph send in services/chatbot_service.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup
2. Phase 2 Foundation (channel split, HMAC, adapter, source seed)
3. Phase 3 US1 (parse + Q&A + Graph send)
4. **STOP and VALIDATE** T008/T009
5. Demo a test Page question if Meta is available

### Incremental Delivery

1. Setup + Foundation
2. US1 → widget-parity replies
3. US2 → inquiries in the existing queue
4. US3 → Manager can subscribe Meta without shell-set params
5. US4 → source filter
6. US5 → hostile/failure hardening
7. Polish + `--test-enable`

### Suggested MVP scope

**US1 + Phase 2 only.** Do not ship US1 to a production Page without US3 (GET verify) and US5 (dedup / 190 handling) if Meta will call the live URL.

---

## Notes

- [P] = different files, no incomplete dependency
- Do not add live-agent pause (FR-023)
- Do not put Facebook secrets in widget JS or XML defaults
- Keep Zalo working via `merchant=zalo`
- Commit after each task or tight group
- Stop at any checkpoint to validate the story independently
