#!/usr/bin/env bash

if [ -n "${LOCAL_SETUP_ASSESSMENT_SH_LOADED:-}" ]; then
  return 0
fi
LOCAL_SETUP_ASSESSMENT_SH_LOADED=1

assessment::render_worker_service() {
  local target_path="$1"
  local service_name="$2"
  local runtime_user="$3"
  local runtime_group="$4"
  local runtime_app_dir="$5"
  local env_file="$6"
  local runtime_venv_dir="$7"
  local credential_name="$8"
  local credential_source_file="$9"

  cat > "$target_path" <<EOF
[Unit]
Description=$service_name Zero Trust assessment worker
After=network.target

[Service]
Type=simple
User=$runtime_user
Group=$runtime_group
WorkingDirectory=$runtime_app_dir
EnvironmentFile=$env_file
LoadCredential=$credential_name:$credential_source_file
ExecStart=$runtime_venv_dir/bin/python manage.py run_assessment_worker
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
}

assessment::install_pinned_modules() {
  local runtime_user="$1"
  local assessment_module_version="$2"
  local assessment_module_sha256="$3"
  local module_bootstrap_script=""

  platform::install_powershell
  if ! command -v runuser >/dev/null 2>&1; then
    echo "runuser is required to bootstrap the Zero Trust assessment PowerShell module." >&2
    exit 1
  fi

  module_bootstrap_script="$(mktemp)"
  cat > "$module_bootstrap_script" <<'EOF'
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$packages = @(
  @{
    Name = 'PSFramework'
    Version = $env:PSFRAMEWORK_MODULE_VERSION
    ExpectedSha256 = $env:PSFRAMEWORK_MODULE_SHA256
  },
  @{
    Name = 'ZeroTrustAssessment'
    Version = $env:ASSESSMENT_MODULE_VERSION
    ExpectedSha256 = $env:ASSESSMENT_MODULE_SHA256
  }
)

$userModuleRoot = ($env:PSModulePath -split [System.IO.Path]::PathSeparator | Where-Object {
  $_ -and $_.StartsWith($HOME, [System.StringComparison]::OrdinalIgnoreCase) -and $_ -like '*powershell*Modules*'
} | Select-Object -First 1)
if (-not $userModuleRoot) {
  $userModuleRoot = Join-Path $HOME '.local/share/powershell/Modules'
}

$tempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('zta-module-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

try {
  foreach ($package in $packages) {
    if ([string]::IsNullOrWhiteSpace($package.Version)) {
      throw ('Missing module version for ' + $package.Name + '.')
    }
    if ([string]::IsNullOrWhiteSpace($package.ExpectedSha256)) {
      throw ('Missing SHA-256 pin for ' + $package.Name + '.')
    }

    $downloadUri = 'https://www.powershellgallery.com/api/v2/package/{0}/{1}' -f $package.Name, $package.Version
    $downloadPath = Join-Path $tempRoot ('{0}.{1}.nupkg' -f $package.Name, $package.Version)
    $expandedPath = Join-Path $tempRoot ('{0}.{1}' -f $package.Name, $package.Version)

    Invoke-WebRequest -Uri $downloadUri -OutFile $downloadPath

    $actualSha256 = (Get-FileHash -LiteralPath $downloadPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualSha256 -ne $package.ExpectedSha256.ToLowerInvariant()) {
      throw ('SHA-256 mismatch for ' + $package.Name + ' ' + $package.Version + '. Expected ' + $package.ExpectedSha256 + ' but downloaded ' + $actualSha256 + '.')
    }

    [System.IO.Compression.ZipFile]::ExtractToDirectory($downloadPath, $expandedPath)
    $manifest = Get-ChildItem -LiteralPath $expandedPath -Filter ($package.Name + '.psd1') -File -Recurse | Where-Object {
      $_.FullName -notmatch '[\\/](package|_rels)[\\/]'
    } | Select-Object -First 1
    if (-not $manifest) {
      throw ('Unable to locate the module manifest for ' + $package.Name + ' ' + $package.Version + '.')
    }

    $targetRoot = Join-Path (Join-Path $userModuleRoot $package.Name) $package.Version
    New-Item -ItemType Directory -Path (Split-Path -Parent $targetRoot) -Force | Out-Null
    if (Test-Path -LiteralPath $targetRoot) {
      Remove-Item -LiteralPath $targetRoot -Recurse -Force
    }
    New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
    Get-ChildItem -LiteralPath $manifest.Directory.FullName -Force | ForEach-Object {
      Copy-Item -LiteralPath $_.FullName -Destination $targetRoot -Recurse -Force
    }

    Import-Module $package.Name -RequiredVersion $package.Version -Force
  }
}
finally {
  if (Test-Path -LiteralPath $tempRoot) {
    Remove-Item -LiteralPath $tempRoot -Recurse -Force
  }
}
EOF
  chmod 0644 "$module_bootstrap_script"
  common::log "Installing pinned PowerShell assessment modules for $runtime_user"
  if ! common::run_as_root env \
    PSFRAMEWORK_MODULE_VERSION="$DEFAULT_PSFRAMEWORK_MODULE_VERSION" \
    PSFRAMEWORK_MODULE_SHA256="$DEFAULT_PSFRAMEWORK_MODULE_SHA256" \
    ASSESSMENT_MODULE_VERSION="$assessment_module_version" \
    ASSESSMENT_MODULE_SHA256="$assessment_module_sha256" \
    runuser -u "$runtime_user" -- pwsh -NoLogo -NoProfile -NonInteractive -File "$module_bootstrap_script"
  then
    rm -f "$module_bootstrap_script"
    echo "Unable to install the pinned PowerShell assessment modules for $runtime_user." >&2
    echo "Verify that pwsh is installed, the server can reach PSGallery, and the configured module SHA pins are correct, then rerun scripts/local_setup.sh." >&2
    exit 1
  fi
  rm -f "$module_bootstrap_script"
}

assessment::setup_worker_service() {
  local service_name="${LOCAL_SETUP_ASSESSMENT_WORKER_SERVICE_NAME:-$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')-assessment-worker}"
  local service_unit=""
  local service_path=""
  local assessment_storage_root=""
  local assessment_certificate_root=""
  local assessment_staging_root=""
  local assessment_module_version=""
  local assessment_module_sha256=""
  local tmp_file=""
  local tmp_env=""

  if ! command -v systemctl >/dev/null 2>&1 || [ ! -d /run/systemd/system ]; then
    common::log "Skipping assessment worker systemd service setup because systemd is unavailable."
    return
  fi

  if [ -z "$GUNICORN_RUNTIME_USER" ] || [ -z "$GUNICORN_RUNTIME_GROUP" ] || [ -z "$GUNICORN_ENV_FILE" ] || [ -z "$GUNICORN_RUNTIME_APP_DIR" ] || [ -z "$GUNICORN_RUNTIME_VENV_DIR" ]; then
    common::log "Skipping assessment worker setup because the Gunicorn runtime context is incomplete."
    return
  fi

  if [ -z "$ASSESSMENT_PFX_PASSWORD_SOURCE_FILE" ]; then
    common::ensure_assessment_pfx_password_source_file "$(dirname "$GUNICORN_ENV_FILE")" "$(basename "$ROOT_DIR" | tr '[:upper:]' '[:lower:]')"
  fi

  if [[ ! "$service_name" =~ ^[A-Za-z0-9_.@-]+$ ]]; then
    echo "Invalid assessment worker service name '$service_name'." >&2
    exit 1
  fi

  assessment_storage_root="${LOCAL_SETUP_ASSESSMENT_STORAGE_ROOT:-/var/lib/$GUNICORN_RUNTIME_USER/assessments}"
  assessment_certificate_root="${LOCAL_SETUP_ASSESSMENT_CERTIFICATE_ROOT:-$assessment_storage_root/certificates}"
  assessment_staging_root="${LOCAL_SETUP_ASSESSMENT_STAGING_ROOT:-$assessment_storage_root/staging}"
  assessment_module_version="${LOCAL_SETUP_ASSESSMENT_MODULE_VERSION:-$(common::read_env_var ASSESSMENT_MODULE_VERSION)}"
  assessment_module_sha256="${LOCAL_SETUP_ASSESSMENT_MODULE_SHA256:-$(common::read_env_var ASSESSMENT_MODULE_SHA256)}"

  if [ -z "$assessment_module_version" ]; then
    assessment_module_version="$DEFAULT_ASSESSMENT_MODULE_VERSION"
  fi
  if [ -z "$assessment_module_sha256" ]; then
    assessment_module_sha256="$DEFAULT_ASSESSMENT_MODULE_SHA256"
  fi
  assessment_module_sha256="${assessment_module_sha256,,}"

  if [[ ! "$assessment_module_sha256" =~ ^[0-9a-f]{64}$ ]]; then
    echo "ASSESSMENT_MODULE_SHA256 must be a 64-character lowercase SHA-256 hex string." >&2
    exit 1
  fi

  common::run_as_root install -d -m 0700 -o "$GUNICORN_RUNTIME_USER" -g "$GUNICORN_RUNTIME_GROUP" \
    "$assessment_storage_root" "$assessment_certificate_root" "$assessment_staging_root"

  tmp_env="$(mktemp)"
  cp "$GUNICORN_ENV_FILE" "$tmp_env"
  "$PYTHON_BIN" - "$tmp_env" "$assessment_storage_root" "$assessment_certificate_root" "$assessment_staging_root" "$assessment_module_version" "$assessment_module_sha256" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
storage_root = sys.argv[2]
certificate_root = sys.argv[3]
staging_root = sys.argv[4]
module_version = sys.argv[5]
module_sha256 = sys.argv[6]

desired = {
    "ASSESSMENT_STORAGE_ROOT": storage_root,
    "ASSESSMENT_CERTIFICATE_ROOT": certificate_root,
    "ASSESSMENT_STAGING_ROOT": staging_root,
    "ASSESSMENT_MODULE_VERSION": module_version,
    "ASSESSMENT_MODULE_SHA256": module_sha256,
}

lines = env_path.read_text(encoding="utf-8").splitlines()
updated = []
seen = set()
for line in lines:
    stripped = line.strip()
    if "=" not in stripped or stripped.startswith("#"):
        updated.append(line)
        continue
    key = stripped.split("=", 1)[0].strip()
    if key in desired:
        updated.append(f"{key}={desired[key]}")
        seen.add(key)
    else:
        updated.append(line)

for key, value in desired.items():
    if key not in seen:
        updated.append(f"{key}={value}")

env_path.write_text("\n".join(updated) + "\n", encoding="utf-8")
PY
  common::run_as_root install -m 0640 -o root -g "$GUNICORN_RUNTIME_GROUP" "$tmp_env" "$GUNICORN_ENV_FILE"
  rm -f "$tmp_env"

  if [ -n "$GUNICORN_SERVICE_UNITS" ]; then
    for service_unit in $GUNICORN_SERVICE_UNITS; do
      common::log "Restarting $service_unit to pick up assessment storage environment changes"
      common::run_as_root systemctl restart "$service_unit"
      if ! common::run_as_root systemctl is-active --quiet "$service_unit"; then
        echo "Gunicorn service failed to restart after updating assessment storage env: $service_unit" >&2
        echo "Inspect with: sudo journalctl -u $service_unit --no-pager -n 100" >&2
        exit 1
      fi
    done
  fi

  assessment::install_pinned_modules "$GUNICORN_RUNTIME_USER" "$assessment_module_version" "$assessment_module_sha256"

  service_unit="${service_name}.service"
  service_path="/etc/systemd/system/$service_unit"
  tmp_file="$(mktemp)"
  assessment::render_worker_service \
    "$tmp_file" \
    "$service_name" \
    "$GUNICORN_RUNTIME_USER" \
    "$GUNICORN_RUNTIME_GROUP" \
    "$GUNICORN_RUNTIME_APP_DIR" \
    "$GUNICORN_ENV_FILE" \
    "$GUNICORN_RUNTIME_VENV_DIR" \
    "$ASSESSMENT_PFX_PASSWORD_CREDENTIAL_NAME" \
    "$ASSESSMENT_PFX_PASSWORD_SOURCE_FILE"

  common::log "Installing assessment worker systemd service at $service_path"
  common::run_as_root install -m 0644 "$tmp_file" "$service_path"
  rm -f "$tmp_file"

  common::run_as_root systemctl daemon-reload
  common::run_as_root systemctl enable "$service_unit"
  common::run_as_root systemctl restart "$service_unit" || common::run_as_root systemctl start "$service_unit"
  if ! common::run_as_root systemctl is-active --quiet "$service_unit"; then
    echo "Assessment worker service failed to start: $service_unit" >&2
    echo "Inspect with: sudo journalctl -u $service_unit --no-pager -n 100" >&2
    exit 1
  fi

  ASSESSMENT_WORKER_SERVICE_UNIT="$service_unit"
}
