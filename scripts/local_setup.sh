#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
ENV_FILE="$ROOT_DIR/.env"
DEFAULT_DATABASE_URL="${LOCAL_SETUP_DATABASE_URL:-postgresql://localhost:5432/complianceapp}"
DEFAULT_DATABASE_USER="${LOCAL_SETUP_DATABASE_USER:-postgres}"
DEFAULT_NGINX_SERVER_NAME="${LOCAL_SETUP_NGINX_SERVER_NAME:-localhost}"
DEFAULT_NGINX_STATIC_ROOT="${LOCAL_SETUP_NGINX_STATIC_ROOT:-/var/www/complianceapp/staticfiles}"
NGINX_SERVER_NAME="$DEFAULT_NGINX_SERVER_NAME"
DEFAULT_ALLOWED_HOSTS="localhost,127.0.0.1"
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
APP_HEALTHCHECK_URL=""
CREATE_SELF_SIGNED_CERT="false"
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

is_truthy() {
  case "${1,,}" in
    1|true|yes|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

ensure_supported_platform() {
  if [ ! -f /etc/os-release ]; then
    echo "Unsupported platform: /etc/os-release is missing. Ubuntu 24.04+ is required." >&2
    exit 1
  fi

  # shellcheck disable=SC1091
  source /etc/os-release
  if [ "${ID:-}" != "ubuntu" ]; then
    echo "Unsupported platform: this setup only supports Ubuntu 24.04+." >&2
    exit 1
  fi
  if ! command -v apt-get >/dev/null 2>&1; then
    echo "Unsupported platform: apt-get is required." >&2
    exit 1
  fi

  local version_id="${VERSION_ID:-}"
  local major=0
  local minor=0
  IFS='.' read -r major minor <<< "$version_id"
  major="${major:-0}"
  minor="${minor:-0}"
  if [ "$major" -lt 24 ] || { [ "$major" -eq 24 ] && [ "$minor" -lt 4 ]; }; then
    echo "Unsupported Ubuntu version: ${version_id:-unknown}. Ubuntu 24.04+ is required." >&2
    exit 1
  fi
}

ensure_python_runtime() {
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    return
  fi

  log "Installing Python runtime and Python 3.12 venv support with apt-get"
  run_as_root apt-get update
  run_as_root apt-get install -y python3 python3-pip python3.12-venv

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

  log "Installing PostgreSQL with apt-get"
  run_as_root apt-get update
  run_as_root apt-get install -y postgresql postgresql-contrib

  if ! command -v psql >/dev/null 2>&1; then
    echo "PostgreSQL installation did not provide the psql command." >&2
    exit 1
  fi
}

install_nginx() {
  if command -v nginx >/dev/null 2>&1; then
    return
  fi

  log "Installing NGINX with apt-get"
  run_as_root apt-get update
  run_as_root apt-get install -y nginx

  if ! command -v nginx >/dev/null 2>&1; then
    echo "NGINX installation did not provide the nginx command." >&2
    exit 1
  fi
}

configure_nginx_site_link() {
  local source_conf="$ROOT_DIR/deploy/nginx/complianceapp.conf"
  local available_dir="/etc/nginx/sites-available"
  local enabled_dir="/etc/nginx/sites-enabled"
  local target_conf="$available_dir/complianceapp.conf"
  local target_link="$enabled_dir/complianceapp.conf"
  local nginx_upstream_bind="${LOCAL_SETUP_GUNICORN_BIND:-127.0.0.1:8000}"
  local nginx_static_root="$NGINX_STATIC_ROOT"
  local primary_server_name=""
  local tls_cert_path=""
  local tls_key_path=""
  local rendered_conf

  if [ ! -f "$source_conf" ]; then
    echo "Expected NGINX config file at $source_conf." >&2
    exit 1
  fi

  primary_server_name="${NGINX_SERVER_NAME%% *}"
  if [ -z "$primary_server_name" ]; then
    primary_server_name="localhost"
  fi

  tls_cert_path="/etc/letsencrypt/live/$primary_server_name/fullchain.pem"
  tls_key_path="/etc/letsencrypt/live/$primary_server_name/privkey.pem"

  NGINX_PRIMARY_SERVER_NAME="$primary_server_name"
  NGINX_SSL_CERT_PATH="$tls_cert_path"
  NGINX_SSL_KEY_PATH="$tls_key_path"

  rendered_conf="$(mktemp)"
  "$PYTHON_BIN" - "$source_conf" "$NGINX_SERVER_NAME" "$nginx_upstream_bind" "$nginx_static_root" "$tls_cert_path" "$tls_key_path" "$rendered_conf" <<'PY'
from pathlib import Path
import sys

source_path = Path(sys.argv[1])
server_name = sys.argv[2]
upstream_bind = sys.argv[3]
static_root = sys.argv[4]
cert_path = sys.argv[5]
key_path = sys.argv[6]
rendered_path = Path(sys.argv[7])

lines = source_path.read_text(encoding="utf-8").splitlines()
updated = []
in_upstream = False
for line in lines:
    stripped = line.lstrip()
    indentation = line[: len(line) - len(stripped)]

    if stripped.startswith("upstream ") and stripped.endswith("{"):
        in_upstream = True
        updated.append(line)
        continue
    if in_upstream and stripped == "}":
        in_upstream = False
        updated.append(line)
        continue

    if stripped.startswith("server_name "):
        updated.append(f"{indentation}server_name {server_name};")
    elif in_upstream and stripped.startswith("server "):
        updated.append(f"{indentation}server {upstream_bind};")
    elif stripped.startswith("alias "):
        static_root_value = static_root.rstrip("/")
        updated.append(f"{indentation}alias {static_root_value}/;")
    elif stripped.startswith("ssl_certificate_key "):
        updated.append(f"{indentation}ssl_certificate_key {key_path};")
    elif stripped.startswith("ssl_certificate "):
        updated.append(f"{indentation}ssl_certificate {cert_path};")
    else:
        updated.append(line)

rendered_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY

  run_as_root mkdir -p "$available_dir" "$enabled_dir"
  run_as_root install -m 0644 "$rendered_conf" "$target_conf"
  run_as_root ln -sfn "$target_conf" "$target_link"
  rm -f "$rendered_conf"
}

sync_static_assets_for_nginx() {
  local collected_static_root="$ROOT_DIR/staticfiles"

  if [ ! -d "$collected_static_root" ]; then
    echo "Collected static directory not found at $collected_static_root." >&2
    echo "Run collectstatic before syncing NGINX static assets." >&2
    exit 1
  fi

  log "Syncing static assets to $NGINX_STATIC_ROOT"
  run_as_root mkdir -p "$NGINX_STATIC_ROOT"
  if command -v rsync >/dev/null 2>&1; then
    run_as_root rsync -a --delete "$collected_static_root"/ "$NGINX_STATIC_ROOT"/
  else
    run_as_root cp -a "$collected_static_root"/. "$NGINX_STATIC_ROOT"/
  fi

  run_as_root find "$NGINX_STATIC_ROOT" -type d -exec chmod 755 {} \;
  run_as_root find "$NGINX_STATIC_ROOT" -type f -exec chmod 644 {} \;
}

start_nginx_service() {
  if ! command -v nginx >/dev/null 2>&1; then
    return
  fi

  if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    if ! run_as_root nginx -t >/dev/null 2>&1; then
      log "Skipping NGINX service enable/start because nginx -t failed."
      log "Review /etc/nginx/sites-available/complianceapp.conf to fix configuration issues."
      return
    fi

    run_as_root systemctl enable nginx || run_as_root systemctl enable nginx.service
    run_as_root systemctl restart nginx || run_as_root systemctl start nginx
    if ! run_as_root systemctl is-active --quiet nginx; then
      echo "NGINX service failed to start." >&2
      echo "Inspect with: sudo journalctl -u nginx --no-pager -n 100" >&2
      exit 1
    fi
    return
  fi
}

prompt_for_nginx_server_name() {
  local input=""

  if [ -n "${LOCAL_SETUP_NGINX_SERVER_NAME:-}" ]; then
    NGINX_SERVER_NAME="$LOCAL_SETUP_NGINX_SERVER_NAME"
    log "Using NGINX server_name from LOCAL_SETUP_NGINX_SERVER_NAME: $NGINX_SERVER_NAME"
    return
  fi

  if [ ! -t 0 ]; then
    log "No interactive terminal detected; using default NGINX server_name: $NGINX_SERVER_NAME"
    return
  fi

  read -r -p "Enter NGINX server_name (space-separated hostnames) [$NGINX_SERVER_NAME]: " input
  input="${input#"${input%%[![:space:]]*}"}"
  input="${input%"${input##*[![:space:]]}"}"
  if [ -n "$input" ]; then
    NGINX_SERVER_NAME="$input"
  fi
}

prompt_for_self_signed_cert_choice() {
  local input=""

  if [ -n "${LOCAL_SETUP_CREATE_SELF_SIGNED_CERT:-}" ]; then
    if is_truthy "${LOCAL_SETUP_CREATE_SELF_SIGNED_CERT}"; then
      CREATE_SELF_SIGNED_CERT="true"
      log "Self-signed certificate creation enabled via LOCAL_SETUP_CREATE_SELF_SIGNED_CERT."
    else
      CREATE_SELF_SIGNED_CERT="false"
      log "Self-signed certificate creation disabled via LOCAL_SETUP_CREATE_SELF_SIGNED_CERT."
    fi
    return
  fi

  if [ ! -t 0 ]; then
    CREATE_SELF_SIGNED_CERT="false"
    log "No interactive terminal detected; skipping self-signed certificate creation."
    return
  fi

  while true; do
    read -r -p "Create a self-signed TLS certificate for NGINX now? [y/N]: " input
    input="${input#"${input%%[![:space:]]*}"}"
    input="${input%"${input##*[![:space:]]}"}"
    case "${input,,}" in
      y|yes)
        CREATE_SELF_SIGNED_CERT="true"
        return
        ;;
      ""|n|no)
        CREATE_SELF_SIGNED_CERT="false"
        return
        ;;
      *)
        echo "Please answer yes or no."
        ;;
    esac
  done
}

create_self_signed_nginx_cert() {
  if [ "$CREATE_SELF_SIGNED_CERT" != "true" ]; then
    return
  fi

  if [ -z "$NGINX_SSL_CERT_PATH" ] || [ -z "$NGINX_SSL_KEY_PATH" ]; then
    echo "Cannot create self-signed cert: NGINX SSL paths are not initialized." >&2
    exit 1
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    log "Installing OpenSSL for self-signed certificate generation"
    run_as_root apt-get update
    run_as_root apt-get install -y openssl
  fi

  local cert_dir
  cert_dir="$(dirname "$NGINX_SSL_CERT_PATH")"
  local san_entries="DNS:localhost,IP:127.0.0.1"
  local host_name=""

  for host_name in $NGINX_SERVER_NAME; do
    if [ -z "$host_name" ]; then
      continue
    fi
    if [[ "$host_name" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
      san_entries="$san_entries,IP:$host_name"
    else
      san_entries="$san_entries,DNS:$host_name"
    fi
  done

  if [ -f "$NGINX_SSL_CERT_PATH" ] && [ -f "$NGINX_SSL_KEY_PATH" ]; then
    log "Reusing existing TLS certificate and key at $cert_dir"
    return
  fi

  log "Creating self-signed TLS certificate for $NGINX_PRIMARY_SERVER_NAME at $cert_dir"
  run_as_root mkdir -p "$cert_dir"
  run_as_root openssl req \
    -x509 \
    -nodes \
    -newkey rsa:2048 \
    -days "${LOCAL_SETUP_SELF_SIGNED_CERT_DAYS:-825}" \
    -keyout "$NGINX_SSL_KEY_PATH" \
    -out "$NGINX_SSL_CERT_PATH" \
    -subj "/CN=$NGINX_PRIMARY_SERVER_NAME" \
    -addext "subjectAltName=$san_entries"
  run_as_root chmod 600 "$NGINX_SSL_KEY_PATH"
  run_as_root chmod 644 "$NGINX_SSL_CERT_PATH"
}

ensure_rsync_installed() {
  if command -v rsync >/dev/null 2>&1; then
    return
  fi

  log "Installing rsync"
  run_as_root apt-get update
  run_as_root apt-get install -y rsync

  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is unavailable after attempted install." >&2
    echo "Install rsync and rerun setup." >&2
    exit 1
  fi
}

sync_runtime_app_bundle() {
  local source_root="$1"
  local deploy_root="$2"
  local deploy_app_dir="$3"
  local deploy_venv_dir="$4"

  ensure_rsync_installed

  log "Syncing runtime app bundle to $deploy_app_dir"
  run_as_root install -d -m 0755 -o root -g root "$deploy_root" "$deploy_app_dir"
  run_as_root rsync -a --delete \
    --exclude ".git/" \
    --exclude ".venv/" \
    --exclude ".env" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache/" \
    "$source_root"/ "$deploy_app_dir"/

  if [ ! -x "$deploy_venv_dir/bin/python" ]; then
    log "Creating runtime virtual environment at $deploy_venv_dir"
    run_as_root "$PYTHON_BIN" -m venv "$deploy_venv_dir"
  fi

  log "Installing runtime dependencies in $deploy_venv_dir"
  run_as_root "$deploy_venv_dir/bin/python" -m pip install --upgrade pip
  run_as_root "$deploy_venv_dir/bin/python" -m pip install -r "$deploy_app_dir/requirements.txt"

  run_as_root chown -R root:root "$deploy_app_dir" "$deploy_venv_dir"
  run_as_root chmod -R a+rX "$deploy_app_dir" "$deploy_venv_dir"
  run_as_root chmod -R go-w "$deploy_app_dir" "$deploy_venv_dir"
}

setup_gunicorn_systemd_service() {
  local default_service_name
  local service_names_raw
  local raw_service_name=""
  local service_name=""
  local service_unit=""
  local service_path=""
  local service_user="${LOCAL_SETUP_GUNICORN_USER:-complianceapp}"
  local service_group="${LOCAL_SETUP_GUNICORN_GROUP:-}"
  local service_bind="${LOCAL_SETUP_GUNICORN_BIND:-127.0.0.1:8000}"
  local service_workers="${LOCAL_SETUP_GUNICORN_WORKERS:-3}"
  local service_app_root="${LOCAL_SETUP_GUNICORN_APP_ROOT:-/opt/complianceapp}"
  local service_working_dir=""
  local service_venv_dir=""
  local nologin_shell="/usr/sbin/nologin"
  local managed_env_dir="/etc/complianceapp"
  local managed_env_file=""
  local managed_env_name=""
  local user_home=""
  local tmp_file=""
  local -a parsed_names=()
  local -a service_units=()

  if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
    log "Skipping Gunicorn systemd service setup because systemd is unavailable."
    return
  fi

  service_app_root="${service_app_root%/}"
  if [ -z "$service_app_root" ]; then
    service_app_root="/opt/complianceapp"
  fi
  if [[ "$service_app_root" != /* ]]; then
    echo "LOCAL_SETUP_GUNICORN_APP_ROOT must be an absolute path." >&2
    exit 1
  fi
  service_working_dir="$service_app_root/app"
  service_venv_dir="$service_app_root/venv"

  if [ -z "$service_group" ]; then
    if id "$service_user" >/dev/null 2>&1; then
      service_group="$(id -gn "$service_user" 2>/dev/null || true)"
    fi
    if [ -z "$service_group" ]; then
      service_group="$service_user"
    fi
  fi

  if [ ! -x "$nologin_shell" ] && [ -x "/sbin/nologin" ]; then
    nologin_shell="/sbin/nologin"
  elif [ ! -x "$nologin_shell" ] && [ -x "/usr/bin/false" ]; then
    nologin_shell="/usr/bin/false"
  fi

  if ! getent group "$service_group" >/dev/null 2>&1; then
    log "Creating Gunicorn runtime group: $service_group"
    run_as_root groupadd --system "$service_group"
  fi

  if ! id "$service_user" >/dev/null 2>&1; then
    user_home="/var/lib/$service_user"
    log "Creating Gunicorn runtime user: $service_user"
    run_as_root useradd --system --home-dir "$user_home" --create-home --shell "$nologin_shell" --gid "$service_group" "$service_user"
  elif [ -n "${LOCAL_SETUP_GUNICORN_GROUP:-}" ]; then
    if ! id -nG "$service_user" | tr ' ' '\n' | grep -Fx "$service_group" >/dev/null 2>&1; then
      log "Adding $service_user to group $service_group"
      run_as_root usermod -a -G "$service_group" "$service_user"
    fi
  fi

  # Runtime account must remain non-interactive and unavailable for human login.
  run_as_root usermod --shell "$nologin_shell" --lock "$service_user"

  sync_runtime_app_bundle "$ROOT_DIR" "$service_app_root" "$service_working_dir" "$service_venv_dir"

  if command -v runuser >/dev/null 2>&1; then
    if ! run_as_root runuser -u "$service_user" -- test -x "$service_working_dir"; then
      echo "Runtime user '$service_user' cannot access $service_working_dir." >&2
      exit 1
    fi
    if ! run_as_root runuser -u "$service_user" -- test -x "$service_venv_dir/bin/gunicorn"; then
      echo "Runtime user '$service_user' cannot execute $service_venv_dir/bin/gunicorn." >&2
      exit 1
    fi
  fi

  managed_env_name="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')"
  managed_env_file="$managed_env_dir/${managed_env_name}.env"
  run_as_root install -d -m 0750 -o root -g "$service_group" "$managed_env_dir"
  run_as_root install -m 0640 -o root -g "$service_group" "$ENV_FILE" "$managed_env_file"

  default_service_name="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')-gunicorn"
  service_names_raw="${LOCAL_SETUP_GUNICORN_SERVICE_NAMES:-${LOCAL_SETUP_GUNICORN_SERVICE_NAME:-$default_service_name}}"
  IFS=',' read -r -a parsed_names <<< "$service_names_raw"

  for raw_service_name in "${parsed_names[@]}"; do
    service_name="$raw_service_name"
    service_name="${service_name#"${service_name%%[![:space:]]*}"}"
    service_name="${service_name%"${service_name##*[![:space:]]}"}"
    if [ -z "$service_name" ]; then
      continue
    fi
    if [[ ! "$service_name" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
      echo "Invalid Gunicorn service name '$service_name'." >&2
      echo "Allowed characters: letters, numbers, underscore, dot, at-sign, and dash." >&2
      exit 1
    fi

    service_unit="${service_name}.service"
    service_path="/etc/systemd/system/$service_unit"
    tmp_file="$(mktemp)"
    cat > "$tmp_file" <<EOF
[Unit]
Description=$service_name Gunicorn service
After=network.target

[Service]
Type=simple
User=$service_user
Group=$service_group
WorkingDirectory=$service_working_dir
EnvironmentFile=$managed_env_file
ExecStart=$service_venv_dir/bin/gunicorn --chdir $service_working_dir portal_backend.wsgi:application --bind $service_bind --workers $service_workers --access-logfile - --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    log "Installing Gunicorn systemd service at $service_path"
    run_as_root install -m 0644 "$tmp_file" "$service_path"
    rm -f "$tmp_file"
    service_units+=("$service_unit")
  done

  if [ "${#service_units[@]}" -eq 0 ]; then
    echo "No valid Gunicorn service names provided." >&2
    echo "Set LOCAL_SETUP_GUNICORN_SERVICE_NAME or LOCAL_SETUP_GUNICORN_SERVICE_NAMES." >&2
    exit 1
  fi

  run_as_root systemctl daemon-reload
  for service_unit in "${service_units[@]}"; do
    log "Enabling $service_unit so Gunicorn starts automatically after reboot"
    run_as_root systemctl enable "$service_unit"
    run_as_root systemctl restart "$service_unit" || run_as_root systemctl start "$service_unit"
    if ! run_as_root systemctl is-active --quiet "$service_unit"; then
      echo "Gunicorn service failed to start: $service_unit" >&2
      echo "Inspect with: sudo journalctl -u $service_unit --no-pager -n 100" >&2
      exit 1
    fi
  done

  GUNICORN_SERVICE_UNITS="${service_units[*]}"
  GUNICORN_RUNTIME_USER="$service_user"
  GUNICORN_RUNTIME_GROUP="$service_group"
  GUNICORN_ENV_FILE="$managed_env_file"
  GUNICORN_RUNTIME_APP_DIR="$service_working_dir"
  GUNICORN_RUNTIME_VENV_DIR="$service_venv_dir"
}

ensure_python_venv() {
  if "$PYTHON_BIN" -c "import venv, ensurepip" >/dev/null 2>&1; then
    return
  fi

  log "Installing python3.12-venv for virtual environment support"
  run_as_root apt-get update
  run_as_root apt-get install -y python3.12-venv

  if ! "$PYTHON_BIN" -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "Python virtual environment support is still unavailable after installing python3.12-venv." >&2
    echo "Ensure PYTHON_BIN points to the system Python interpreter and rerun." >&2
    exit 1
  fi
}

start_postgresql() {
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

merge_host_values() {
  local existing_hosts="${1:-}"
  local additional_hosts="${2:-}"
  "$PYTHON_BIN" - "$existing_hosts" "$additional_hosts" <<'PY'
import re
import sys

existing_hosts = sys.argv[1]
additional_hosts = sys.argv[2]

merged = []
seen = set()

def add_host(raw_host: str) -> None:
    host = raw_host.strip().rstrip(";")
    if not host or host == "_":
        return
    if host.startswith("*."):
        host = f".{host[2:]}"
    host = host.strip()
    if not host or host in seen:
        return
    seen.add(host)
    merged.append(host)

for token in re.split(r"[\s,]+", existing_hosts.strip()):
    add_host(token)

for token in re.split(r"[\s,]+", additional_hosts.strip()):
    add_host(token)

print(",".join(merged), end="")
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


def decode_env_value(raw_value: str) -> str:
    if len(raw_value) < 2:
        return raw_value

    quote = raw_value[0]
    if quote not in {"'", '"'} or raw_value[-1] != quote:
        return raw_value

    inner = raw_value[1:-1]
    if quote == "'":
        return inner

    decoded = []
    idx = 0
    while idx < len(inner):
        char = inner[idx]
        if char == "\\" and idx + 1 < len(inner):
            escaped = inner[idx + 1]
            if escaped in {'\\', '"', '$', '`'}:
                decoded.append(escaped)
                idx += 2
                continue
        decoded.append(char)
        idx += 1
    return "".join(decoded)

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
        parsed_value = decode_env_value(parsed_value)
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


def quote_env_value(value: str) -> str:
    escaped = (
        value.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("$", "\\$")
        .replace("`", "\\`")
    )
    return f'"{escaped}"'


replacement = f"{target_key}={quote_env_value(target_value)}"

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

collect_static_assets() {
  log "Collecting static assets"
  python "$ROOT_DIR/manage.py" collectstatic --noinput
}

verify_app_readiness() {
  if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
    log "Skipping readiness check because systemd is unavailable."
    return
  fi

  local service_bind="${LOCAL_SETUP_GUNICORN_BIND:-127.0.0.1:8000}"
  local healthcheck_url="${LOCAL_SETUP_HEALTHCHECK_URL:-}"

  if [ -z "$healthcheck_url" ]; then
    if [[ "$service_bind" != *:* ]]; then
      log "Skipping readiness check because LOCAL_SETUP_GUNICORN_BIND is not host:port."
      return
    fi

    local bind_host="${service_bind%:*}"
    local bind_port="${service_bind##*:}"
    if [ "$bind_host" = "0.0.0.0" ] || [ "$bind_host" = "::" ]; then
      bind_host="127.0.0.1"
    fi
    healthcheck_url="http://$bind_host:$bind_port/login/"
  fi

  APP_HEALTHCHECK_URL="$healthcheck_url"
  log "Verifying app readiness at $healthcheck_url"
  if ! python - "$healthcheck_url" <<'PY'
from urllib import error, request
import sys
import time

url = sys.argv[1]
deadline = time.time() + 45
last_error = ""

while time.time() < deadline:
    try:
        with request.urlopen(url, timeout=5) as response:
            status = getattr(response, "status", 0) or response.getcode()
            if 200 <= status < 500:
                raise SystemExit(0)
    except error.HTTPError as exc:
        if 200 <= exc.code < 500:
            raise SystemExit(0)
        last_error = f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        last_error = str(exc)
    time.sleep(1)

if last_error:
    print(last_error, file=sys.stderr)
raise SystemExit(1)
PY
  then
    echo "Application readiness check failed at $healthcheck_url." >&2
    exit 1
  fi
}

ensure_supported_platform
ensure_python_runtime
ensure_python_venv
install_nginx
prompt_for_nginx_server_name
DEFAULT_ALLOWED_HOSTS="$(merge_host_values "$DEFAULT_ALLOWED_HOSTS" "$NGINX_SERVER_NAME")"
configure_nginx_site_link
prompt_for_self_signed_cert_choice
create_self_signed_nginx_cert

if [ ! -f "$VENV_DIR/bin/activate" ]; then
  if [ -d "$VENV_DIR" ]; then
    log "Existing virtual environment at $VENV_DIR is incomplete; recreating it."
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

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "$ROOT_DIR/requirements.txt"

if [ ! -f "$ENV_FILE" ]; then
  SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
  printf '%s\n' \
    "DJANGO_SECRET_KEY=$SECRET_KEY" \
    "DJANGO_DEBUG=True" \
    "ALLOWED_HOSTS=$DEFAULT_ALLOWED_HOSTS" \
    "CSRF_TRUSTED_ORIGINS=http://localhost:8000" \
    "TIME_ZONE=America/New_York" \
    "DATABASE_URL=$DEFAULT_DATABASE_URL" \
    "DATABASE_USER=$DEFAULT_DATABASE_USER" \
    "DATABASE_PASSWORD=" \
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
  echo "Created $ENV_FILE"
else
  echo "Using existing $ENV_FILE"
fi

CURRENT_ALLOWED_HOSTS="$(read_env_var ALLOWED_HOSTS)"
if [ -z "$CURRENT_ALLOWED_HOSTS" ]; then
  upsert_env_var ALLOWED_HOSTS "$DEFAULT_ALLOWED_HOSTS"
  echo "Added ALLOWED_HOSTS to $ENV_FILE"
else
  MERGED_ALLOWED_HOSTS="$(merge_host_values "$CURRENT_ALLOWED_HOSTS" "$NGINX_SERVER_NAME")"
  if [ "$MERGED_ALLOWED_HOSTS" != "$CURRENT_ALLOWED_HOSTS" ]; then
    upsert_env_var ALLOWED_HOSTS "$MERGED_ALLOWED_HOSTS"
    echo "Updated ALLOWED_HOSTS in $ENV_FILE to include NGINX server_name values"
  fi
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
fi

# Normalize quoting/escaping so shells, systemd, and Python loaders read the same value.
upsert_env_var DATABASE_PASSWORD "$DATABASE_PASSWORD"

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
collect_static_assets
sync_static_assets_for_nginx
setup_gunicorn_systemd_service
verify_app_readiness
start_nginx_service

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
