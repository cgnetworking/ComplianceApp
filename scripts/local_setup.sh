#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
ENV_FILE="$ROOT_DIR/.env"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python interpreter not found: $PYTHON_BIN" >&2
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
  SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
  printf '%s\n' \
    "DJANGO_SECRET_KEY=$SECRET_KEY" \
    "DJANGO_DEBUG=True" \
    "ALLOWED_HOSTS=localhost,127.0.0.1" \
    "CSRF_TRUSTED_ORIGINS=http://localhost:8000" \
    "TIME_ZONE=America/New_York" \
    "" \
    "# Optional: uncomment to use PostgreSQL locally." \
    "# DATABASE_URL=postgresql://postgres:postgres@localhost:5432/iso27001" \
    "" \
    "# Default SSO configuration uses generic OpenID Connect." \
    "SOCIAL_AUTH_SSO_BACKEND_PATH=social_core.backends.open_id_connect.OpenIdConnectAuth" \
    "SOCIAL_AUTH_SSO_BACKEND_NAME=oidc" \
    "SOCIAL_AUTH_SSO_LOGIN_LABEL=Sign in with SSO" \
    "# SOCIAL_AUTH_ALLOWED_DOMAINS=example.com" \
    "# SOCIAL_AUTH_ALLOWED_EMAILS=" \
    "SOCIAL_AUTH_REDIRECT_IS_HTTPS=False" \
    "# SOCIAL_AUTH_OIDC_OIDC_ENDPOINT=https://your-idp.example.com" \
    "# SOCIAL_AUTH_OIDC_KEY=your-client-id" \
    "# SOCIAL_AUTH_OIDC_SECRET=your-client-secret" \
    "SOCIAL_AUTH_OIDC_SCOPE=openid,profile,email" \
    > "$ENV_FILE"
  echo "Created $ENV_FILE"
else
  echo "Using existing $ENV_FILE"
fi

python "$ROOT_DIR/manage.py" migrate

echo
echo "Local setup complete."
echo "Activate the environment with: source \"$VENV_DIR/bin/activate\""
echo "Start the app with: python manage.py runserver"
