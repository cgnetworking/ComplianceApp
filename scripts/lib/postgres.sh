#!/usr/bin/env bash

if [ -n "${LOCAL_SETUP_POSTGRES_SH_LOADED:-}" ]; then
  return 0
fi
LOCAL_SETUP_POSTGRES_SH_LOADED=1

postgres::install_postgresql() {
  if command -v psql >/dev/null 2>&1 && command -v pg_isready >/dev/null 2>&1; then
    return
  fi

  common::log "Installing PostgreSQL with apt-get"
  common::run_as_root apt-get update
  common::run_as_root apt-get install -y postgresql postgresql-contrib

  if ! command -v psql >/dev/null 2>&1; then
    echo "PostgreSQL installation did not provide the psql command." >&2
    exit 1
  fi
}

postgres::start_postgresql() {
  if command -v systemctl >/dev/null 2>&1; then
    common::run_as_root systemctl enable --now postgresql || common::run_as_root systemctl start postgresql || true
    return
  fi

  if command -v service >/dev/null 2>&1; then
    common::run_as_root service postgresql start || true
  fi
}

postgres::parse_database_url() {
  "$PYTHON_BIN" - "$1" <<'PY'
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

postgres::prompt_for_database_password() {
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

postgres::select_admin_psql() {
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

postgres::run_admin_psql() {
  if [ "$PSQL_ADMIN_CMD" = "psql" ]; then
    psql "$@"
    return
  fi

  sudo -u postgres psql "$@"
}

postgres::wait_for_postgresql() {
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

postgres::ensure_database_objects() {
  local db_name="$1"
  local db_user="$2"
  local db_password="$3"

  postgres::run_admin_psql -v ON_ERROR_STOP=1 -d postgres -v db_user="$db_user" -v db_password="$db_password" <<'SQL'
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

  postgres::run_admin_psql -v ON_ERROR_STOP=1 -d postgres -v db_name="$db_name" -v db_owner="$db_user" <<'SQL'
SELECT format('CREATE DATABASE %I OWNER %I', :'db_name', :'db_owner')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db_name')
\gexec
SQL
}

postgres::load_database_connection_settings() {
  local -a db_fields=()

  mapfile -t db_fields < <(postgres::parse_database_url "$DATABASE_URL")
  if [ "${#db_fields[@]}" -ne 3 ]; then
    echo "Unable to parse DATABASE_URL from $ENV_FILE." >&2
    exit 1
  fi

  DB_NAME="${db_fields[0]}"
  DB_HOST="${db_fields[1]}"
  DB_PORT="${db_fields[2]}"
}

postgres::bootstrap_local_database_if_needed() {
  postgres::load_database_connection_settings

  if [[ "$DB_HOST" = "localhost" || "$DB_HOST" = "127.0.0.1" || "$DB_HOST" = "::1" ]]; then
    postgres::install_postgresql
    postgres::start_postgresql
    postgres::wait_for_postgresql "$DB_HOST" "$DB_PORT"
    postgres::select_admin_psql
    postgres::ensure_database_objects "$DB_NAME" "$DATABASE_USER" "$DATABASE_PASSWORD"
    return
  fi

  common::log "Skipping local PostgreSQL install/bootstrap because DATABASE_URL host is $DB_HOST"
}
