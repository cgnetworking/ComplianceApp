#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB_DIR="$ROOT_DIR/scripts/lib"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
ENV_FILE="$ROOT_DIR/.env"
DEFAULT_DATABASE_URL="${LOCAL_SETUP_DATABASE_URL:-postgresql://localhost:5432/complianceapp}"
DEFAULT_DATABASE_USER="${LOCAL_SETUP_DATABASE_USER:-postgres}"
DEFAULT_NGINX_SERVER_NAME="${LOCAL_SETUP_NGINX_SERVER_NAME:-localhost}"
DEFAULT_NGINX_STATIC_ROOT="${LOCAL_SETUP_NGINX_STATIC_ROOT:-/var/www/complianceapp/staticfiles}"
DEFAULT_ASSESSMENT_MODULE_VERSION="${LOCAL_SETUP_ASSESSMENT_MODULE_VERSION:-2.2.0}"
DEFAULT_ASSESSMENT_MODULE_SHA256="${LOCAL_SETUP_ASSESSMENT_MODULE_SHA256:-78a82e566190ffec320bb042c8978e8708ef1f46ac9e17ed84b588d22b2386f0}"
DEFAULT_PSFRAMEWORK_MODULE_VERSION="1.13.419"
DEFAULT_PSFRAMEWORK_MODULE_SHA256="d9bf13aa683ee87e6f791a054db87b63743bb5478547a3f65fb9dcb6e0f2051b"
DEFAULT_ALLOWED_HOSTS="localhost,127.0.0.1"
NGINX_SERVER_NAME="$DEFAULT_NGINX_SERVER_NAME"
NGINX_STATIC_ROOT="$DEFAULT_NGINX_STATIC_ROOT"
NGINX_PRIMARY_SERVER_NAME=""
NGINX_SSL_CERT_PATH=""
NGINX_SSL_KEY_PATH=""
GUNICORN_SERVICE_UNITS=""
GUNICORN_RUNTIME_USER=""
GUNICORN_RUNTIME_GROUP=""
GUNICORN_ENV_FILE=""
GUNICORN_RUNTIME_APP_DIR=""
GUNICORN_RUNTIME_VENV_DIR=""
ASSESSMENT_WORKER_SERVICE_UNIT=""
APP_HEALTHCHECK_URL=""
CREATE_SELF_SIGNED_CERT="false"
PSQL_ADMIN_CMD=""
ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME="assessment-pfx-password"
ASSESSMENT_PFX_PASSWORD_SOURCE_FILE=""
DATABASE_URL=""
DATABASE_USER=""
DATABASE_PASSWORD=""
DB_NAME=""
DB_HOST=""
DB_PORT=""

# shellcheck source=scripts/lib/common.sh
source "$LIB_DIR/common.sh"
# shellcheck source=scripts/lib/platform.sh
source "$LIB_DIR/platform.sh"
# shellcheck source=scripts/lib/postgres.sh
source "$LIB_DIR/postgres.sh"
# shellcheck source=scripts/lib/python_env.sh
source "$LIB_DIR/python_env.sh"
# shellcheck source=scripts/lib/nginx.sh
source "$LIB_DIR/nginx.sh"
# shellcheck source=scripts/lib/systemd.sh
source "$LIB_DIR/systemd.sh"
# shellcheck source=scripts/lib/assessment.sh
source "$LIB_DIR/assessment.sh"

main() {
  platform::ensure_supported_platform
  platform::ensure_python_runtime
  platform::ensure_python_venv
  platform::install_nginx
  platform::install_powershell

  nginx::prompt_for_server_name
  DEFAULT_ALLOWED_HOSTS="$(common::merge_host_values "$DEFAULT_ALLOWED_HOSTS" "$NGINX_SERVER_NAME")"
  nginx::configure_site_link
  nginx::prompt_for_self_signed_cert_choice
  nginx::create_self_signed_cert

  python_env::ensure_project_virtualenv
  python_env::activate_virtualenv
  python_env::install_project_requirements
  python_env::ensure_env_file
  python_env::ensure_default_env_settings
  python_env::load_database_env

  postgres::bootstrap_local_database_if_needed

  python_env::run_migrations
  python_env::collect_static_assets
  nginx::sync_static_assets
  systemd::setup_gunicorn_service
  assessment::setup_worker_service
  systemd::verify_app_readiness
  nginx::start_service

  echo
  echo "Local setup complete."
  echo "Activate the environment with: source \"$VENV_DIR/bin/activate\""
  echo "Gunicorn service units: ${GUNICORN_SERVICE_UNITS:-none}"
  echo "Gunicorn runtime user: ${GUNICORN_RUNTIME_USER:-none}"
  echo "Gunicorn runtime group: ${GUNICORN_RUNTIME_GROUP:-none}"
  if [ -n "$GUNICORN_ENV_FILE" ]; then
    echo "Gunicorn environment file: $GUNICORN_ENV_FILE"
  fi
  if [ -n "$GUNICORN_RUNTIME_APP_DIR" ]; then
    echo "Gunicorn runtime app dir: $GUNICORN_RUNTIME_APP_DIR"
  fi
  if [ -n "$GUNICORN_RUNTIME_VENV_DIR" ]; then
    echo "Gunicorn runtime venv dir: $GUNICORN_RUNTIME_VENV_DIR"
  fi
  if [ -n "$ASSESSMENT_WORKER_SERVICE_UNIT" ]; then
    echo "Assessment worker service unit: $ASSESSMENT_WORKER_SERVICE_UNIT"
  fi
  if [ -n "$ASSESSMENT_PFX_PASSWORD_SOURCE_FILE" ]; then
    echo "Assessment PFX password source file: $ASSESSMENT_PFX_PASSWORD_SOURCE_FILE"
  fi
  if [ -n "$APP_HEALTHCHECK_URL" ]; then
    echo "Application readiness URL: $APP_HEALTHCHECK_URL"
  fi
  echo "NGINX static root: $NGINX_STATIC_ROOT"
  if [ "$CREATE_SELF_SIGNED_CERT" = "true" ] && [ -n "$NGINX_SSL_CERT_PATH" ] && [ -n "$NGINX_SSL_KEY_PATH" ]; then
    echo "Self-signed cert: $NGINX_SSL_CERT_PATH"
    echo "Self-signed key:  $NGINX_SSL_KEY_PATH"
  fi
  echo "Self-signed TLS cert creation is prompted during setup (yes/no)."
  echo "Non-interactive override: LOCAL_SETUP_CREATE_SELF_SIGNED_CERT=true|false"
  echo "Database URL: $DATABASE_URL"
}

main "$@"
