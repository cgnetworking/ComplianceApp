#!/usr/bin/env bash

if [ -n "${LOCAL_SETUP_NGINX_SH_LOADED:-}" ]; then
  return 0
fi
LOCAL_SETUP_NGINX_SH_LOADED=1

nginx::render_site_config() {
  local source_conf="$1"
  local server_name="$2"
  local upstream_bind="$3"
  local static_root="$4"
  local cert_path="$5"
  local key_path="$6"
  local output_path="$7"

  "$PYTHON_BIN" - "$source_conf" "$server_name" "$upstream_bind" "$static_root" "$cert_path" "$key_path" "$output_path" <<'PY'
from pathlib import Path
import sys

source_path = Path(sys.argv[1])
server_name = sys.argv[2]
upstream_bind = sys.argv[3]
static_root = sys.argv[4]
cert_path = sys.argv[5]
key_path = sys.argv[6]
output_path = Path(sys.argv[7])

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

output_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
}

nginx::configure_site_link() {
  local source_conf="$ROOT_DIR/deploy/nginx/complianceapp.conf"
  local available_dir="/etc/nginx/sites-available"
  local enabled_dir="/etc/nginx/sites-enabled"
  local target_conf="$available_dir/complianceapp.conf"
  local target_link="$enabled_dir/complianceapp.conf"
  local nginx_upstream_bind="${LOCAL_SETUP_GUNICORN_BIND:-127.0.0.1:8000}"
  local primary_server_name=""
  local rendered_conf=""

  if [ ! -f "$source_conf" ]; then
    echo "Expected NGINX config file at $source_conf." >&2
    exit 1
  fi

  primary_server_name="${NGINX_SERVER_NAME%% *}"
  if [ -z "$primary_server_name" ]; then
    primary_server_name="localhost"
  fi

  NGINX_PRIMARY_SERVER_NAME="$primary_server_name"
  NGINX_SSL_CERT_PATH="/etc/letsencrypt/live/$primary_server_name/fullchain.pem"
  NGINX_SSL_KEY_PATH="/etc/letsencrypt/live/$primary_server_name/privkey.pem"

  rendered_conf="$(mktemp)"
  nginx::render_site_config \
    "$source_conf" \
    "$NGINX_SERVER_NAME" \
    "$nginx_upstream_bind" \
    "$NGINX_STATIC_ROOT" \
    "$NGINX_SSL_CERT_PATH" \
    "$NGINX_SSL_KEY_PATH" \
    "$rendered_conf"

  common::run_as_root mkdir -p "$available_dir" "$enabled_dir"
  common::run_as_root install -m 0644 "$rendered_conf" "$target_conf"
  common::run_as_root ln -sfn "$target_conf" "$target_link"
  rm -f "$rendered_conf"
}

nginx::prompt_for_server_name() {
  local input=""

  if [ -n "${LOCAL_SETUP_NGINX_SERVER_NAME:-}" ]; then
    NGINX_SERVER_NAME="$LOCAL_SETUP_NGINX_SERVER_NAME"
    common::log "Using NGINX server_name from LOCAL_SETUP_NGINX_SERVER_NAME: $NGINX_SERVER_NAME"
    return
  fi

  if [ ! -t 0 ]; then
    common::log "No interactive terminal detected; using default NGINX server_name: $NGINX_SERVER_NAME"
    return
  fi

  read -r -p "Enter NGINX server_name (space-separated hostnames) [$NGINX_SERVER_NAME]: " input
  input="${input#"${input%%[![:space:]]*}"}"
  input="${input%"${input##*[![:space:]]}"}"
  if [ -n "$input" ]; then
    NGINX_SERVER_NAME="$input"
  fi
}

nginx::prompt_for_self_signed_cert_choice() {
  local input=""

  if [ -n "${LOCAL_SETUP_CREATE_SELF_SIGNED_CERT:-}" ]; then
    if common::is_truthy "${LOCAL_SETUP_CREATE_SELF_SIGNED_CERT}"; then
      CREATE_SELF_SIGNED_CERT="true"
      common::log "Self-signed certificate creation enabled via LOCAL_SETUP_CREATE_SELF_SIGNED_CERT."
    else
      CREATE_SELF_SIGNED_CERT="false"
      common::log "Self-signed certificate creation disabled via LOCAL_SETUP_CREATE_SELF_SIGNED_CERT."
    fi
    return
  fi

  if [ ! -t 0 ]; then
    CREATE_SELF_SIGNED_CERT="false"
    common::log "No interactive terminal detected; skipping self-signed certificate creation."
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

nginx::create_self_signed_cert() {
  local cert_dir=""
  local san_entries="DNS:localhost,IP:127.0.0.1"
  local host_name=""

  if [ "$CREATE_SELF_SIGNED_CERT" != "true" ]; then
    return
  fi

  if [ -z "$NGINX_SSL_CERT_PATH" ] || [ -z "$NGINX_SSL_KEY_PATH" ]; then
    echo "Cannot create self-signed cert: NGINX SSL paths are not initialized." >&2
    exit 1
  fi

  if ! command -v openssl >/dev/null 2>&1; then
    common::log "Installing OpenSSL for self-signed certificate generation"
    common::run_as_root apt-get update
    common::run_as_root apt-get install -y openssl
  fi

  cert_dir="$(dirname "$NGINX_SSL_CERT_PATH")"
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
    common::log "Reusing existing TLS certificate and key at $cert_dir"
    return
  fi

  common::log "Creating self-signed TLS certificate for $NGINX_PRIMARY_SERVER_NAME at $cert_dir"
  common::run_as_root mkdir -p "$cert_dir"
  common::run_as_root openssl req \
    -x509 \
    -nodes \
    -newkey rsa:2048 \
    -days "${LOCAL_SETUP_SELF_SIGNED_CERT_DAYS:-825}" \
    -keyout "$NGINX_SSL_KEY_PATH" \
    -out "$NGINX_SSL_CERT_PATH" \
    -subj "/CN=$NGINX_PRIMARY_SERVER_NAME" \
    -addext "subjectAltName=$san_entries"
  common::run_as_root chmod 600 "$NGINX_SSL_KEY_PATH"
  common::run_as_root chmod 644 "$NGINX_SSL_CERT_PATH"
}

nginx::sync_static_assets() {
  local collected_static_root="$ROOT_DIR/staticfiles"

  if [ ! -d "$collected_static_root" ]; then
    echo "Collected static directory not found at $collected_static_root." >&2
    echo "Run collectstatic before syncing NGINX static assets." >&2
    exit 1
  fi

  common::log "Syncing static assets to $NGINX_STATIC_ROOT"
  common::run_as_root mkdir -p "$NGINX_STATIC_ROOT"
  if command -v rsync >/dev/null 2>&1; then
    common::run_as_root rsync -a --delete "$collected_static_root"/ "$NGINX_STATIC_ROOT"/
  else
    common::run_as_root cp -a "$collected_static_root"/. "$NGINX_STATIC_ROOT"/
  fi

  common::run_as_root find "$NGINX_STATIC_ROOT" -type d -exec chmod 755 {} \;
  common::run_as_root find "$NGINX_STATIC_ROOT" -type f -exec chmod 644 {} \;
}

nginx::start_service() {
  if ! command -v nginx >/dev/null 2>&1; then
    return
  fi

  if command -v systemctl >/dev/null 2>&1 && [ -d /run/systemd/system ]; then
    if ! common::run_as_root nginx -t >/dev/null 2>&1; then
      common::log "Skipping NGINX service enable/start because nginx -t failed."
      common::log "Review /etc/nginx/sites-available/complianceapp.conf to fix configuration issues."
      return
    fi

    common::run_as_root systemctl enable nginx || common::run_as_root systemctl enable nginx.service
    common::run_as_root systemctl restart nginx || common::run_as_root systemctl start nginx
    if ! common::run_as_root systemctl is-active --quiet nginx; then
      echo "NGINX service failed to start." >&2
      echo "Inspect with: sudo journalctl -u nginx --no-pager -n 100" >&2
      exit 1
    fi
  fi
}
