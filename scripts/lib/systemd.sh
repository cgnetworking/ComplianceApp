#!/usr/bin/env bash

if [ -n "${LOCAL_SETUP_SYSTEMD_SH_LOADED:-}" ]; then
  return 0
fi
LOCAL_SETUP_SYSTEMD_SH_LOADED=1

systemd::sync_runtime_app_bundle() {
  local source_root="$1"
  local deploy_root="$2"
  local deploy_app_dir="$3"
  local deploy_venv_dir="$4"

  platform::ensure_rsync_installed

  common::log "Syncing runtime app bundle to $deploy_app_dir"
  common::run_as_root install -d -m 0755 -o root -g root "$deploy_root" "$deploy_app_dir"
  common::run_as_root rsync -a --delete \
    --exclude ".git/" \
    --exclude ".venv/" \
    --exclude ".env" \
    --exclude "__pycache__/" \
    --exclude "*.pyc" \
    --exclude ".pytest_cache/" \
    "$source_root"/ "$deploy_app_dir"/

  if [ ! -x "$deploy_venv_dir/bin/python" ]; then
    common::log "Creating runtime virtual environment at $deploy_venv_dir"
    common::run_as_root "$PYTHON_BIN" -m venv "$deploy_venv_dir"
  fi

  common::log "Installing runtime dependencies in $deploy_venv_dir"
  common::run_as_root "$deploy_venv_dir/bin/python" -m pip install --upgrade pip
  common::run_as_root "$deploy_venv_dir/bin/python" -m pip install -r "$deploy_app_dir/requirements.txt"

  common::run_as_root chown -R root:root "$deploy_app_dir" "$deploy_venv_dir"
  common::run_as_root chmod -R a+rX "$deploy_app_dir" "$deploy_venv_dir"
  common::run_as_root chmod -R go-w "$deploy_app_dir" "$deploy_venv_dir"
}

systemd::render_gunicorn_service() {
  local target_path="$1"
  local service_name="$2"
  local service_user="$3"
  local service_group="$4"
  local service_working_dir="$5"
  local env_file="$6"
  local service_bind="$7"
  local service_workers="$8"
  local credential_name="$9"
  local credential_source_file="${10}"
  local service_venv_dir="${11}"

  cat > "$target_path" <<EOF
[Unit]
Description=$service_name Gunicorn service
After=network.target

[Service]
Type=simple
User=$service_user
Group=$service_group
WorkingDirectory=$service_working_dir
EnvironmentFile=$env_file
LoadCredential=$credential_name:$credential_source_file
ExecStart=$service_venv_dir/bin/gunicorn --chdir $service_working_dir portal_backend.wsgi:application --bind $service_bind --workers $service_workers --access-logfile - --error-logfile -
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

systemd::setup_gunicorn_service() {
  local default_service_name=""
  local service_names_raw=""
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
    common::log "Skipping Gunicorn systemd service setup because systemd is unavailable."
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
    common::log "Creating Gunicorn runtime group: $service_group"
    common::run_as_root groupadd --system "$service_group"
  fi

  if ! id "$service_user" >/dev/null 2>&1; then
    user_home="/var/lib/$service_user"
    common::log "Creating Gunicorn runtime user: $service_user"
    common::run_as_root useradd --system --home-dir "$user_home" --create-home --shell "$nologin_shell" --gid "$service_group" "$service_user"
  elif [ -n "${LOCAL_SETUP_GUNICORN_GROUP:-}" ]; then
    if ! id -nG "$service_user" | tr ' ' '\n' | grep -Fx "$service_group" >/dev/null 2>&1; then
      common::log "Adding $service_user to group $service_group"
      common::run_as_root usermod -a -G "$service_group" "$service_user"
    fi
  fi

  common::run_as_root usermod --shell "$nologin_shell" --lock "$service_user"

  systemd::sync_runtime_app_bundle "$ROOT_DIR" "$service_app_root" "$service_working_dir" "$service_venv_dir"

  if command -v runuser >/dev/null 2>&1; then
    if ! common::run_as_root runuser -u "$service_user" -- test -x "$service_working_dir"; then
      echo "Runtime user '$service_user' cannot access $service_working_dir." >&2
      exit 1
    fi
    if ! common::run_as_root runuser -u "$service_user" -- test -x "$service_venv_dir/bin/gunicorn"; then
      echo "Runtime user '$service_user' cannot execute $service_venv_dir/bin/gunicorn." >&2
      exit 1
    fi
  fi

  managed_env_name="$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')"
  managed_env_file="$managed_env_dir/${managed_env_name}.env"
  common::run_as_root install -d -m 0750 -o root -g "$service_group" "$managed_env_dir"
  common::run_as_root install -m 0640 -o root -g "$service_group" "$ENV_FILE" "$managed_env_file"
  common::ensure_assessment_pfx_password_source_file "$managed_env_dir" "$managed_env_name"

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
    systemd::render_gunicorn_service \
      "$tmp_file" \
      "$service_name" \
      "$service_user" \
      "$service_group" \
      "$service_working_dir" \
      "$managed_env_file" \
      "$service_bind" \
      "$service_workers" \
      "$ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME" \
      "$ASSESSMENT_PFX_PASSWORD_SOURCE_FILE" \
      "$service_venv_dir"

    common::log "Installing Gunicorn systemd service at $service_path"
    common::run_as_root install -m 0644 "$tmp_file" "$service_path"
    rm -f "$tmp_file"
    service_units+=("$service_unit")
  done

  if [ "${#service_units[@]}" -eq 0 ]; then
    echo "No valid Gunicorn service names provided." >&2
    echo "Set LOCAL_SETUP_GUNICORN_SERVICE_NAME or LOCAL_SETUP_GUNICORN_SERVICE_NAMES." >&2
    exit 1
  fi

  common::run_as_root systemctl daemon-reload
  for service_unit in "${service_units[@]}"; do
    common::log "Enabling $service_unit so Gunicorn starts automatically after reboot"
    common::run_as_root systemctl enable "$service_unit"
    common::run_as_root systemctl restart "$service_unit" || common::run_as_root systemctl start "$service_unit"
    if ! common::run_as_root systemctl is-active --quiet "$service_unit"; then
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

systemd::verify_app_readiness() {
  local service_bind="${LOCAL_SETUP_GUNICORN_BIND:-127.0.0.1:8000}"
  local healthcheck_url="${LOCAL_SETUP_HEALTHCHECK_URL:-}"
  local bind_host=""
  local bind_port=""

  if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
    common::log "Skipping readiness check because systemd is unavailable."
    return
  fi

  if [ -z "$healthcheck_url" ]; then
    if [[ "$service_bind" != *:* ]]; then
      common::log "Skipping readiness check because LOCAL_SETUP_GUNICORN_BIND is not host:port."
      return
    fi

    bind_host="${service_bind%:*}"
    bind_port="${service_bind##*:}"
    if [ "$bind_host" = "0.0.0.0" ] || [ "$bind_host" = "::" ]; then
      bind_host="127.0.0.1"
    fi
    healthcheck_url="http://$bind_host:$bind_port/login/"
  fi

  APP_HEALTHCHECK_URL="$healthcheck_url"
  common::log "Verifying app readiness at $healthcheck_url"
  if ! python - "$healthcheck_url" <<'PY'
from urllib import error, request
import sys
import time

url = sys.argv[1]
deadline = time.time() + 45
last_error = ""


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ARG002
        return None


opener = request.build_opener(NoRedirect)

while time.time() < deadline:
    try:
        with opener.open(url, timeout=5) as response:
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
