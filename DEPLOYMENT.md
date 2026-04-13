# ISMS Portal Hosting

This repo now includes a Django backend that persists portal uploads and workspace state. The static ISO snapshot in `webapp/data.js` stays embedded, and the shared data now lives in the database.

## What the backend stores

- Uploaded policy documents from the Policies page
- Imported vendor questionnaire metadata and extracted preview text
- Risk register entries
- Review checklist progress
- Local control exclusion state

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

1. Run `./scripts/local_setup.sh`.
2. Activate the virtual environment with `source .venv/bin/activate`.
3. Run `python manage.py createsuperuser` if you want Django admin access.
4. Run `python manage.py runserver`.

The setup script creates `.env` if it does not already exist, installs dependencies into `.venv`, and runs migrations. The Django entrypoints load `.env` automatically for local commands.

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

Set `DATABASE_URL` in `.env` to a PostgreSQL connection string, for example:

`postgresql://postgres:postgres@localhost:5432/iso27001`

If `DATABASE_URL` is not set, Django falls back to SQLite for local development.
The generated local `.env` leaves PostgreSQL disabled by default so a new machine can boot with SQLite immediately.

## Hosting notes

- `gunicorn portal_backend.wsgi:application` is the production entrypoint.
- Static assets are served through WhiteNoise after `python manage.py collectstatic`.
- The current implementation keeps uploaded content in PostgreSQL-backed records, but does not expose raw file downloads. That avoids adding object storage as a hard dependency for the first hosted version.
- If you later want to retain original uploaded files, add S3-compatible media storage rather than relying on an ephemeral app filesystem.
- Put the Django app and the HTML frontend on the same domain so CSRF protection works without extra CORS setup.
- Create at least one local superuser with `python manage.py createsuperuser` so you retain break-glass admin access if the SSO provider is unavailable.
