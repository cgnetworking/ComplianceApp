#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB_DIR="$ROOT_DIR/scripts/lib"
PYTHON_BIN="${PYTHON_BIN:-python3}"
ENV_FILE="$ROOT_DIR/.env"
OUTPUT_DIR="${LOCAL_SETUP_RENDER_OUTPUT_DIR:-$ROOT_DIR/.local_setup/rendered}"
DEFAULT_NGINX_SERVER_NAME="${LOCAL_SETUP_NGINX_SERVER_NAME:-localhost}"
DEFAULT_NGINX_STATIC_ROOT="${LOCAL_SETUP_NGINX_STATIC_ROOT:-/var/www/complianceapp/staticfiles}"
NGINX_SERVER_NAME="$DEFAULT_NGINX_SERVER_NAME"
NGINX_STATIC_ROOT="$DEFAULT_NGINX_STATIC_ROOT"
NGINX_PRIMARY_SERVER_NAME=""
NGINX_SSL_CERT_PATH=""
NGINX_SSL_KEY_PATH=""
ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME="assessment-pfx-password"

# shellcheck source=scripts/lib/common.sh
source "$LIB_DIR/common.sh"
# shellcheck source=scripts/lib/nginx.sh
source "$LIB_DIR/nginx.sh"
# shellcheck source=scripts/lib/systemd.sh
source "$LIB_DIR/systemd.sh"
# shellcheck source=scripts/lib/assessment.sh
source "$LIB_DIR/assessment.sh"

main() {
  local managed_name=""
  local managed_env_path=""
  local credential_source_file=""
  local service_bind="${LOCAL_SETUP_GUNICORN_BIND:-127.0.0.1:8000}"
  local service_workers="${LOCAL_SETUP_GUNICORN_WORKERS:-3}"
  local service_user="${LOCAL_SETUP_GUNICORN_USER:-complianceapp}"
  local service_group="${LOCAL_SETUP_GUNICORN_GROUP:-$service_user}"
  local service_app_root="${LOCAL_SETUP_GUNICORN_APP_ROOT:-/opt/complianceapp}"
  local service_working_dir=""
  local service_venv_dir=""
  local gunicorn_service_name=""
  local assessment_service_name=""

  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "PYTHON_BIN '$PYTHON_BIN' was not found." >&2
    exit 1
  fi

  managed_name="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')"
  managed_env_path="$OUTPUT_DIR/env/${managed_name}.env"
  credential_source_file="/etc/complianceapp/${managed_name}-${ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME}"
  service_app_root="${service_app_root%/}"
  service_working_dir="$service_app_root/app"
  service_venv_dir="$service_app_root/venv"
  gunicorn_service_name="${LOCAL_SETUP_GUNICORN_SERVICE_NAME:-${managed_name}-gunicorn}"
  assessment_service_name="${LOCAL_SETUP_ASSESSMENT_WORKER_SERVICE_NAME:-${managed_name}-assessment-worker}"

  mkdir -p "$OUTPUT_DIR/env" "$OUTPUT_DIR/nginx" "$OUTPUT_DIR/systemd"

  if [ -f "$ENV_FILE" ]; then
    cp "$ENV_FILE" "$managed_env_path"
  else
    cat > "$managed_env_path" <<EOF
# Copy your current repository .env here before using this rendered config.
DATABASE_URL=postgresql://localhost:5432/complianceapp
DATABASE_USER=postgres
EOF
  fi

  NGINX_PRIMARY_SERVER_NAME="${NGINX_SERVER_NAME%% *}"
  if [ -z "$NGINX_PRIMARY_SERVER_NAME" ]; then
    NGINX_PRIMARY_SERVER_NAME="localhost"
  fi
  NGINX_SSL_CERT_PATH="/etc/letsencrypt/live/$NGINX_PRIMARY_SERVER_NAME/fullchain.pem"
  NGINX_SSL_KEY_PATH="/etc/letsencrypt/live/$NGINX_PRIMARY_SERVER_NAME/privkey.pem"

  nginx::render_site_config \
    "$ROOT_DIR/deploy/nginx/complianceapp.conf" \
    "$NGINX_SERVER_NAME" \
    "$service_bind" \
    "$NGINX_STATIC_ROOT" \
    "$NGINX_SSL_CERT_PATH" \
    "$NGINX_SSL_KEY_PATH" \
    "$OUTPUT_DIR/nginx/complianceapp.conf"

  systemd::render_gunicorn_service \
    "$OUTPUT_DIR/systemd/${gunicorn_service_name}.service" \
    "$gunicorn_service_name" \
    "$service_user" \
    "$service_group" \
    "$service_working_dir" \
    "$managed_env_path" \
    "$service_bind" \
    "$service_workers" \
    "$ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME" \
    "$credential_source_file" \
    "$service_venv_dir"

  assessment::render_worker_service \
    "$OUTPUT_DIR/systemd/${assessment_service_name}.service" \
    "$assessment_service_name" \
    "$service_user" \
    "$service_group" \
    "$service_working_dir" \
    "$managed_env_path" \
    "$service_venv_dir" \
    "$ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME" \
    "$credential_source_file"

  echo "Rendered config artifacts:"
  echo "- env: $managed_env_path"
  echo "- nginx: $OUTPUT_DIR/nginx/complianceapp.conf"
  echo "- gunicorn unit: $OUTPUT_DIR/systemd/${gunicorn_service_name}.service"
  echo "- assessment worker unit: $OUTPUT_DIR/systemd/${assessment_service_name}.service"
}

main "$@"
