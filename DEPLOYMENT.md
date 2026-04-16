# ISMS Portal Hosting

This repo includes a Django backend that persists portal uploads and workspace state. In API mode, uploaded mappings and policies are loaded from PostgreSQL. A fresh deployment still shows the default control catalog (control number and name), and policy detail appears after uploading mapping/policy content.

## What the backend stores

- Uploaded policy documents from the Policies page
- Control/policy mapping data uploaded from the Controls page
- Imported vendor questionnaire metadata and extracted preview text
- Risk register entries
- Review checklist progress
- Local control exclusion state
- Zero Trust assessment tenant profiles, run history, logs, and report bundles

## Initial data load

After first deploy (or after clearing the database), load content in this order:

1. Open Controls and upload a mapping file (`.json` or `.csv`).
2. Open Policies and upload policy source files (`.md`, `.txt`, `.html`).

## Authentication

The portal now requires login for both the HTML pages and the API.

- Local Django username/password auth remains enabled through `django.contrib.auth.backends.ModelBackend`
- SSO is enabled through `social-auth-app-django`
- The default SSO configuration assumes a generic OpenID Connect provider using the `oidc` backend

If you use the default OIDC setup, configure your identity provider callback URL as:

- `https://your-domain.com/complete/oidc/`

Relevant environment variables:

- `SOCIAL_AUTH_SSO_BACKEND_PATH`
- `SOCIAL_AUTH_SSO_BACKEND_NAME`
- `SOCIAL_AUTH_SSO_LOGIN_LABEL`
- `SOCIAL_AUTH_ALLOWED_DOMAINS`
- `SOCIAL_AUTH_ALLOWED_EMAILS`
- `SOCIAL_AUTH_OIDC_OIDC_ENDPOINT`
- `SOCIAL_AUTH_OIDC_KEY`
- `SOCIAL_AUTH_OIDC_SECRET`
- `SOCIAL_AUTH_OIDC_SCOPE`

The default settings also enable per-backend domain and email allowlists, require POST for the SSO begin route, and sanitize post-login redirects.

## Local setup

`scripts/local_setup.sh` is designed for Ubuntu 24.04+.

1. Run `./scripts/local_setup.sh` from the repository root.
2. Run `python manage.py createsuperuser` if you want Django admin access.

The setup script creates `.env` if it does not already exist, installs dependencies into `.venv`, installs PostgreSQL when needed, prompts for `DATABASE_PASSWORD` if empty, ensures the database role and database exist, runs migrations, collects static assets, renders and installs NGINX site config, creates a dedicated non-login system runtime user for Gunicorn (default: `complianceapp`), stages a root-owned runtime bundle under `/opt/complianceapp` (app code and venv by default), creates/enables/starts Gunicorn systemd service units, creates the Zero Trust assessment worker service and writable assessment storage roots, validates app readiness, and starts/enables NGINX when config validation passes.

During setup, the script asks a yes/no question about generating a local self-signed TLS cert. If you answer yes, it creates the cert at the exact `ssl_certificate` and `ssl_certificate_key` paths rendered into `deploy/nginx/complianceapp.conf`.

For non-interactive runs, set `LOCAL_SETUP_CREATE_SELF_SIGNED_CERT=true` or `LOCAL_SETUP_CREATE_SELF_SIGNED_CERT=false`.

Useful local setup overrides:

- `LOCAL_SETUP_DATABASE_URL`
- `LOCAL_SETUP_DATABASE_USER`
- `LOCAL_SETUP_NGINX_SERVER_NAME`
- `LOCAL_SETUP_NGINX_STATIC_ROOT`
- `LOCAL_SETUP_CREATE_SELF_SIGNED_CERT`
- `LOCAL_SETUP_SELF_SIGNED_CERT_DAYS`
- `LOCAL_SETUP_GUNICORN_BIND`
- `LOCAL_SETUP_GUNICORN_WORKERS`
- `LOCAL_SETUP_GUNICORN_USER`
- `LOCAL_SETUP_GUNICORN_GROUP`
- `LOCAL_SETUP_GUNICORN_APP_ROOT` (default: `/opt/complianceapp`)
- `LOCAL_SETUP_GUNICORN_SERVICE_NAME`
- `LOCAL_SETUP_GUNICORN_SERVICE_NAMES` (comma-separated)
- `LOCAL_SETUP_ASSESSMENT_STORAGE_ROOT` (default: `/var/lib/<gunicorn-user>/assessments`)
- `LOCAL_SETUP_ASSESSMENT_CERTIFICATE_ROOT`
- `LOCAL_SETUP_ASSESSMENT_STAGING_ROOT`
- `LOCAL_SETUP_ASSESSMENT_WORKER_SERVICE_NAME`
- `LOCAL_SETUP_HEALTHCHECK_URL`

## Zero Trust assessment prerequisites

The assessment feature is Ubuntu 24.04-only and assumes:

- PowerShell 7 (`pwsh`) is installed on the server
- The runtime venv includes the Python dependency `cryptography`
- The worker service can install or import the `ZeroTrustAssessment` PowerShell module for the runtime user

`scripts/local_setup.sh` now installs PowerShell 7 automatically on Ubuntu 24.04 using Microsoft's preferred package-repository method from the official install guide, then bootstraps the `ZeroTrustAssessment` PowerShell module for the runtime user during setup. If you are deploying manually instead of using the setup script, perform those steps yourself before starting the worker.

The worker stores private assessment certificate material on disk and stores generated report bundles in PostgreSQL after ingestion. The staging export directory is transient and is removed after the report is copied into the database.

The setup script writes these environment variables into the managed runtime env file so the worker uses writable storage outside the root-owned app bundle:

- `ASSESSMENT_STORAGE_ROOT`
- `ASSESSMENT_CERTIFICATE_ROOT`
- `ASSESSMENT_STAGING_ROOT`

Default production layout from `scripts/local_setup.sh`:

- Assessment storage root: `/var/lib/complianceapp/assessments`
- Certificate bundles: `/var/lib/complianceapp/assessments/certificates`
- Transient staging exports: `/var/lib/complianceapp/assessments/staging`
- Worker service: `complianceapp-assessment-worker.service` unless overridden

Operational flow:

1. Save `TenantId` and `ClientId` on the Assessments page.
2. Generate a certificate from the portal.
3. Download the generated `.cer` and upload it to the target Entra app registration as a certificate credential.
4. Run the assessment from the portal.
5. The worker copies the generated report bundle into PostgreSQL and removes the staged filesystem copy.

The portal pages will be available at:

- `http://127.0.0.1:8000/` (direct Gunicorn bind, default)
- `https://localhost/` via NGINX when `LOCAL_SETUP_NGINX_SERVER_NAME` is default and TLS is configured
- `http://localhost/` redirects to `https://localhost/` in the default NGINX config

## PostgreSQL

PostgreSQL is required for both local development and hosting. Set `DATABASE_URL` in `.env` to a PostgreSQL connection string, for example:

`postgresql://localhost:5432/complianceapp`

Set credentials separately:

- `DATABASE_USER=postgres`
- `DATABASE_PASSWORD=<your-password>`

`DATABASE_URL` should not include username or password.

If you want a different local connection string or user, run the setup script with:

- `LOCAL_SETUP_DATABASE_URL=postgresql://localhost:5432/customdb ./scripts/local_setup.sh`
- `LOCAL_SETUP_DATABASE_USER=customuser ./scripts/local_setup.sh`

## Nginx

Deployment includes Nginx as the reverse proxy in front of Gunicorn.

For local Ubuntu 24.04+ setup, `./scripts/local_setup.sh` handles NGINX automatically:

- Installs NGINX when missing
- Renders `server_name`, Gunicorn upstream bind, static alias path, and TLS cert/key paths
- Installs `/etc/nginx/sites-available/complianceapp.conf`
- Creates `/etc/nginx/sites-enabled/complianceapp.conf` symlink
- Validates config and starts/enables `nginx` if valid

For manual/custom deployment, use [deploy/nginx/complianceapp.conf](/Users/coreygeorge/Documents/ISO27001/deploy/nginx/complianceapp.conf) as the template and apply your environment-specific values.

Example manual reload on Ubuntu:

`sudo nginx -t && sudo systemctl reload nginx`

## Hosting notes

- `gunicorn portal_backend.wsgi:application` is the production entrypoint.
- `scripts/local_setup.sh` runs Gunicorn as a dedicated locked system user with a non-login shell (default user: `complianceapp`).
- `scripts/local_setup.sh` points Gunicorn at a root-owned runtime app tree (default `/opt/complianceapp/app`) and runtime venv (default `/opt/complianceapp/venv`).
- `python manage.py run_assessment_worker` is the Zero Trust assessment worker entrypoint.
- The example worker unit template lives at [deploy/systemd/portal-assessment-worker.service](/Users/coreygeorge/Documents/ISO27001/deploy/systemd/portal-assessment-worker.service). Replace the placeholder values with your runtime user, env file, app root, and venv path if you deploy it manually.
- `scripts/local_setup.sh` already runs `python manage.py collectstatic --noinput`.
- The current implementation keeps uploaded content in PostgreSQL-backed records, but does not expose raw file downloads. That avoids adding object storage as a hard dependency for the first hosted version.
- Zero Trust assessment report bundles are stored in PostgreSQL so they remain viewable in the portal after the worker deletes the staged export directory.
- If you later want to retain original uploaded files, add S3-compatible media storage rather than relying on an ephemeral app filesystem.
- Put the Django app and the HTML frontend on the same domain so CSRF protection works without extra CORS setup.
- Create at least one local superuser with `python manage.py createsuperuser` so you retain break-glass admin access if the SSO provider is unavailable.
