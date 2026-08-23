<!--
Sync Impact Report
- Version change: unversioned template → 1.0.0
- Modified principles:
  - [PRINCIPLE_1_NAME] → I. Inquiry-First Data Boundary
  - [PRINCIPLE_2_NAME] → II. Least-Privilege Access (NON-NEGOTIABLE)
  - [PRINCIPLE_3_NAME] → III. Public Surface Safety
  - [PRINCIPLE_4_NAME] → IV. Integration Isolation
  - [PRINCIPLE_5_NAME] → V. Odoo Addon Integrity
- Added sections:
  - Technology & Compatibility Constraints
  - Specification & Quality Workflow
  - Governance (filled)
- Removed sections: none (scaffold placeholders replaced)
- Follow-up TODOs: none
-->

# ISD Chatbot Constitution

## Core Principles

### I. Inquiry-First Data Boundary

Inbound customer data MUST land in `customer.inquiry` before any CRM,
Calendar, Survey, or OpenEduCat side effect. The inquiry is the system of
record for chatbot-originated leads.

- The original customer message (`message`) MUST remain immutable after
  create. Analysis writes only to `analyzed_message`, `analyzed`,
  `analysis_date`, and `analysis_log`.
- An inquiry MUST have a name and at least one of email or phone.
- Promotion to CRM, booking, survey response, or student record MUST be an
  explicit staff action (or a documented, settings-gated automation). Silent
  auto-promotion from the public chat path is forbidden.
- Promotion MUST be idempotent: if `crm_lead_id` or `calendar_event_id` is
  already set, a second Save to CRM or Booking MUST refuse rather than
  duplicate.
- Assignment is a prerequisite for Save to CRM and Booking. If
  `assigned_user_id` is empty, those actions MUST open the assign wizard
  instead of proceeding.
- Source (`source_id`) and conversation (`conversation_id`) links MUST be
  preserved; they MUST NOT be overwritten by later integrations.

Rationale: Staff review, assignment, and analysis happen on the inquiry.
Skipping it loses audit trail and creates unowned CRM/calendar records.

### II. Least-Privilege Access (NON-NEGOTIABLE)

Access is defined by groups and record rules, not by hidden buttons.

Group ladder (each implies the one below):

- Chatbot Guest — no feature access
- Chatbot User — assigned inquiries only; no unlink; no config write
- Chatbot Editor — inquiries and conversations; no webhook logs or
  statistics reserved for Manager
- Chatbot Manager — full access, including configuration, webhook logs,
  and all inquiries

Hard rules:

- Record rule `rule_inquiry_user` MUST restrict Users to
  `assigned_user_id = user.id`. Record rule `rule_inquiry_manager` MUST
  grant Managers all inquiries. A change that lets a User read unassigned
  or other-users' inquiries is a constitution violation.
- Settings that hide Analyze, Save to CRM, or Invite User are UX only.
  They MUST NOT replace ACL, record rules, or method-level checks.
- Public (`base.group_public`) ACL MUST be create-only on
  `customer.inquiry`, `chatbot.conversation`, and `chatbot.message`.
  Public read/write/unlink on those models is forbidden. Public MUST NOT
  have access to webhook logs beyond the existing create-only row, and
  MUST NOT have write access to `chatbot.config`.
- `sudo()` is allowed only at public HTTP / system-cron boundaries, and
  MUST be scoped to the records and fields that boundary needs. New
  `sudo()` in staff-facing models or wizards requires a written
  justification in the spec or code comment.
- Secrets (OpenAI keys, webhook credentials, SSH deploy keys) MUST live
  in `ir.config_parameter`, Odoo config, or CI secrets — never in
  committed source, widget JavaScript, or default XML data.

### III. Public Surface Safety

Routes with `auth='public'` are the threat surface. Treat them as
untrusted.

- Every public POST (`/chatbot/api/chat`, `/chatbot/api/submit_info`, and
  any successor) MUST validate payload shape, length, and contact fields
  through `chatbot.security.validator` (or a successor that keeps the same
  guarantees) before write.
- Chat messages MUST be rejected if empty or longer than 5000 characters.
- CORS MUST be driven by `isd_chatbot.cors_origins`. A production database
  MUST set an explicit allow-list. Defaulting to `*` is permitted only
  when that parameter is empty (local/dev); shipping a hardcoded `*` is
  forbidden.
- Widget JavaScript (`/chatbot/widget.js`) MUST contain no credentials,
  no internal model names beyond what the public API already exposes, and
  no staff-only URLs.
- Base URL MUST come from `web.base.url` or the current request. Hardcoded
  hostnames (including the e-hub fallback) MUST NOT be the primary
  resolution path.
- Public create of an inquiry MUST NOT accept or honor client-supplied
  `assigned_user_id`, `crm_lead_id`, `state`, or manager-only flags.

### IV. Integration Isolation

CRM, Calendar, mail, Survey, OpenEduCat, outbound webhooks, spaCy, and
OpenAI are adapters around the inquiry and conversation core.

- A failure in one adapter MUST leave the inquiry and conversation in a
  consistent state (no half-written `state`, no dangling required FKs).
  Partial success MUST be logged and surfaced to the acting user.
- Outbound webhook attempts MUST be recorded on `chatbot.webhook.log`
  with enough data to retry or diagnose (endpoint, status, payload
  reference, error).
- Adapter endpoints, models, and feature flags MUST be configured through
  `res.config.settings` / `ir.config_parameter`, not new hardcoded URLs or
  API keys.
- New third-party integrations MUST be added as their own model/service
  and listed in `__manifest__.py` `depends` or
  `external_dependencies`. They MUST NOT be inlined into
  `customer.inquiry` beyond foreign keys and explicit action methods.
- NLP / LLM calls MUST NOT persist raw provider secrets, and MUST NOT
  overwrite `customer.inquiry.message`.

### V. Odoo Addon Integrity

This repository is a single Odoo 18 application addon (`isd_chatbot`),
license LGPL-3.

- New models, views, security, data, and wizards MUST be registered in
  `__manifest__.py` in load-safe order (security before data before
  views).
- XML IDs MUST be module-local and stable. Do not reuse or collide with
  IDs from `crm`, `calendar`, `survey`, or `openeducat_core`.
- Core Odoo or third-party modules MUST NOT be monkey-patched unless the
  spec records why inheritance / override cannot work. `_inherit`
  extensions MUST be additive and upgrade-safe.
- Python files MUST declare `# -*- coding: utf-8 -*-`. User-facing
  strings MUST be wrapped in `_()` so they are translatable.
- Manifest `depends` MUST list every runtime Odoo module this addon
  imports or references. `external_dependencies.python` MUST list
  required non-Odoo packages (currently `spacy`).
- Deploy workflows MAY `git reset --hard` on a dedicated server clone.
  Application code MUST remain upgrade-safe under `-u isd_chatbot`
  (no unreproducible filesystem state, no untracked schema).

## Technology & Compatibility Constraints

- Target platform: **Odoo 18.0**. Features that require a newer or older
  major series are out of scope until this constraint is amended.
- Required Odoo dependencies: `base`, `crm`, `calendar`, `mail`, `web`,
  `survey`, `openeducat_core`. Removing any of these is a MAJOR
  constitution change.
- Required Python package: `spacy`. OpenAI is optional and MUST degrade
  gracefully when unset.
- The embeddable widget is served as HTTP JavaScript, not as
  `web.assets_frontend`, unless a later amendment revives the commented
  assets block.
- Customer-facing copy MAY be Vietnamese or English; code identifiers,
  XML IDs, and constitution language stay English.
- CI deploys (currently `vfo`, `bloompod`, `ehub-demo`) MUST use
  repository secrets for host, user, and key. A workflow MUST NOT embed
  those values.

## Specification & Quality Workflow

Feature work on this addon follows Spec Kit:

1. `/speckit-specify` — user-visible behavior, including who can see or
   act on an inquiry.
2. `/speckit-plan` — models, ACL, public routes, and adapter touchpoints.
3. `/speckit-tasks` — ordered implementation units.
4. `/speckit-implement` — execute only what `tasks.md` lists.

Quality gates (a PR or implement pass is incomplete if any fail):

- Every new `auth='public'` route has an explicit validation path and a
  stated ACL impact.
- Every new model has rows in `security/ir.model.access.csv` for the
  groups that should reach it, and no extra Public write/unlink.
- Inquiry visibility changes include record-rule review against
  Principle II.
- Inquiry promotion changes preserve immutability of `message` and
  idempotency of CRM/booking.
- Automated tests do not yet exist in-repo. New behavior that touches
  record rules, public POST routes, or inquiry promotion MUST add tests
  under `tests/` (or a documented successor) before it is considered
  done. Until that harness exists, the spec MUST list the manual
  verification cases.

Reviews MUST check `security/security.xml`, `security/ir.model.access.csv`,
and `controllers/` on any PR that touches access or HTTP.

## Governance

This constitution supersedes informal practice, README examples, and
ad-hoc PR conventions. Where a spec, plan, or task conflicts with a
principle here, the constitution wins until it is amended.

Amendments:

- Propose and apply changes only through `/speckit-constitution`.
- Each amendment MUST update `CONSTITUTION_VERSION`, `LAST_AMENDED_DATE`,
  and the Sync Impact Report comment.
- Versioning is SemVer for governance, not the Odoo module version
  (`18.0.x.y.z` in `__manifest__.py`):
  - MAJOR: remove or redefine a principle, or drop a required dependency
    / access guarantee.
  - MINOR: add a principle or materially expand guidance.
  - PATCH: clarifications, wording, typos, non-semantic refinements.
- A migration note is required when an amendment invalidates existing
  specs, record rules, or public routes.

Compliance:

- Specs and plans MUST cite the principles they rely on when they touch
  inquiries, ACL, public routes, or adapters.
- Complexity (new `sudo()`, new public route, new third-party adapter)
  MUST be justified in the spec. "We might need it later" is not
  justification.
- Runtime development guidance stays in the spec/plan for the active
  feature; this file stays governance-only.

**Version**: 1.0.0 | **Ratified**: 2026-08-23 | **Last Amended**: 2026-08-23
