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

The setup script creates `.env` if it does not already exist, installs dependencies into `.venv`, installs PostgreSQL when needed, prompts for `DATABASE_PASSWORD` if empty, ensures the database role and database exist, and runs migrations. The Django entrypoints load `.env` automatically for local commands.

The portal pages will be available at:

- `http://localhost:8000/`
- `http://localhost:8000/index.html`
- `http://localhost:8000/controls.html`
- `http://localhost:8000/reports.html`
- `http://localhost:8000/reviews.html`
- `http://localhost:8000/policies.html`
- `http://localhost:8000/risks.html`
- `http://localhost:8000/vendors.html`

## Containers

This repo includes a containerized runtime with Django + PostgreSQL.

1. Build and start services:

`docker compose up --build -d`

2. Watch logs:

`docker compose logs -f web`

3. Create an admin user:

`docker compose exec web python manage.py createsuperuser`

4. Open the app:

`http://localhost:8000/`

Container files:

- [Dockerfile](/Users/coreygeorge/Documents/ISO27001/Dockerfile)
- [docker-compose.yml](/Users/coreygeorge/Documents/ISO27001/docker-compose.yml)
- [scripts/docker_start.sh](/Users/coreygeorge/Documents/ISO27001/scripts/docker_start.sh)

Useful compose variables (set in your shell or a compose env file):

- `COMPOSE_POSTGRES_DB` (default `complianceapp`)
- `COMPOSE_POSTGRES_USER` (default `postgres`)
- `COMPOSE_POSTGRES_PASSWORD` (default `postgres`)
- `COMPOSE_DJANGO_SECRET_KEY`
- `COMPOSE_DJANGO_DEBUG`
- `COMPOSE_WEB_PORT` (default `8000`)

Stop and remove containers:

`docker compose down`

Stop and remove containers + database volume:

`docker compose down -v`

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
