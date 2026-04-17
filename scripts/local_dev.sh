#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LIB_DIR="$ROOT_DIR/scripts/lib"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
ENV_FILE="$ROOT_DIR/.env"
DEFAULT_DATABASE_URL="${LOCAL_SETUP_DATABASE_URL:-postgresql://localhost:5432/complianceapp}"
DEFAULT_DATABASE_USER="${LOCAL_SETUP_DATABASE_USER:-postgres}"
DEFAULT_ASSESSMENT_MODULE_VERSION="${LOCAL_SETUP_ASSESSMENT_MODULE_VERSION:-2.2.0}"
DEFAULT_ASSESSMENT_MODULE_SHA256="${LOCAL_SETUP_ASSESSMENT_MODULE_SHA256:-78a82e566190ffec320bb042c8978e8708ef1f46ac9e17ed84b588d22b2386f0}"
DEFAULT_ALLOWED_HOSTS="localhost,127.0.0.1"
NGINX_SERVER_NAME="${LOCAL_SETUP_NGINX_SERVER_NAME:-localhost}"
DATABASE_URL=""
DATABASE_USER=""
DATABASE_PASSWORD=""
DB_NAME=""
DB_HOST=""
DB_PORT=""

# shellcheck source=scripts/lib/common.sh
source "$LIB_DIR/common.sh"
# shellcheck source=scripts/lib/postgres.sh
source "$LIB_DIR/postgres.sh"
# shellcheck source=scripts/lib/python_env.sh
source "$LIB_DIR/python_env.sh"

main() {
  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "PYTHON_BIN '$PYTHON_BIN' was not found." >&2
    echo "Install Python 3 and rerun scripts/local_dev.sh." >&2
    exit 1
  fi

  if ! "$PYTHON_BIN" -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "Python virtual environment support is unavailable for $PYTHON_BIN." >&2
    echo "Install the system venv package for your Python interpreter and rerun scripts/local_dev.sh." >&2
    exit 1
  fi

  python_env::ensure_project_virtualenv
  python_env::activate_virtualenv
  python_env::install_project_requirements
  python_env::ensure_env_file
  python_env::ensure_default_env_settings
  python_env::load_database_env
  postgres::load_database_connection_settings
  python_env::run_migrations
  python_env::collect_static_assets

  echo
  echo "Local dev bootstrap complete."
  echo "Activate the environment with: source \"$VENV_DIR/bin/activate\""
  echo "Database URL: $DATABASE_URL"
  echo "Database host: $DB_HOST"
  echo "Database port: $DB_PORT"
  echo "This script does not install NGINX, systemd units, or PowerShell modules."
}

main "$@"
