#!/usr/bin/env bash

if [ -n "${LOCAL_SETUP_PLATFORM_SH_LOADED:-}" ]; then
  return 0
fi
LOCAL_SETUP_PLATFORM_SH_LOADED=1

platform::ensure_supported_platform() {
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

platform::ensure_python_runtime() {
  if command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    return
  fi

  common::log "Installing Python runtime and Python 3.12 venv support with apt-get"
  common::run_as_root apt-get update
  common::run_as_root apt-get install -y python3 python3-pip python3.12-venv

  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="python3"
    else
      echo "Python installation completed but no usable python executable was found." >&2
      exit 1
    fi
  fi
}

platform::ensure_python_venv() {
  if "$PYTHON_BIN" -c "import venv, ensurepip" >/dev/null 2>&1; then
    return
  fi

  common::log "Installing python3.12-venv for virtual environment support"
  common::run_as_root apt-get update
  common::run_as_root apt-get install -y python3.12-venv

  if ! "$PYTHON_BIN" -c "import venv, ensurepip" >/dev/null 2>&1; then
    echo "Python virtual environment support is still unavailable after installing python3.12-venv." >&2
    echo "Ensure PYTHON_BIN points to the system Python interpreter and rerun." >&2
    exit 1
  fi
}

platform::install_nginx() {
  if command -v nginx >/dev/null 2>&1; then
    return
  fi

  common::log "Installing NGINX with apt-get"
  common::run_as_root apt-get update
  common::run_as_root apt-get install -y nginx

  if ! command -v nginx >/dev/null 2>&1; then
    echo "NGINX installation did not provide the nginx command." >&2
    exit 1
  fi
}

platform::install_powershell() {
  local version_id=""
  local package_dir=""
  local package_path=""

  if command -v pwsh >/dev/null 2>&1; then
    return
  fi

  # shellcheck disable=SC1091
  source /etc/os-release
  version_id="${VERSION_ID:-}"
  if [ -z "$version_id" ]; then
    echo "Unable to determine Ubuntu VERSION_ID for PowerShell installation." >&2
    exit 1
  fi

  common::log "Installing PowerShell 7 from the Microsoft package repository"
  common::run_as_root apt-get update
  common::run_as_root apt-get install -y wget apt-transport-https software-properties-common

  if ! dpkg -s packages-microsoft-prod >/dev/null 2>&1; then
    package_dir="$(mktemp -d)"
    package_path="$package_dir/packages-microsoft-prod.deb"
    wget -q "https://packages.microsoft.com/config/ubuntu/$version_id/packages-microsoft-prod.deb" -O "$package_path"
    common::run_as_root dpkg -i "$package_path"
    rm -rf "$package_dir"
  fi

  common::run_as_root apt-get update
  common::run_as_root apt-get install -y powershell

  if ! command -v pwsh >/dev/null 2>&1; then
    echo "PowerShell installation completed but the pwsh command was not found." >&2
    exit 1
  fi
}

platform::ensure_rsync_installed() {
  if command -v rsync >/dev/null 2>&1; then
    return
  fi

  common::log "Installing rsync"
  common::run_as_root apt-get update
  common::run_as_root apt-get install -y rsync

  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is unavailable after attempted install." >&2
    echo "Install rsync and rerun setup." >&2
    exit 1
  fi
}
