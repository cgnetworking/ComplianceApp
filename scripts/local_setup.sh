#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
ENV_FILE="$ROOT_DIR/.env"
DEFAULT_DATABASE_URL="${LOCAL_SETUP_DATABASE_URL:-postgresql://localhost:5432/iso27001}"
DEFAULT_DATABASE_USER="${LOCAL_SETUP_DATABASE_USER:-postgres}"
PG_SERVICE_FORMULA=""
PSQL_ADMIN_CMD=""

log() {
  echo "[local_setup] $*"
}

run_as_root() {
  if [ "$(id -u)" -eq 0 ]; then
    "$@"
    return
  fi

  if command -v sudo >/dev/null 2>&1; then
    sudo "$@"
    return
  fi

  echo "This action requires elevated privileges: $*" >&2
  exit 1
}

detect_package_manager() {
  if command -v brew >/dev/null 2>&1; then
    echo "brew"
    return
  fi
  if command -v apt-get >/dev/null 2>&1; then
    echo "apt"
    return
  fi
  if command -v dnf >/dev/null 2>&1; then
    echo "dnf"
    return
  fi
  if command -v yum >/dev/null 2>&1; then
    echo "yum"
    return
  fi
  if command -v pacman >/dev/null 2>&1; then
    echo "pacman"
    return
  fi
  echo ""
}

ensure_python_runtime() {
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    return
  fi

  local manager
  manager="$(detect_package_manager)"
  case "$manager" in
    brew)
      log "Installing Python with Homebrew"
      brew install python
      ;;
    apt)
      log "Installing Python runtime and venv support with apt-get"
      run_as_root apt-get update
      run_as_root apt-get install -y python3 python3-pip python3-venv
      ;;
    dnf)
      log "Installing Python runtime with dnf"
      run_as_root dnf install -y python3 python3-pip
      ;;
    yum)
      log "Installing Python runtime with yum"
      run_as_root yum install -y python3 python3-pip
      ;;
    pacman)
      log "Installing Python runtime with pacman"
      run_as_root pacman -Sy --noconfirm python python-pip
      ;;
    *)
      echo "Python is not installed and no supported package manager was found." >&2
      exit 1
      ;;
  esac

  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="python3"
    else
      echo "Python installation completed but no usable python executable was found." >&2
      exit 1
    fi
  fi
}

install_postgresql() {
  if command -v psql >/dev/null 2>&1 && command -v pg_isready >/dev/null 2>&1; then
    return
  fi

  local manager
  manager="$(detect_package_manager)"
  case "$manager" in
    brew)
      log "Installing PostgreSQL with Homebrew"
      if brew list --versions postgresql@16 >/dev/null 2>&1; then
        PG_SERVICE_FORMULA="postgresql@16"
      elif brew list --versions postgresql >/dev/null 2>&1; then
        PG_SERVICE_FORMULA="postgresql"
      else
        if brew install postgresql@16 >/dev/null 2>&1; then
          PG_SERVICE_FORMULA="postgresql@16"
        else
          brew install postgresql
          PG_SERVICE_FORMULA="postgresql"
        fi
      fi
      ;;
    apt)
      log "Installing PostgreSQL with apt-get"
      run_as_root apt-get update
      run_as_root apt-get install -y postgresql postgresql-contrib
      ;;
    dnf)
      log "Installing PostgreSQL with dnf"
      run_as_root dnf install -y postgresql-server postgresql
      if command -v postgresql-setup >/dev/null 2>&1; then
        run_as_root postgresql-setup --initdb || true
      fi
      ;;
    yum)
      log "Installing PostgreSQL with yum"
      run_as_root yum install -y postgresql-server postgresql
      if command -v postgresql-setup >/dev/null 2>&1; then
        run_as_root postgresql-setup --initdb || true
      fi
      ;;
    pacman)
      log "Installing PostgreSQL with pacman"
      run_as_root pacman -Sy --noconfirm postgresql
      ;;
    *)
      echo "Unable to install PostgreSQL automatically. Install PostgreSQL 14+ and rerun this script." >&2
      exit 1
      ;;
  esac

  if ! command -v psql >/dev/null 2>&1; then
    echo "PostgreSQL installation did not provide the psql command." >&2
    exit 1
  fi
}

install_nginx() {
  if command -v nginx >/dev/null 2>&1; then
    return
  fi

  local manager
  manager="$(detect_package_manager)"
  case "$manager" in
    brew)
      log "Installing NGINX with Homebrew"
      brew install nginx
      ;;
    apt)
      log "Installing NGINX with apt-get"
      run_as_root apt-get update
      run_as_root apt-get install -y nginx
      ;;
    dnf)
      log "Installing NGINX with dnf"
      run_as_root dnf install -y nginx
      ;;
    yum)
      log "Installing NGINX with yum"
      run_as_root yum install -y nginx
      ;;
    pacman)
      log "Installing NGINX with pacman"
      run_as_root pacman -Sy --noconfirm nginx
      ;;
    *)
      echo "Unable to install NGINX automatically. Install NGINX manually and rerun this script." >&2
      exit 1
      ;;
  esac

  if ! command -v nginx >/dev/null 2>&1; then
    echo "NGINX installation did not provide the nginx command." >&2
    exit 1
  fi
}

ensure_python_venv() {
  if "$PYTHON_BIN" -c "import venv" >/dev/null 2>&1; then
    return
  fi

  local manager
  manager="$(detect_package_manager)"
  case "$manager" in
    apt)
      log "Installing python3-venv for virtual environment support"
      run_as_root apt-get update
      run_as_root apt-get install -y python3-venv
      ;;
    dnf)
      log "Installing python3-venv for virtual environment support"
      run_as_root dnf install -y python3-venv || run_as_root dnf install -y python3
      ;;
    yum)
      log "Installing python3-venv for virtual environment support"
      run_as_root yum install -y python3-venv || run_as_root yum install -y python3
      ;;
    *)
      echo "Python venv module is missing. Install python3-venv (or equivalent) and rerun." >&2
      exit 1
      ;;
  esac

  if ! "$PYTHON_BIN" -c "import venv" >/dev/null 2>&1; then
    echo "Python venv module is still unavailable after installation attempt." >&2
    exit 1
  fi
}

start_postgresql() {
  if [ -n "$PG_SERVICE_FORMULA" ] && command -v brew >/dev/null 2>&1; then
    brew services start "$PG_SERVICE_FORMULA" || true
    return
  fi

  if command -v brew >/dev/null 2>&1; then
    if brew list --versions postgresql@16 >/dev/null 2>&1; then
      brew services start postgresql@16 || true
      return
    fi
    if brew list --versions postgresql >/dev/null 2>&1; then
      brew services start postgresql || true
      return
    fi
  fi

  if command -v systemctl >/dev/null 2>&1; then
    run_as_root systemctl enable --now postgresql || run_as_root systemctl start postgresql || true
    return
  fi

  if command -v service >/dev/null 2>&1; then
    run_as_root service postgresql start || true
  fi
}

parse_database_url() {
  python - "$1" <<'PY'
from urllib.parse import unquote, urlparse
import sys

database_url = sys.argv[1]
parsed = urlparse(database_url)
if parsed.scheme.lower() not in {"postgres", "postgresql", "pgsql"}:
    raise SystemExit("DATABASE_URL must use postgres/postgresql/pgsql scheme")
if parsed.username or parsed.password:
    raise SystemExit("DATABASE_URL must not include credentials. Use DATABASE_USER and DATABASE_PASSWORD.")

db_name = unquote(parsed.path.lstrip("/"))
if not db_name:
    raise SystemExit("DATABASE_URL must include a database name")

db_host = parsed.hostname or "localhost"
db_port = str(parsed.port or 5432)

print(db_name)
print(db_host)
print(db_port)
PY
}

read_env_var() {
  local key="$1"
  python - "$ENV_FILE" "$key" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
target_key = sys.argv[2]
value = ""

if env_path.exists():
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].strip()
        if "=" not in line:
            continue

        key, parsed_value = line.split("=", 1)
        key = key.strip()
        parsed_value = parsed_value.strip()
        if key != target_key:
            continue
        if len(parsed_value) >= 2 and parsed_value[0] == parsed_value[-1] and parsed_value[0] in {"'", '"'}:
            parsed_value = parsed_value[1:-1]
        value = parsed_value

print(value, end="")
PY
}

upsert_env_var() {
  local key="$1"
  local value="$2"
  python - "$ENV_FILE" "$key" "$value" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
target_key = sys.argv[2]
target_value = sys.argv[3]
replacement = f"{target_key}={target_value}"

lines = []
replaced = False
if env_path.exists():
    lines = env_path.read_text(encoding="utf-8").splitlines()

updated = []
for raw_line in lines:
    stripped = raw_line.strip()
    normalized = stripped[len("export ") :].strip() if stripped.startswith("export ") else stripped
    if normalized.startswith(f"{target_key}="):
        if not replaced:
            updated.append(replacement)
            replaced = True
        continue
    updated.append(raw_line)

if not replaced:
    if updated and updated[-1] != "":
        updated.append("")
    updated.append(replacement)

env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

prompt_for_database_password() {
  local first=""
  local second=""

  while true; do
    read -r -s -p "Enter PostgreSQL password for $DATABASE_USER: " first
    echo
    if [ -z "$first" ]; then
      echo "Password cannot be empty."
      continue
    fi

    read -r -s -p "Confirm PostgreSQL password for $DATABASE_USER: " second
    echo
    if [ "$first" != "$second" ]; then
      echo "Passwords did not match. Try again."
      continue
    fi

    DATABASE_PASSWORD="$first"
    break
  done
}

select_admin_psql() {
  if psql -d postgres -c "SELECT 1" >/dev/null 2>&1; then
    PSQL_ADMIN_CMD="psql"
    return
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -u postgres psql -d postgres -c "SELECT 1" >/dev/null 2>&1; then
    PSQL_ADMIN_CMD="sudo -u postgres psql"
    return
  fi

  echo "Unable to connect as a PostgreSQL admin user." >&2
  echo "Ensure PostgreSQL is running and that your user can administer the server." >&2
  exit 1
}

run_admin_psql() {
  if [ "$PSQL_ADMIN_CMD" = "psql" ]; then
    psql "$@"
    return
  fi

  sudo -u postgres psql "$@"
}

wait_for_postgresql() {
  local host="$1"
  local port="$2"

  for _ in $(seq 1 30); do
    if pg_isready -h "$host" -p "$port" >/dev/null 2>&1; then
      return
    fi
    sleep 1
  done

  echo "PostgreSQL is installed but did not become ready at $host:$port." >&2
  exit 1
}

ensure_database_objects() {
  local db_name="$1"
  local db_user="$2"
  local db_password="$3"

  run_admin_psql -v ON_ERROR_STOP=1 -d postgres -v db_user="$db_user" -v db_password="$db_password" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN', :'db_user')
WHERE :'db_password' = ''
  AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user')
\gexec

SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE :'db_password' <> ''
  AND NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user')
\gexec

SELECT format('ALTER ROLE %I LOGIN', :'db_user')
WHERE :'db_password' = ''
  AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user')
\gexec

SELECT format('ALTER ROLE %I LOGIN PASSWORD %L', :'db_user', :'db_password')
WHERE :'db_password' <> ''
  AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'db_user')
\gexec
SQL

  run_admin_psql -v ON_ERROR_STOP=1 -d postgres -v db_name="$db_name" -v db_owner="$db_user" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name')
\gexec
SQL
}

ensure_python_runtime
ensure_python_venv
install_nginx

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
    "DATABASE_URL=$DEFAULT_DATABASE_URL" \
    "DATABASE_USER=$DEFAULT_DATABASE_USER" \
    "DATABASE_PASSWORD=" \
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

if [ -z "$(read_env_var DATABASE_URL)" ]; then
  upsert_env_var DATABASE_URL "$DEFAULT_DATABASE_URL"
  echo "Added DATABASE_URL to $ENV_FILE"
fi

if [ -z "$(read_env_var DATABASE_USER)" ]; then
  upsert_env_var DATABASE_USER "$DEFAULT_DATABASE_USER"
  echo "Added DATABASE_USER to $ENV_FILE"
fi

DATABASE_URL="$(read_env_var DATABASE_URL)"
DATABASE_USER="$(read_env_var DATABASE_USER)"
DATABASE_PASSWORD="$(read_env_var DATABASE_PASSWORD)"

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
  prompt_for_database_password
  upsert_env_var DATABASE_PASSWORD "$DATABASE_PASSWORD"
fi

mapfile -t DB_FIELDS < <(parse_database_url "$DATABASE_URL")
if [ "${#DB_FIELDS[@]}" -ne 3 ]; then
  echo "Unable to parse DATABASE_URL from $ENV_FILE." >&2
  exit 1
fi

DB_NAME="${DB_FIELDS[0]}"
DB_HOST="${DB_FIELDS[1]}"
DB_PORT="${DB_FIELDS[2]}"

if [[ "$DB_HOST" = "localhost" || "$DB_HOST" = "127.0.0.1" || "$DB_HOST" = "::1" ]]; then
  install_postgresql
  start_postgresql
  wait_for_postgresql "$DB_HOST" "$DB_PORT"
  select_admin_psql
  ensure_database_objects "$DB_NAME" "$DATABASE_USER" "$DATABASE_PASSWORD"
else
  log "Skipping local PostgreSQL install/bootstrap because DATABASE_URL host is $DB_HOST"
fi

python "$ROOT_DIR/manage.py" migrate

echo
echo "Local setup complete."
echo "Activate the environment with: source \"$VENV_DIR/bin/activate\""
echo "Start the app with: python manage.py runserver"
echo "Database URL: $DATABASE_URL"
