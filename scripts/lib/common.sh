#!/usr/bin/env bash

if [ -n "${LOCAL_SETUP_COMMON_SH_LOADED:-}" ]; then
  return 0
fi
LOCAL_SETUP_COMMON_SH_LOADED=1

common::log() {
  echo "[local_setup] $*"
}

common::run_as_root() {
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

common::is_truthy() {
  case "${1,,}" in
    1|true|yes|on)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

common::generate_random_secret() {
  "$PYTHON_BIN" - <<'PY'
import secrets

print(secrets.token_urlsafe(48))
PY
}

common::ensure_local_env_file_permissions() {
  if [ ! -e "$ENV_FILE" ]; then
    return
  fi

  if chmod 0600 "$ENV_FILE" 2>/dev/null; then
    return
  fi

  common::run_as_root chmod 0600 "$ENV_FILE"
}

common::ensure_assessment_pfx_password_source_file() {
  local credential_dir="$1"
  local managed_name="$2"
  local credential_file="$credential_dir/${managed_name}-${ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME}"
  local tmp_secret=""

  if [ -f "$credential_file" ]; then
    ASSESSMENT_PFX_PASSWORD_SOURCE_FILE="$credential_file"
    return
  fi

  tmp_secret="$(mktemp)"
  common::generate_random_secret > "$tmp_secret"
  common::run_as_root install -m 0600 -o root -g root "$tmp_secret" "$credential_file"
  rm -f "$tmp_secret"
  ASSESSMENT_PFX_PASSWORD_SOURCE_FILE="$credential_file"
}

common::merge_host_values() {
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

common::read_env_var() {
  local key="$1"

  "$PYTHON_BIN" - "$ENV_FILE" "$key" <<'PY'
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
        value = decode_env_value(parsed_value)

print(value, end="")
PY
}

common::upsert_env_var() {
  local key="$1"
  local value="$2"

  "$PYTHON_BIN" - "$ENV_FILE" "$key" "$value" <<'PY'
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

  common::ensure_local_env_file_permissions
}
