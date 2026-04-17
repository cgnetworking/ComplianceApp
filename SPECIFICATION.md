# ISMS Command Center Specification

Status: reverse-engineered from the current repository implementation on 2026-04-16.

This document describes the system as it exists in code today. It is intended to be the source material for a future implementation plan with clear delegation boundaries.

## 1. Product Definition

The project is an authenticated Django application for running an ISO 27001:2022 program from a single shared workspace. The current product combines:

- an Annex A control register
- a policy library with approval workflow for uploaded policies
- reporting views over control and review cadence data
- recurring review task tracking and an audit log
- a business risk register
- vendor due diligence intake
- a staff-only Zero Trust assessment workspace backed by a background worker

The application is a server-rendered HTML product with page-specific vanilla JavaScript. Persistent state is stored in PostgreSQL. SQLite is explicitly unsupported.

## 2. Product Scope

### Core goals

- Provide one authenticated compliance workspace for shared ISO program operations.
- Let users load a control-to-policy mapping from JSON or CSV and work from that normalized dataset.
- Let users upload policy documents, view rendered content, assign approvers, and record approvals.
- Track recurring review work, checklist completion, and selected audit events.
- Maintain vendor intake records and a risk register in the shared database.
- Let staff users run and review Microsoft Zero Trust assessments without leaving the portal.

### Explicitly out of scope in the current codebase

- multi-workspace or multi-tenant data partitioning
- SQLite support
- public or unauthenticated access
- direct download of original uploaded policy or vendor files
- object storage integration
- a complete system-wide audit trail for every mutation
- API versioning or a formal REST framework layer

## 3. User Roles And Access Rules

### Authenticated user

- Must log in to access all HTML pages and API routes.
- Can use the main compliance workspace features except staff-only assessment functions.

### Policy Reader group member

- A non-staff user in the `Policy Reader` group is treated as read-only.
- Is redirected to the Policies page when attempting to open non-policy pages.
- Can access read-only policy bootstrap state.
- Cannot mutate controls, reviews, vendors, risks, mapping state, or uploaded policy approvals.

### Staff user

- Has access to Django admin.
- Can access the Assessments page and assessment API.
- Can assign approvers to uploaded policies.

### Assigned policy approver

- Must match the uploaded policy's assigned approver identity.
- Can approve that uploaded policy exactly once.

## 4. System Architecture

### Runtime architecture

- Backend framework: Django
- Application package: `portal`
- Project package: `portal_backend`
- Database: PostgreSQL only
- Static asset serving: WhiteNoise
- Authentication: Django local auth plus `social-auth-app-django`
- Frontend: server-rendered templates plus vanilla JavaScript
- Background processing: Django management command for assessment worker

### Request model

- HTML pages are rendered by Django views in `portal/views.py` and `portal/assessment_views.py`.
- JSON APIs are plain Django views under `/api/`.
- All non-GET API requests rely on same-origin session auth plus CSRF tokens.
- Frontend bootstrap is loaded from `/api/state/`, then page-specific rendering runs in the browser.

### Frontend composition

- Templates live in `templates/portal/`.
- Static CSS and JavaScript live in `webapp/`.
- `_app_scripts.html` loads all JavaScript bundles on every page.
- `webapp/js/runtime.js` selects behavior by `document.body.dataset.page`.
- `webapp/js/shared.js` owns shared bootstrap, API, filters, state persistence, and event wiring.

### Deployment model

- Production entrypoint: `gunicorn portal_backend.wsgi:application`
- Reverse proxy: NGINX
- Worker entrypoint: `python manage.py run_assessment_worker`
- Local/prod bootstrap script: `scripts/local_setup.sh`
- Runtime assumptions are documented in `DEPLOYMENT.md`

## 5. Persisted Data Model

### Relational models

#### `UploadedPolicy`

- Stores uploaded policy content, rendered HTML, metadata, approver assignment, and approval timestamps.
- Acts as the uploaded portion of the policy library.

#### `VendorResponse`

- Stores imported vendor due diligence metadata, optional preview text, summary, and raw extracted text.

#### `RiskRecord`

- Stores business risk entries with probability, impact, computed score, owner, raised date, and optional closure date.

#### `ReviewChecklistItem`

- Stores user-created recurring review tasks.

#### `ReviewChecklistRecommendation`

- Stores seeded recommended checklist items from `webapp/default_review_checklist.json`.

#### `PortalState`

- Stores JSON blobs keyed by logical domain.
- Current keys used by the application:
  - `mapping_state`
  - `control_state`
  - `review_state`

#### `ZeroTrustTenantProfile`

- Stores assessment tenant settings: display name, tenant ID, client ID, current certificate thumbprint, and run timestamps.

#### `ZeroTrustCertificate`

- Stores generated X.509 certificate metadata, DER bytes, and PFX bytes for a tenant profile.

#### `ZeroTrustAssessmentRun`

- Stores queued and executed assessment runs, lifecycle timestamps, status, worker identity, module metadata, input snapshot, and summary metadata.

#### `ZeroTrustAssessmentRunLog`

- Stores ordered log lines for an assessment run.

#### `ZeroTrustAssessmentArtifact`

- Stores report bundle files in PostgreSQL, including HTML entrypoint and linked assets.

### JSON state ownership

#### `mapping_state`

- Stores the normalized base mapping payload:
  - controls
  - documents
  - activities
  - checklist
  - policy coverage
  - summary
  - source snapshot

#### `control_state`

- Stores user overrides on top of the base mapping per control ID:
  - applicability override
  - exclusion reason
  - review frequency override
  - owner override
  - policy document mapping override
  - preferred mapped document override

Important: manual mapping edits from Controls and Policies are persisted in `control_state`, not written back into `mapping_state`.

#### `review_state`

- Stores review completion state and audit entries:
  - activity completion flags
  - checklist completion flags
  - completion timestamps
  - audit log entries

## 6. Seed Data And Default Behavior

- Migration `0010_seed_default_portal_state.py` loads default controls from `webapp/default_controls.json`.
- The same migration seeds recommended checklist items from `webapp/default_review_checklist.json`.
- A fresh deployment can operate with default controls even before a custom mapping file is uploaded.
- The workspace label is currently hard-coded in templates as `Acme Co / ISO Program`.

## 7. Functional Modules

### 7.1 Authentication And Session Management

- Login page supports local Django username/password login.
- SSO support is provided through `social-auth-app-django`.
- The default SSO configuration assumes a generic OIDC provider.
- All pages and APIs require authentication.
- Logout is POST-only.
- Redirect handling is sanitized to same-host destinations.

### 7.2 Home

- Shows overview cards derived from current portal state.
- Provides navigation to the main work areas.
- Surfaces upcoming review work, control-domain distribution, and mapped policy summaries.

### 7.3 Controls

- Displays the Annex A control register.
- Supports search and domain filtering.
- Allows mapping file upload in JSON or CSV.
- Shows detail for a selected control.
- Allows editing:
  - owner
  - review frequency
  - applicability
  - exclusion reason
  - mapped policy documents
  - preferred mapped document
- Clicking a control deep-links to the Policies page with control context.

### 7.4 Reports

- Reuses the control dataset and effective control state.
- Supports filters for:
  - domain
  - applicability
  - review cadence
- Renders reporting views for:
  - control coverage by cadence
  - review windows across the year
  - visible domain counts
  - visible mapped policy coverage

### 7.5 Policies

- Builds a single policy library from:
  - mapping documents from `mapping_state`
  - uploaded documents from `UploadedPolicy`
- Lets users upload markdown, text, or HTML policy files.
- Renders uploaded policy content as HTML.
- Supports two library modes:
  - all policies
  - my approvals
- Supports bidirectional control-to-policy mapping from the UI.
- Staff users can assign approvers for uploaded policies.
- Assigned approvers can mark uploaded policies as approved.
- Policy approval writes an audit entry into `review_state.auditLog`.

### 7.6 Reviews

- Uses mapping activities plus recurring checklist items to render a review program.
- Tracks monthly review completion state.
- Supports adding checklist items from:
  - a recommendation picker
  - a custom checklist form
- Stores checklist task definitions in `ReviewChecklistItem`.
- Stores task completion state in `review_state`.

### 7.7 Review Tasks

- Shows all stored recurring review tasks.
- Supports deleting review checklist items.
- Removes orphaned completion state entries when a checklist item is deleted.

### 7.8 Audit Log

- Displays entries from `review_state.auditLog`.
- Current audit coverage is limited.
- Confirmed event sources in the current code:
  - review completion state changes
  - uploaded policy approvals

### 7.9 Risk Register

- Shows and filters shared risk entries.
- Supports create and update behavior from the browser UI.
- Persists the entire risk register through a replacing PUT API.
- Validates:
  - required fields
  - probability and impact in the range 1-5
  - score consistency
  - closure date not before raised date

### 7.10 Vendors

- Imports multiple vendor response files.
- Supports text-like files for inline preview extraction.
- Stores metadata for binary office and PDF uploads even when preview text is unavailable.
- Generates a lightweight summary and inferred vendor name.

### 7.11 Zero Trust Assessments

- Staff-only feature.
- Manages saved tenant profiles.
- Generates an app-only client certificate on the server.
- Allows `.cer` download for upload into the target Entra app registration.
- Queues an assessment run for background execution.
- Streams and stores run logs.
- Ingests the generated report bundle into PostgreSQL.
- Serves the stored HTML report and linked assets directly from the portal.
- Prevents profile deletion while an active run exists.

## 8. Assessment Execution Specification

### Preconditions

- Host OS is Ubuntu 24.04 in the supported deployment path.
- `pwsh` is installed.
- Python dependency `cryptography` is installed.
- The runtime user already has the pinned `ZeroTrustAssessment` PowerShell module installed.

### Run lifecycle

1. Staff user creates or updates a tenant profile.
2. Staff user generates a certificate for that profile.
3. Staff user downloads the `.cer` file and adds it to the target Entra app registration.
4. Staff user queues an assessment run.
5. Worker loop claims the oldest queued run.
6. Worker launches PowerShell, imports or installs the module, connects with the stored certificate, and runs the assessment export.
7. Worker ingests all report artifacts into PostgreSQL.
8. Run is finalized as succeeded, succeeded with warnings, failed, or stale.

### Worker behavior

- Worker lease timestamps are maintained in the database.
- Runs can be marked stale if the worker stops heartbeating.
- Artifacts are rejected if they escape the temporary output root or use symlinks.
- The HTML entrypoint is detected automatically if the preferred filename is absent.

## 9. API Surface

The implemented JSON API is private to the web application and session-authenticated.

### Bootstrap and state

- `GET /api/state/`
  - returns bootstrap state for the current user
  - payload differs for Policy Reader users
- `PUT /api/state/mapping/`
  - stores a normalized mapping payload
- `PUT /api/state/control/`
  - stores normalized control overrides
- `PUT /api/state/review/`
  - stores normalized review completion state

### Mapping and policies

- `POST /api/mapping/uploads/`
  - accepts one JSON or CSV mapping file
- `POST /api/policies/uploads/`
  - accepts one or more uploaded policy files
- `DELETE /api/policies/<document_id>/`
  - deletes one uploaded policy
- `PATCH|PUT /api/policies/<document_id>/approver/`
  - updates the approver for an uploaded policy
- `POST /api/policies/<document_id>/approval/`
  - records approval of an uploaded policy

### Vendors

- `POST /api/vendors/uploads/`
  - imports vendor response files

### Risks

- `PUT /api/risks/`
  - replaces the risk register contents

### Reviews

- `POST /api/checklist/`
  - creates a recurring checklist item
- `DELETE /api/checklist/<checklist_item_id>/`
  - deletes a recurring checklist item

### Assessments

- `GET|POST /api/assessments/`
  - list profiles or save a profile
- `GET|DELETE /api/assessments/<profile_id>/`
  - fetch detail or delete a profile
- `POST /api/assessments/<profile_id>/certificate/`
  - generate a certificate
- `GET /api/assessments/<profile_id>/certificate.cer`
  - download the generated public certificate
- `POST /api/assessments/<profile_id>/runs/`
  - queue a run
- `GET /api/assessments/runs/<run_id>/`
  - fetch run detail and logs
- `GET /api/assessments/runs/<run_id>/logs/`
  - fetch incremental log entries

### Non-API assessment report routes

- `GET /assessments/runs/<run_id>/report/`
  - renders stored HTML report
- `GET /assessments/runs/<run_id>/files/<relative_path>`
  - serves stored report assets

## 10. File And Module Ownership Map

| Area | Primary backend files | Primary frontend files | Primary persistence |
| --- | --- | --- | --- |
| Auth, shell, bootstrap | `portal_backend/settings.py`, `portal/views.py`, `portal_backend/urls.py` | `templates/portal/login.html`, `_sidebar.html`, `_auth_controls.html`, `_app_scripts.html`, `webapp/js/shared.js`, `webapp/js/runtime.js` | session auth, `PortalState` bootstrap reads |
| Controls and home | `portal/views.py`, control and mapping sections of `portal/services.py` | `templates/portal/index.html`, `controls.html`, `webapp/js/home.js`, `controls.js`, `shared.js`, `runtime.js` | `PortalState.mapping_state`, `PortalState.control_state` |
| Policies and approvals | `portal/views.py`, policy sections of `portal/services.py` | `templates/portal/policies.html`, `webapp/js/policies.js`, `shared.js`, `runtime.js` | `UploadedPolicy`, `PortalState.review_state`, mapping/control overlays |
| Reviews and audit | `portal/views.py`, review sections of `portal/services.py` | `templates/portal/reviews.html`, `review_tasks.html`, `audit_log.html`, `webapp/js/reviews.js`, `review_tasks.js`, `audit_log.js`, `shared.js`, `runtime.js` | `ReviewChecklistItem`, `ReviewChecklistRecommendation`, `PortalState.review_state` |
| Risks and vendors | `portal/views.py`, risk and vendor sections of `portal/services.py` | `templates/portal/risks.html`, `vendors.html`, `webapp/js/risks.js`, `vendors.js`, `shared.js`, `runtime.js` | `RiskRecord`, `VendorResponse` |
| Assessments | `portal/assessment_views.py`, `portal/assessment_services.py`, `portal/management/commands/run_assessment_worker.py` | `templates/portal/assessments.html`, `webapp/js/assessments.js`, `shared.js`, `runtime.js` | Zero Trust assessment models |
| Deployment and operations | `scripts/local_setup.sh`, `deploy/`, `DEPLOYMENT.md` | none | runtime env, NGINX, systemd |

## 11. Planning And Delegation Constraints

### Current high-conflict files

- `portal/services.py`
- `webapp/js/shared.js`
- `webapp/js/runtime.js`

These files currently span multiple product domains. Parallel work across controls, policies, reviews, risks, and vendors will collide unless the plan either:

- serializes changes touching these files, or
- first extracts domain-specific modules and wiring

### Safe delegation boundaries today

The cleanest high-level delegation units are:

1. Auth, shell, and bootstrap behavior
2. Controls, reports, and mapping normalization
3. Policies and approval workflow
4. Reviews, review tasks, and audit log
5. Risks and vendors
6. Zero Trust assessments and worker pipeline
7. Deployment and environment automation

### Required sequencing for a parallel plan

- Any plan that changes cross-cutting browser bootstrap should isolate that work first.
- Any plan that changes `portal/services.py` in multiple domains should either extract modules first or assign a single owner for integration.
- Assessment work can be delegated most independently because it already lives in separate service and view modules.
- Deployment work is mostly independent from UI and domain logic.

## 12. Acceptance Baseline For Future Changes

Any future plan derived from this specification should preserve these invariants unless the plan explicitly includes a migration:

- PostgreSQL remains the required system of record.
- HTML pages and APIs remain authenticated.
- Policy Reader access remains read-only and policy-scoped.
- Control mapping upload continues to support both JSON and CSV.
- Uploaded policy approval remains bound to an assigned approver.
- Review completion state and audit entries remain persisted in the database.
- Assessment reports remain viewable after worker ingestion without relying on ephemeral filesystem storage.
- Same-origin CSRF-protected browser/API interaction remains intact.

## 13. Known Gaps And Risks In The Current Implementation

- The product is effectively single-workspace; workspace identity is presentation-only.
- Audit logging is partial rather than comprehensive.
- Uploaded original files are not exposed for later download.
- Shared browser and service modules are broad and will slow parallel feature development.
- The repository does not currently show an automated test suite, so future plans should budget explicit verification work.
