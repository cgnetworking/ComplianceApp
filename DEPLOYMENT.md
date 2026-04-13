# ISMS Portal Hosting

This repo includes a Django backend that persists portal uploads and workspace state. In API mode, controls/policy mapping and uploaded policies are loaded from PostgreSQL, so a fresh deployment starts with no policies until you upload mapping and policy content.

## What the backend stores

- Uploaded policy documents from the Policies page
- Control/policy mapping snapshot data uploaded from the Controls page
- Imported vendor questionnaire metadata and extracted preview text
- Risk register entries
- Review checklist progress
- Local control exclusion state

## Initial data load

After first deploy (or after clearing the database), load content in this order:

1. Open Controls and upload a mapping snapshot (`.json` or `data.js` with `window.ISMS_DATA = {...}`).
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

1. Run `./scripts/local_setup.sh`.
2. Run `python manage.py createsuperuser` if you want Django admin access.

The setup script creates `.env` if it does not already exist, installs dependencies into `.venv`, installs PostgreSQL when needed, prompts for `DATABASE_PASSWORD` if empty, ensures the database role and database exist, runs migrations, collects static assets, creates/enables/starts Gunicorn systemd services, and validates app readiness.

During setup, the script asks a yes/no question about generating a local self-signed TLS cert. If you answer yes, it creates the cert at the exact `ssl_certificate` and `ssl_certificate_key` paths rendered into `deploy/nginx/complianceapp.conf`.

For non-interactive runs, set `LOCAL_SETUP_CREATE_SELF_SIGNED_CERT=true` or `LOCAL_SETUP_CREATE_SELF_SIGNED_CERT=false`.

The portal pages will be available at:

- `http://localhost:8000/`
- `http://localhost:8000/index.html`
- `http://localhost:8000/controls.html`
- `http://localhost:8000/reports.html`
- `http://localhost:8000/reviews.html`
- `http://localhost:8000/policies.html`
- `http://localhost:8000/risks.html`
- `http://localhost:8000/vendors.html`

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

1. Install Nginx on the host (for example, `sudo apt-get install -y nginx` on Ubuntu).
2. Copy [deploy/nginx/complianceapp.conf](/Users/coreygeorge/Documents/ISO27001/deploy/nginx/complianceapp.conf) to `/etc/nginx/sites-available/complianceapp.conf`.
3. Update `server_name`, TLS certificate paths, the static assets path, and Gunicorn port to match your environment.
4. Enable the site and reload Nginx.

Example on Ubuntu:

`sudo ln -sf /etc/nginx/sites-available/complianceapp.conf /etc/nginx/sites-enabled/`

`sudo nginx -t && sudo systemctl reload nginx`

## Hosting notes

- `gunicorn portal_backend.wsgi:application` is the production entrypoint.
- Collect static assets with `python manage.py collectstatic` before enabling Nginx static routing.
- The current implementation keeps uploaded content in PostgreSQL-backed records, but does not expose raw file downloads. That avoids adding object storage as a hard dependency for the first hosted version.
- If you later want to retain original uploaded files, add S3-compatible media storage rather than relying on an ephemeral app filesystem.
- Put the Django app and the HTML frontend on the same domain so CSRF protection works without extra CORS setup.
- Create at least one local superuser with `python manage.py createsuperuser` so you retain break-glass admin access if the SSO provider is unavailable.
