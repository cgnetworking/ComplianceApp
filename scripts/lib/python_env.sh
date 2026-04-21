#!/usr/bin/env bash

if [ -n "${LOCAL_SETUP_PYTHON_ENV_SH_LOADED:-}" ]; then
  return 0
fi
LOCAL_SETUP_PYTHON_ENV_SH_LOADED=1

python_env::ensure_project_virtualenv() {
  if [ ! -f "$VENV_DIR/bin/activate" ]; then
    if [ -d "$VENV_DIR" ]; then
      common::log "Existing virtual environment at $VENV_DIR is incomplete; recreating it."
      if ! "$PYTHON_BIN" -m venv --clear "$VENV_DIR"; then
        echo "Failed to repair virtual environment at $VENV_DIR." >&2
        echo "Install python3.12-venv and rerun: sudo apt-get install -y python3.12-venv" >&2
        exit 1
      fi
    else
      if ! "$PYTHON_BIN" -m venv "$VENV_DIR"; then
        echo "Failed to create virtual environment at $VENV_DIR." >&2
        echo "Install python3.12-venv and rerun: sudo apt-get install -y python3.12-venv" >&2
        exit 1
      fi
    fi
  fi

  if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Virtual environment is missing $VENV_DIR/bin/activate after creation." >&2
    echo "Install python3.12-venv and rerun: sudo apt-get install -y python3.12-venv" >&2
    exit 1
  fi
}

python_env::activate_virtualenv() {
  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

python_env::install_project_requirements() {
  python -m pip install --upgrade pip
  python -m pip install -r "$ROOT_DIR/requirements.txt"
}

python_env::ensure_env_file() {
  local secret_key=""

  if [ ! -f "$ENV_FILE" ]; then
    secret_key="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
    printf '%s\n' \
      "DJANGO_SECRET_KEY=$secret_key" \
      "DJANGO_DEBUG=False" \
      "ALLOWED_HOSTS=$DEFAULT_ALLOWED_HOSTS" \
      "CSRF_TRUSTED_ORIGINS=http://localhost:8000" \
      "SECURE_SSL_REDIRECT=False" \
      "SESSION_COOKIE_SECURE=False" \
      "CSRF_COOKIE_SECURE=False" \
      "SECURE_HSTS_SECONDS=0" \
      "SECURE_HSTS_INCLUDE_SUBDOMAINS=False" \
      "SECURE_HSTS_PRELOAD=False" \
      "SECURE_CONTENT_TYPE_NOSNIFF=True" \
      "SECURE_REFERRER_POLICY=strict-origin-when-cross-origin" \
      "TIME_ZONE=America/New_York" \
      "DATABASE_URL=$DEFAULT_DATABASE_URL" \
      "DATABASE_USER=$DEFAULT_DATABASE_USER" \
      "DATABASE_PASSWORD=" \
      "ASSESSMENT_MODULE_VERSION=$DEFAULT_ASSESSMENT_MODULE_VERSION" \
      "ASSESSMENT_MODULE_SHA256=$DEFAULT_ASSESSMENT_MODULE_SHA256" \
      "" \
      "# Default SSO configuration uses generic OpenID Connect." \
      "SOCIAL_AUTH_SSO_BACKEND_PATH=social_core.backends.open_id_connect.OpenIdConnectAuth" \
      "SOCIAL_AUTH_SSO_BACKEND_NAME=oidc" \
      "SOCIAL_AUTH_SSO_LOGIN_LABEL=\"Sign in with SSO\"" \
      "# SOCIAL_AUTH_ALLOWED_DOMAINS=example.com" \
      "# SOCIAL_AUTH_ALLOWED_EMAILS=" \
      "SOCIAL_AUTH_REDIRECT_IS_HTTPS=False" \
      "# SOCIAL_AUTH_OIDC_OIDC_ENDPOINT=https://your-idp.example.com" \
      "# SOCIAL_AUTH_OIDC_KEY=your-client-id" \
      "# SOCIAL_AUTH_OIDC_SECRET=your-client-secret" \
      "SOCIAL_AUTH_OIDC_SCOPE=openid,profile,email" \
      > "$ENV_FILE"
    common::ensure_local_env_file_permissions
    echo "Created $ENV_FILE"
    return
  fi

  common::ensure_local_env_file_permissions
  echo "Using existing $ENV_FILE"
}

python_env::ensure_default_env_settings() {
  local current_allowed_hosts=""
  local merged_allowed_hosts=""

  if [ -z "$(common::read_env_var SECURE_SSL_REDIRECT)" ]; then
    common::upsert_env_var SECURE_SSL_REDIRECT "False"
    echo "Added SECURE_SSL_REDIRECT=False to $ENV_FILE for local HTTP checks"
  fi

  if [ -z "$(common::read_env_var SESSION_COOKIE_SECURE)" ]; then
    common::upsert_env_var SESSION_COOKIE_SECURE "False"
    echo "Added SESSION_COOKIE_SECURE=False to $ENV_FILE for local development"
  fi

  if [ -z "$(common::read_env_var CSRF_COOKIE_SECURE)" ]; then
    common::upsert_env_var CSRF_COOKIE_SECURE "False"
    echo "Added CSRF_COOKIE_SECURE=False to $ENV_FILE for local development"
  fi

  if [ -z "$(common::read_env_var SECURE_HSTS_SECONDS)" ]; then
    common::upsert_env_var SECURE_HSTS_SECONDS "0"
    echo "Added SECURE_HSTS_SECONDS=0 to $ENV_FILE for local development"
  fi

  if [ -z "$(common::read_env_var SECURE_HSTS_INCLUDE_SUBDOMAINS)" ]; then
    common::upsert_env_var SECURE_HSTS_INCLUDE_SUBDOMAINS "False"
    echo "Added SECURE_HSTS_INCLUDE_SUBDOMAINS=False to $ENV_FILE for local development"
  fi

  if [ -z "$(common::read_env_var SECURE_HSTS_PRELOAD)" ]; then
    common::upsert_env_var SECURE_HSTS_PRELOAD "False"
    echo "Added SECURE_HSTS_PRELOAD=False to $ENV_FILE for local development"
  fi

  if [ -z "$(common::read_env_var SECURE_CONTENT_TYPE_NOSNIFF)" ]; then
    common::upsert_env_var SECURE_CONTENT_TYPE_NOSNIFF "True"
    echo "Added SECURE_CONTENT_TYPE_NOSNIFF=True to $ENV_FILE"
  fi

  if [ -z "$(common::read_env_var SECURE_REFERRER_POLICY)" ]; then
    common::upsert_env_var SECURE_REFERRER_POLICY "strict-origin-when-cross-origin"
    echo "Added SECURE_REFERRER_POLICY to $ENV_FILE"
  fi

  current_allowed_hosts="$(common::read_env_var ALLOWED_HOSTS)"
  if [ -z "$current_allowed_hosts" ]; then
    common::upsert_env_var ALLOWED_HOSTS "$DEFAULT_ALLOWED_HOSTS"
    echo "Added ALLOWED_HOSTS to $ENV_FILE"
  else
    merged_allowed_hosts="$(common::merge_host_values "$current_allowed_hosts" "$NGINX_SERVER_NAME")"
    if [ "$merged_allowed_hosts" != "$current_allowed_hosts" ]; then
      common::upsert_env_var ALLOWED_HOSTS "$merged_allowed_hosts"
      echo "Updated ALLOWED_HOSTS in $ENV_FILE to include NGINX server_name values"
    fi
  fi

  if [ -z "$(common::read_env_var DATABASE_URL)" ]; then
    common::upsert_env_var DATABASE_URL "$DEFAULT_DATABASE_URL"
    echo "Added DATABASE_URL to $ENV_FILE"
  fi

  if [ -z "$(common::read_env_var DATABASE_USER)" ]; then
    common::upsert_env_var DATABASE_USER "$DEFAULT_DATABASE_USER"
    echo "Added DATABASE_USER to $ENV_FILE"
  fi
}

python_env::load_database_env() {
  DATABASE_URL="$(common::read_env_var DATABASE_URL)"
  DATABASE_USER="$(common::read_env_var DATABASE_USER)"
  DATABASE_PASSWORD="$(common::read_env_var DATABASE_PASSWORD)"

  if [ -z "$DATABASE_URL" ]; then
    echo "DATABASE_URL is missing in $ENV_FILE." >&2
    exit 1
  fi

  if [ -z "$DATABASE_USER" ]; then
    echo "DATABASE_USER is missing in $ENV_FILE." >&2
    exit 1
  fi

  if [ -z "$DATABASE_PASSWORD" ] && [ ! -t 0 ]; then
    echo "DATABASE_PASSWORD is empty in $ENV_FILE and this shell is non-interactive." >&2
    echo "Set DATABASE_PASSWORD in $ENV_FILE and rerun." >&2
    exit 1
  fi

  if [ -z "$DATABASE_PASSWORD" ]; then
    postgres::prompt_for_database_password
  fi

  common::upsert_env_var DATABASE_PASSWORD "$DATABASE_PASSWORD"
}

python_env::run_migrations() {
  python "$ROOT_DIR/manage.py" migrate
}

python_env::collect_static_assets() {
  common::log "Collecting static assets"
  python "$ROOT_DIR/manage.py" collectstatic --noinput
}
