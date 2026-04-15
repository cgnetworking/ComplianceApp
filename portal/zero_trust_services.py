from __future__ import annotations

import os
import platform
import pwd
import re
import shutil
import subprocess
import threading
import uuid
from datetime import timedelta, timezone as dt_timezone
from pathlib import Path

from django.db import transaction
from django.utils import timezone

from .models import PortalState

ZERO_TRUST_RUNTIME_SERVICE_USER = "complianceapp"


def _resolve_runtime_service_home() -> Path:
    try:
        runtime_user = pwd.getpwnam(ZERO_TRUST_RUNTIME_SERVICE_USER)
    except KeyError:
        return Path.home().resolve()

    home_directory = runtime_user.pw_dir.strip() if runtime_user.pw_dir else ""
    if not home_directory:
        return Path.home().resolve()
    return Path(home_directory).expanduser().resolve()


ZERO_TRUST_STATE_KEY = "zero_trust_assessment_state"
ZERO_TRUST_RUN_INTERVAL_DAYS = 7
ZERO_TRUST_HISTORY_LIMIT = 20
ZERO_TRUST_REPORT_FILENAME = "ZeroTrustAssessmentReport.html"
ZERO_TRUST_LOG_FILENAME = "assessment.log"
ZERO_TRUST_RUNS_ROOT = (_resolve_runtime_service_home() / ".local" / "share" / "isms-zero-trust").resolve()
ZERO_TRUST_CERTIFICATES_ROOT = (ZERO_TRUST_RUNS_ROOT / "certificates").resolve()
ZERO_TRUST_PUBLIC_CERTIFICATE_FILENAME = "ZeroTrustAssessmentPublicKey.cer"
ZERO_TRUST_CERTIFICATE_VALID_DAYS = 825

ZERO_TRUST_DOC_URL = "https://learn.microsoft.com/en-us/security/zero-trust/assessment/get-started"
POWERSHELL_INSTALL_DOC_URL = (
    "https://learn.microsoft.com/en-us/powershell/scripting/install/install-ubuntu?view=powershell-7.6"
)
GRAPH_APP_ONLY_DOC_URL = "https://learn.microsoft.com/en-us/powershell/microsoftgraph/app-only?view=graph-powershell-1.0"
ZERO_TRUST_REQUIRED_GRAPH_PERMISSIONS = [
    "AuditLog.Read.All",
    "CrossTenantInformation.ReadBasic.All",
    "DeviceManagementApps.Read.All",
    "DeviceManagementConfiguration.Read.All",
    "DeviceManagementManagedDevices.Read.All",
    "DeviceManagementRBAC.Read.All",
    "DeviceManagementServiceConfig.Read.All",
    "Directory.Read.All",
    "DirectoryRecommendations.Read.All",
    "EntitlementManagement.Read.All",
    "IdentityRiskEvent.Read.All",
    "IdentityRiskyUser.Read.All",
    "IdentityRiskyServicePrincipal.Read.All",
    "NetworkAccess.Read.All",
    "Policy.Read.All",
    "Policy.Read.ConditionalAccess",
    "Policy.Read.PermissionGrant",
    "PrivilegedAccess.Read.AzureAD",
    "Reports.Read.All",
    "RoleManagement.Read.All",
    "UserAuthenticationMethod.Read.All",
]


def _normalize_string(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    normalized = str(value).strip()
    return normalized if normalized else fallback


def _normalize_bool(value: object, fallback: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return fallback
    if isinstance(value, (int, float)):
        return bool(value)
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return fallback


def _normalize_int(value: object, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _parse_iso_datetime(value: object) -> timezone.datetime | None:
    if not isinstance(value, str):
        return None

    raw_value = value.strip().replace("Z", "+00:00")
    if not raw_value:
        return None

    try:
        parsed = timezone.datetime.fromisoformat(raw_value)
    except ValueError:
        return None

    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, dt_timezone.utc)
    return parsed


def _current_system_username() -> str:
    try:
        return pwd.getpwuid(os.geteuid()).pw_name
    except KeyError:
        return str(os.geteuid())


def _runtime_service_requirement_error() -> str:
    try:
        pwd.getpwnam(ZERO_TRUST_RUNTIME_SERVICE_USER)
    except KeyError:
        return (
            f"Runtime service account `{ZERO_TRUST_RUNTIME_SERVICE_USER}` was not found. "
            "Create this user and run all services under it."
        )

    current_user = _current_system_username()
    if current_user != ZERO_TRUST_RUNTIME_SERVICE_USER:
        return (
            f"This process is running as `{current_user}`. "
            f"All runtime services must run as `{ZERO_TRUST_RUNTIME_SERVICE_USER}`."
        )

    return ""


def _require_runtime_service_owner() -> None:
    requirement_error = _runtime_service_requirement_error()
    if requirement_error:
        raise ValueError(requirement_error)


def _default_generated_certificate() -> dict[str, object]:
    return {
        "available": False,
        "subject": "",
        "thumbprint": "",
        "publicKeyPath": "",
        "generatedAt": "",
        "expiresAt": "",
        "downloadName": ZERO_TRUST_PUBLIC_CERTIFICATE_FILENAME,
    }


def _normalize_generated_certificate(value: object) -> dict[str, object]:
    defaults = _default_generated_certificate()
    if not isinstance(value, dict):
        return defaults

    public_key_path = _normalize_string(value.get("publicKeyPath"))
    if public_key_path:
        try:
            resolved_path = Path(public_key_path).expanduser().resolve()
        except OSError:
            public_key_path = ""
        else:
            if _is_path_within_root(resolved_path, ZERO_TRUST_CERTIFICATES_ROOT) and resolved_path.exists() and resolved_path.is_file():
                public_key_path = str(resolved_path)
            else:
                public_key_path = ""

    available = _normalize_bool(value.get("available"), False) and bool(public_key_path)

    return {
        "available": available,
        "subject": _normalize_string(value.get("subject")),
        "thumbprint": _normalize_string(value.get("thumbprint")).upper(),
        "publicKeyPath": public_key_path,
        "generatedAt": _normalize_string(value.get("generatedAt")),
        "expiresAt": _normalize_string(value.get("expiresAt")),
        "downloadName": _normalize_string(value.get("downloadName"), ZERO_TRUST_PUBLIC_CERTIFICATE_FILENAME),
    }


def _default_authentication_config() -> dict[str, object]:
    return {
        "mode": "app_only",
        "useDeviceCode": False,
        "appOnly": {
            "tenantId": "",
            "clientId": "",
            "certificateReference": "",
            "generatedCertificate": _default_generated_certificate(),
        },
    }


def _normalize_authentication_config(value: object) -> dict[str, object]:
    defaults = _default_authentication_config()
    if not isinstance(value, dict):
        return defaults

    app_only_payload = value.get("appOnly") if isinstance(value.get("appOnly"), dict) else {}
    generated_certificate_payload = (
        app_only_payload.get("generatedCertificate")
        if isinstance(app_only_payload.get("generatedCertificate"), dict)
        else {}
    )

    return {
        "mode": "app_only",
        "useDeviceCode": False,
        "appOnly": {
            "tenantId": _normalize_string(app_only_payload.get("tenantId")),
            "clientId": _normalize_string(app_only_payload.get("clientId")),
            "certificateReference": _normalize_string(app_only_payload.get("certificateReference")),
            "generatedCertificate": _normalize_generated_certificate(generated_certificate_payload),
        },
    }


def _validate_guid(value: str, label: str) -> str:
    normalized = _normalize_string(value)
    if not normalized:
        raise ValueError(f"{label} is required.")
    if not re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        normalized,
    ):
        raise ValueError(f"{label} must be a valid GUID.")
    return normalized


def _validate_authentication_config(value: object) -> dict[str, object]:
    normalized = _normalize_authentication_config(value)
    app_only = normalized["appOnly"]
    app_only["tenantId"] = _validate_guid(str(app_only.get("tenantId") or ""), "Tenant ID")
    app_only["clientId"] = _validate_guid(str(app_only.get("clientId") or ""), "Client ID")

    certificate_reference = _normalize_string(app_only.get("certificateReference"))
    if not certificate_reference:
        raise ValueError("Certificate reference is required for certificate authentication.")
    app_only["certificateReference"] = certificate_reference
    return normalized


def _authentication_readiness(authentication: dict[str, object]) -> dict[str, object]:
    app_only = authentication.get("appOnly") if isinstance(authentication.get("appOnly"), dict) else {}
    missing_fields: list[str] = []
    if not _normalize_string(app_only.get("tenantId")):
        missing_fields.append("tenant ID")
    if not _normalize_string(app_only.get("clientId")):
        missing_fields.append("client ID")
    if not _normalize_string(app_only.get("certificateReference")):
        missing_fields.append("certificate reference")

    if missing_fields:
        return {
            "ready": False,
            "message": f"Certificate authentication is missing: {', '.join(missing_fields)}.",
        }

    return {
        "ready": True,
        "message": "Certificate authentication is configured.",
    }


def _state_default() -> dict[str, object]:
    return {
        "authentication": _default_authentication_config(),
        "run": {
            "status": "not_started",
            "message": "Run the assessment to generate your first report.",
            "runId": "",
            "trigger": "",
            "startedAt": "",
            "finishedAt": "",
            "runDirectory": "",
            "logPath": "",
        },
        "schedule": {
            "intervalDays": ZERO_TRUST_RUN_INTERVAL_DAYS,
            "autoRunEnabled": True,
            "firstRunAt": "",
            "lastRunAt": "",
            "lastSuccessfulRunAt": "",
            "nextRunAt": "",
        },
        "latestResult": {
            "runId": "",
            "status": "",
            "message": "",
            "reportPath": "",
            "reportSizeBytes": 0,
            "reportGeneratedAt": "",
            "logPath": "",
            "returnCode": None,
            "summary": {},
        },
        "history": [],
    }


def _normalize_history_entry(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None

    return {
        "runId": _normalize_string(value.get("runId")),
        "status": _normalize_string(value.get("status"), "failed"),
        "message": _normalize_string(value.get("message")),
        "trigger": _normalize_string(value.get("trigger")),
        "startedAt": _normalize_string(value.get("startedAt")),
        "finishedAt": _normalize_string(value.get("finishedAt")),
        "runDirectory": _normalize_string(value.get("runDirectory")),
        "reportPath": _normalize_string(value.get("reportPath")),
        "reportSizeBytes": _normalize_int(value.get("reportSizeBytes"), 0),
        "reportGeneratedAt": _normalize_string(value.get("reportGeneratedAt")),
        "logPath": _normalize_string(value.get("logPath")),
        "returnCode": value.get("returnCode") if isinstance(value.get("returnCode"), int) else None,
        "summary": value.get("summary") if isinstance(value.get("summary"), dict) else {},
    }


def normalize_zero_trust_state(payload: object) -> dict[str, object]:
    defaults = _state_default()
    if not isinstance(payload, dict):
        return defaults

    run_payload = payload.get("run") if isinstance(payload.get("run"), dict) else {}
    schedule_payload = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
    latest_result_payload = payload.get("latestResult") if isinstance(payload.get("latestResult"), dict) else {}
    authentication_payload = _normalize_authentication_config(payload.get("authentication"))

    interval_days = max(1, _normalize_int(schedule_payload.get("intervalDays"), ZERO_TRUST_RUN_INTERVAL_DAYS))

    history: list[dict[str, object]] = []
    if isinstance(payload.get("history"), list):
        for item in payload.get("history", []):
            normalized = _normalize_history_entry(item)
            if normalized is not None:
                history.append(normalized)

    return {
        "authentication": authentication_payload,
        "run": {
            "status": _normalize_string(run_payload.get("status"), "not_started"),
            "message": _normalize_string(
                run_payload.get("message"),
                "Run the assessment to generate your first report.",
            ),
            "runId": _normalize_string(run_payload.get("runId")),
            "trigger": _normalize_string(run_payload.get("trigger")),
            "startedAt": _normalize_string(run_payload.get("startedAt")),
            "finishedAt": _normalize_string(run_payload.get("finishedAt")),
            "runDirectory": _normalize_string(run_payload.get("runDirectory")),
            "logPath": _normalize_string(run_payload.get("logPath")),
        },
        "schedule": {
            "intervalDays": interval_days,
            "autoRunEnabled": _normalize_bool(schedule_payload.get("autoRunEnabled"), True),
            "firstRunAt": _normalize_string(schedule_payload.get("firstRunAt")),
            "lastRunAt": _normalize_string(schedule_payload.get("lastRunAt")),
            "lastSuccessfulRunAt": _normalize_string(schedule_payload.get("lastSuccessfulRunAt")),
            "nextRunAt": _normalize_string(schedule_payload.get("nextRunAt")),
        },
        "latestResult": {
            "runId": _normalize_string(latest_result_payload.get("runId")),
            "status": _normalize_string(latest_result_payload.get("status")),
            "message": _normalize_string(latest_result_payload.get("message")),
            "reportPath": _normalize_string(latest_result_payload.get("reportPath")),
            "reportSizeBytes": _normalize_int(latest_result_payload.get("reportSizeBytes"), 0),
            "reportGeneratedAt": _normalize_string(latest_result_payload.get("reportGeneratedAt")),
            "logPath": _normalize_string(latest_result_payload.get("logPath")),
            "returnCode": latest_result_payload.get("returnCode")
            if isinstance(latest_result_payload.get("returnCode"), int)
            else None,
            "summary": latest_result_payload.get("summary") if isinstance(latest_result_payload.get("summary"), dict) else {},
        },
        "history": history[:ZERO_TRUST_HISTORY_LIMIT],
    }


def _read_zero_trust_state() -> dict[str, object]:
    try:
        record = PortalState.objects.get(key=ZERO_TRUST_STATE_KEY)
    except PortalState.DoesNotExist:
        return _state_default()

    return normalize_zero_trust_state(record.payload)


def _read_os_release() -> dict[str, str]:
    os_release_path = Path("/etc/os-release")
    if not os_release_path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in os_release_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        normalized_key = key.strip()
        normalized_value = value.strip().strip('"').strip("'")
        if normalized_key:
            values[normalized_key] = normalized_value

    return values


def detect_linux_platform() -> dict[str, object]:
    system_name = platform.system().strip() or "Unknown"
    platform_payload: dict[str, object] = {
        "supported": False,
        "system": system_name,
        "distribution": "",
        "version": "",
        "reason": "",
    }

    if system_name.lower() != "linux":
        platform_payload["reason"] = "This feature supports Ubuntu only."
        return platform_payload

    os_release = _read_os_release()
    distro_id = os_release.get("ID", "").strip().lower()
    distro_name = os_release.get("PRETTY_NAME") or os_release.get("NAME") or "Linux"
    distro_version = os_release.get("VERSION_ID", "")
    platform_payload["distribution"] = distro_name
    platform_payload["version"] = distro_version

    if distro_id != "ubuntu":
        platform_payload["reason"] = "This feature supports Ubuntu only."
        return platform_payload

    platform_payload["supported"] = True
    return platform_payload


def _run_capture(command: list[str], timeout_seconds: int = 20) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
        )
    except (FileNotFoundError, subprocess.SubprocessError):
        return 127, "", ""

    return completed.returncode, completed.stdout.strip(), completed.stderr.strip()


def detect_zero_trust_prerequisites(platform_payload: dict[str, object] | None = None) -> dict[str, object]:
    platform_info = platform_payload if isinstance(platform_payload, dict) else detect_linux_platform()

    prerequisites = {
        "powerShell": {
            "installed": False,
            "version": "",
        },
        "zeroTrustModule": {
            "installed": False,
            "version": "",
        },
    }

    if not platform_info.get("supported"):
        return prerequisites

    if not shutil.which("pwsh"):
        return prerequisites

    version_code, version_stdout, _ = _run_capture(
        ["pwsh", "-NoLogo", "-NoProfile", "-Command", "$PSVersionTable.PSVersion.ToString()"],
    )
    if version_code == 0 and version_stdout:
        prerequisites["powerShell"]["installed"] = True
        prerequisites["powerShell"]["version"] = version_stdout

    module_command = (
        "$module = Get-Module -ListAvailable ZeroTrustAssessment "
        "| Sort-Object Version -Descending "
        "| Select-Object -First 1; "
        "if ($null -eq $module) { '' } else { $module.Version.ToString() }"
    )
    module_code, module_stdout, _ = _run_capture(
        ["pwsh", "-NoLogo", "-NoProfile", "-Command", module_command],
    )
    if module_code == 0 and module_stdout:
        prerequisites["zeroTrustModule"]["installed"] = True
        prerequisites["zeroTrustModule"]["version"] = module_stdout

    return prerequisites


def _prerequisite_readiness(prerequisites: dict[str, object]) -> dict[str, object]:
    power_shell = prerequisites.get("powerShell") if isinstance(prerequisites.get("powerShell"), dict) else {}
    zero_trust_module = (
        prerequisites.get("zeroTrustModule")
        if isinstance(prerequisites.get("zeroTrustModule"), dict)
        else {}
    )

    missing_items: list[str] = []
    if not _normalize_bool(power_shell.get("installed"), False):
        missing_items.append("PowerShell 7")
    if not _normalize_bool(zero_trust_module.get("installed"), False):
        missing_items.append("ZeroTrustAssessment module")

    if missing_items:
        return {
            "ready": False,
            "message": (
                "Ubuntu prerequisites are incomplete. "
                f"Run `scripts/local_setup.sh` to install: {', '.join(missing_items)}."
            ),
        }

    return {
        "ready": True,
        "message": "Ubuntu prerequisites are installed.",
    }


def _is_path_within_root(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _prepare_run_context(
    state: dict[str, object],
    *,
    trigger: str,
    started_at: timezone.datetime,
) -> dict[str, object]:
    run_id = f"zt-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    run_directory = (ZERO_TRUST_RUNS_ROOT / run_id).resolve()
    run_directory.mkdir(parents=True, exist_ok=True)
    log_path = run_directory / ZERO_TRUST_LOG_FILENAME

    schedule = state["schedule"]
    interval_days = max(1, int(schedule.get("intervalDays") or ZERO_TRUST_RUN_INTERVAL_DAYS))

    if not _parse_iso_datetime(schedule.get("firstRunAt")):
        schedule["firstRunAt"] = started_at.isoformat()

    schedule["nextRunAt"] = (started_at + timedelta(days=interval_days)).isoformat()

    state["run"] = {
        "status": "running",
        "message": "Assessment is running. Keep this page open and refresh to track progress.",
        "runId": run_id,
        "trigger": trigger,
        "startedAt": started_at.isoformat(),
        "finishedAt": "",
        "runDirectory": str(run_directory),
        "logPath": str(log_path),
    }

    authentication = _normalize_authentication_config(state.get("authentication"))
    state["run"]["message"] = "Assessment is running with certificate authentication."

    return {
        "runId": run_id,
        "trigger": trigger,
        "startedAt": started_at,
        "runDirectory": run_directory,
        "logPath": log_path,
        "authentication": authentication,
    }


def _read_log_tail(log_path: Path, max_characters: int = 3000) -> str:
    if not log_path.exists() or not log_path.is_file():
        return ""

    try:
        content = log_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""

    content = content.strip()
    if not content:
        return ""

    if len(content) <= max_characters:
        return content
    return content[-max_characters:]


def _status_bucket(label: str) -> str:
    normalized = label.strip().lower()
    if not normalized:
        return "unknown"

    if normalized in {"pass", "passed", "success", "succeeded", "ok"}:
        return "passed"
    if normalized in {"fail", "failed", "error", "critical"}:
        return "failed"
    if normalized in {"warning", "warn", "caution"}:
        return "warning"
    if normalized in {"informational", "info", "notrun", "not run"}:
        return "informational"
    return normalized


def _summarize_report(report_path: Path) -> dict[str, object]:
    try:
        report_text = report_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return {}

    status_matches = re.findall(r'"status"\s*:\s*"([^"]+)"', report_text, flags=re.IGNORECASE)
    if not status_matches:
        status_matches = re.findall(r"data-status\s*=\s*['\"]([^'\"]+)['\"]", report_text, flags=re.IGNORECASE)

    risk_matches = re.findall(r'"risk"\s*:\s*"([^"]+)"', report_text, flags=re.IGNORECASE)

    status_counts: dict[str, int] = {}
    for status_value in status_matches:
        bucket = _status_bucket(status_value)
        status_counts[bucket] = status_counts.get(bucket, 0) + 1

    risk_counts: dict[str, int] = {}
    for risk_value in risk_matches:
        bucket = _status_bucket(risk_value)
        risk_counts[bucket] = risk_counts.get(bucket, 0) + 1

    summary: dict[str, object] = {
        "detectedStatusRows": len(status_matches),
        "statusCounts": status_counts,
    }
    if risk_matches:
        summary["detectedRiskRows"] = len(risk_matches)
        summary["riskCounts"] = risk_counts

    return summary


def _resolve_report_path(run_directory: Path) -> Path | None:
    preferred = run_directory / ZERO_TRUST_REPORT_FILENAME
    if preferred.exists() and preferred.is_file():
        return preferred

    matches = [
        candidate
        for candidate in run_directory.rglob(ZERO_TRUST_REPORT_FILENAME)
        if candidate.exists() and candidate.is_file()
    ]
    if not matches:
        return None

    matches.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    return matches[0]


def _powershell_single_quote(value: object) -> str:
    return "'" + str(value).replace("'", "''") + "'"


def _run_checked_command(
    command: list[str],
    *,
    timeout_seconds: int = 120,
    cwd: Path | None = None,
) -> str:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=timeout_seconds,
            cwd=str(cwd) if isinstance(cwd, Path) else None,
        )
    except FileNotFoundError as error:
        raise ValueError(f"Required command `{command[0]}` is not available on this server.") from error
    except subprocess.SubprocessError as error:
        raise ValueError(f"Unable to run `{command[0]}` while preparing the certificate: {error}") from error

    if completed.returncode != 0:
        details = (completed.stderr or completed.stdout).strip()
        if details:
            raise ValueError(f"`{command[0]}` failed: {details}")
        raise ValueError(f"`{command[0]}` failed with exit code {completed.returncode}.")

    return completed.stdout.strip()


def _certificate_common_name() -> str:
    return f"ZeroTrustAssessment-{timezone.now().strftime('%Y%m%d%H%M%S')}"


def _import_certificate_into_powershell_store(pfx_path: Path, password: str) -> dict[str, str]:
    script = "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            f"$pfxPath = {_powershell_single_quote(str(pfx_path))}",
            f"$plain = {_powershell_single_quote(password)}",
            "$cert = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2",
            "$cert.Import($pfxPath, $plain, [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::PersistKeySet)",
            "$stores = @(",
            "  @{ Name = 'My'; Location = 'CurrentUser' },",
            "  @{ Name = 'Root'; Location = 'CurrentUser' }",
            ")",
            "foreach ($storeInfo in $stores) {",
            "  $store = New-Object System.Security.Cryptography.X509Certificates.X509Store($storeInfo.Name, $storeInfo.Location)",
            "  $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)",
            "  $existing = $store.Certificates.Find([System.Security.Cryptography.X509Certificates.X509FindType]::FindByThumbprint, $cert.Thumbprint, $false)",
            "  if ($existing.Count -eq 0) {",
            "    $store.Add($cert)",
            "  }",
            "  $store.Close()",
            "}",
            'Write-Output ("{0}|{1}|{2}" -f $cert.Subject, $cert.Thumbprint, $cert.NotAfter.ToUniversalTime().ToString("o"))',
        ]
    )
    output = _run_checked_command(
        ["pwsh", "-NoLogo", "-NoProfile", "-Command", script],
        timeout_seconds=180,
    )
    parts = output.strip().split("|")
    if len(parts) < 3:
        raise ValueError("Certificate import completed but metadata could not be parsed.")

    return {
        "subject": _normalize_string(parts[0]),
        "thumbprint": _normalize_string(parts[1]).upper(),
        "expiresAt": _normalize_string(parts[2]),
    }


def _generate_trusted_app_only_certificate() -> dict[str, object]:
    if not shutil.which("openssl"):
        raise ValueError("OpenSSL is required. Install it on this server before generating the certificate.")
    if not shutil.which("pwsh"):
        raise ValueError("PowerShell 7 (`pwsh`) is required before generating the certificate.")

    certificate_id = f"cert-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    certificate_directory = (ZERO_TRUST_CERTIFICATES_ROOT / certificate_id).resolve()
    certificate_directory.mkdir(parents=True, exist_ok=True)

    private_key_path = certificate_directory / "app_only.key"
    certificate_pem_path = certificate_directory / "app_only.pem"
    public_key_path = certificate_directory / ZERO_TRUST_PUBLIC_CERTIFICATE_FILENAME
    pfx_path = certificate_directory / "app_only.pfx"

    common_name = _certificate_common_name()
    subject = f"CN={common_name}"
    openssl_subject = f"/CN={common_name}"
    pfx_password = uuid.uuid4().hex + uuid.uuid4().hex

    imported_metadata: dict[str, str] = {}
    try:
        _run_checked_command(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-sha256",
                "-days",
                str(ZERO_TRUST_CERTIFICATE_VALID_DAYS),
                "-nodes",
                "-subj",
                openssl_subject,
                "-keyout",
                str(private_key_path),
                "-out",
                str(certificate_pem_path),
            ],
            timeout_seconds=180,
        )

        _run_checked_command(
            [
                "openssl",
                "x509",
                "-in",
                str(certificate_pem_path),
                "-outform",
                "der",
                "-out",
                str(public_key_path),
            ],
            timeout_seconds=120,
        )

        _run_checked_command(
            [
                "openssl",
                "pkcs12",
                "-export",
                "-inkey",
                str(private_key_path),
                "-in",
                str(certificate_pem_path),
                "-out",
                str(pfx_path),
                "-passout",
                f"pass:{pfx_password}",
            ],
            timeout_seconds=120,
        )

        imported_metadata = _import_certificate_into_powershell_store(pfx_path, pfx_password)
    finally:
        for secret_path in [private_key_path, certificate_pem_path, pfx_path]:
            try:
                if secret_path.exists():
                    secret_path.unlink()
            except OSError:
                continue

    try:
        public_key_path.chmod(0o644)
    except OSError:
        pass

    generated_at = timezone.now().isoformat()
    return {
        "available": True,
        "subject": _normalize_string(imported_metadata.get("subject"), subject),
        "thumbprint": _normalize_string(imported_metadata.get("thumbprint")).upper(),
        "publicKeyPath": str(public_key_path),
        "generatedAt": generated_at,
        "expiresAt": _normalize_string(imported_metadata.get("expiresAt")),
        "downloadName": ZERO_TRUST_PUBLIC_CERTIFICATE_FILENAME,
    }


def _set_generated_certificate_metadata(authentication: dict[str, object], metadata: dict[str, object]) -> dict[str, object]:
    normalized_authentication = _normalize_authentication_config(authentication)
    app_only = normalized_authentication.get("appOnly") if isinstance(normalized_authentication.get("appOnly"), dict) else {}
    generated_certificate = _normalize_generated_certificate(metadata)
    app_only["generatedCertificate"] = generated_certificate
    app_only["certificateReference"] = _normalize_string(
        generated_certificate.get("subject"),
        _normalize_string(app_only.get("certificateReference")),
    )
    normalized_authentication["appOnly"] = app_only
    return normalized_authentication


def generate_zero_trust_certificate() -> dict[str, object]:
    platform_info = detect_linux_platform()
    if not platform_info.get("supported"):
        raise ValueError(_normalize_string(platform_info.get("reason"), "Ubuntu is required."))
    _require_runtime_service_owner()

    generated_certificate = _generate_trusted_app_only_certificate()

    with transaction.atomic():
        record, _ = PortalState.objects.select_for_update().get_or_create(
            key=ZERO_TRUST_STATE_KEY,
            defaults={"payload": _state_default()},
        )
        state = normalize_zero_trust_state(record.payload)
        run_status = _normalize_string(state.get("run", {}).get("status"))
        if run_status == "running":
            raise ValueError("Cannot generate a certificate while an assessment run is active.")

        authentication = _set_generated_certificate_metadata(
            _normalize_authentication_config(state.get("authentication")),
            generated_certificate,
        )
        state["authentication"] = authentication
        record.payload = state
        record.save(update_fields=["payload"])

    return get_zero_trust_assessment_payload(auto_run_due=False)


def get_zero_trust_public_certificate_path() -> Path | None:
    state = _read_zero_trust_state()
    authentication = _normalize_authentication_config(state.get("authentication"))
    app_only = authentication.get("appOnly") if isinstance(authentication.get("appOnly"), dict) else {}
    generated_certificate = _normalize_generated_certificate(app_only.get("generatedCertificate"))
    public_key_path_raw = _normalize_string(generated_certificate.get("publicKeyPath"))
    if not public_key_path_raw:
        return None

    public_key_path = Path(public_key_path_raw).expanduser().resolve()
    if not _is_path_within_root(public_key_path, ZERO_TRUST_CERTIFICATES_ROOT):
        return None
    if not public_key_path.exists() or not public_key_path.is_file():
        return None

    return public_key_path


def _build_connect_command(authentication: dict[str, object]) -> str:
    app_only = authentication.get("appOnly") if isinstance(authentication.get("appOnly"), dict) else {}
    tenant_id = _validate_guid(str(app_only.get("tenantId") or ""), "Tenant ID")
    client_id = _validate_guid(str(app_only.get("clientId") or ""), "Client ID")
    certificate_reference = _normalize_string(app_only.get("certificateReference"))
    if not certificate_reference:
        raise ValueError("Certificate reference is required for certificate authentication.")

    return " ".join(
        [
            "Connect-ZtAssessment",
            "-ClientId",
            _powershell_single_quote(client_id),
            "-TenantId",
            _powershell_single_quote(tenant_id),
            "-Certificate",
            _powershell_single_quote(certificate_reference),
        ]
    )


def _build_powershell_script(report_directory: Path, authentication: dict[str, object]) -> str:
    escaped_directory = str(report_directory).replace("'", "''")
    connect_command = _build_connect_command(authentication)
    return "\n".join(
        [
            "$ErrorActionPreference = 'Stop'",
            connect_command,
            f"Invoke-ZtAssessment -Path '{escaped_directory}'",
        ]
    )


def _finalize_run(
    run_context: dict[str, object],
    *,
    status: str,
    message: str,
    finished_at: timezone.datetime,
    return_code: int | None,
    report_path: Path | None,
    summary: dict[str, object],
) -> None:
    run_id = _normalize_string(run_context.get("runId"))
    run_directory = run_context.get("runDirectory")
    log_path = run_context.get("logPath")
    trigger = _normalize_string(run_context.get("trigger"))
    started_at_raw = run_context.get("startedAt")
    started_at = started_at_raw if isinstance(started_at_raw, timezone.datetime) else finished_at

    report_generated_at = ""
    report_size_bytes = 0
    report_path_value = ""
    if report_path and report_path.exists() and report_path.is_file():
        report_path_value = str(report_path)
        report_size_bytes = int(report_path.stat().st_size)
        report_generated_at = timezone.datetime.fromtimestamp(
            report_path.stat().st_mtime,
            tz=dt_timezone.utc,
        ).isoformat()

    log_path_value = str(log_path) if isinstance(log_path, Path) else _normalize_string(log_path)

    history_entry: dict[str, object] = {
        "runId": run_id,
        "status": status,
        "message": message,
        "trigger": trigger,
        "startedAt": started_at.isoformat(),
        "finishedAt": finished_at.isoformat(),
        "runDirectory": str(run_directory) if isinstance(run_directory, Path) else _normalize_string(run_directory),
        "reportPath": report_path_value,
        "reportSizeBytes": report_size_bytes,
        "reportGeneratedAt": report_generated_at,
        "logPath": log_path_value,
        "returnCode": return_code,
        "summary": summary,
    }

    with transaction.atomic():
        record, _ = PortalState.objects.select_for_update().get_or_create(
            key=ZERO_TRUST_STATE_KEY,
            defaults={"payload": _state_default()},
        )
        state = normalize_zero_trust_state(record.payload)

        schedule = state["schedule"]
        interval_days = max(1, int(schedule.get("intervalDays") or ZERO_TRUST_RUN_INTERVAL_DAYS))

        if not _parse_iso_datetime(schedule.get("firstRunAt")):
            schedule["firstRunAt"] = started_at.isoformat()
        schedule["lastRunAt"] = finished_at.isoformat()
        if status == "succeeded":
            schedule["lastSuccessfulRunAt"] = finished_at.isoformat()

        next_run_at = _parse_iso_datetime(schedule.get("nextRunAt"))
        if not next_run_at or next_run_at <= finished_at:
            schedule["nextRunAt"] = (finished_at + timedelta(days=interval_days)).isoformat()

        state["run"] = {
            "status": status,
            "message": message,
            "runId": run_id,
            "trigger": trigger,
            "startedAt": started_at.isoformat(),
            "finishedAt": finished_at.isoformat(),
            "runDirectory": history_entry["runDirectory"],
            "logPath": log_path_value,
        }

        history: list[dict[str, object]] = []
        for item in state.get("history", []):
            normalized_item = _normalize_history_entry(item)
            if normalized_item is None:
                continue
            if _normalize_string(normalized_item.get("runId")) == run_id:
                continue
            history.append(normalized_item)
        state["history"] = [history_entry] + history[: ZERO_TRUST_HISTORY_LIMIT - 1]

        if status == "succeeded":
            state["latestResult"] = {
                "runId": run_id,
                "status": status,
                "message": message,
                "reportPath": report_path_value,
                "reportSizeBytes": report_size_bytes,
                "reportGeneratedAt": report_generated_at,
                "logPath": log_path_value,
                "returnCode": return_code,
                "summary": summary,
            }
        elif not state.get("latestResult"):
            state["latestResult"] = {
                "runId": run_id,
                "status": status,
                "message": message,
                "reportPath": "",
                "reportSizeBytes": 0,
                "reportGeneratedAt": "",
                "logPath": log_path_value,
                "returnCode": return_code,
                "summary": {},
            }

        record.payload = state
        record.save(update_fields=["payload"])


def _run_assessment_in_background(run_context: dict[str, object]) -> None:
    run_directory = run_context.get("runDirectory")
    log_path = run_context.get("logPath")
    authentication = _normalize_authentication_config(run_context.get("authentication"))

    if not isinstance(run_directory, Path) or not isinstance(log_path, Path):
        return

    finished_at = timezone.now()
    status = "failed"
    message = "Assessment failed before startup."
    return_code: int | None = None
    report_path: Path | None = None
    summary: dict[str, object] = {}

    try:
        script = _build_powershell_script(run_directory, authentication)
        with log_path.open("w", encoding="utf-8") as stream:
            stream.write("Starting Microsoft Zero Trust Assessment...\n")
            stream.flush()
            process = subprocess.Popen(
                ["pwsh", "-NoLogo", "-NoProfile", "-Command", script],
                cwd=str(run_directory),
                stdout=stream,
                stderr=subprocess.STDOUT,
                text=True,
            )
            return_code = process.wait()

        report_path = _resolve_report_path(run_directory)
        if return_code == 0 and report_path is not None:
            status = "succeeded"
            message = "Assessment completed successfully."
            summary = _summarize_report(report_path)
        elif return_code == 0:
            status = "failed"
            message = "Assessment completed but the report file was not found."
        else:
            status = "failed"
            message = f"Assessment failed with exit code {return_code}."
    except FileNotFoundError:
        status = "failed"
        message = "PowerShell 7 (`pwsh`) is not installed. Run `scripts/local_setup.sh` first."
    except ValueError as error:
        status = "failed"
        message = str(error)
    except Exception as error:  # noqa: BLE001
        status = "failed"
        message = f"Assessment execution failed: {error}"

    finished_at = timezone.now()
    log_tail = _read_log_tail(log_path)
    if status == "failed" and log_tail:
        message = f"{message} Latest output: {log_tail[-800:]}"

    _finalize_run(
        run_context,
        status=status,
        message=message,
        finished_at=finished_at,
        return_code=return_code,
        report_path=report_path,
        summary=summary,
    )


def _start_run(
    *,
    trigger: str,
    require_due_schedule: bool,
) -> bool:
    platform_info = detect_linux_platform()
    if not platform_info.get("supported"):
        return False
    if _runtime_service_requirement_error():
        return False

    run_context: dict[str, object] | None = None

    with transaction.atomic():
        record, _ = PortalState.objects.select_for_update().get_or_create(
            key=ZERO_TRUST_STATE_KEY,
            defaults={"payload": _state_default()},
        )
        state = normalize_zero_trust_state(record.payload)

        current_status = _normalize_string(state.get("run", {}).get("status"))
        if current_status == "running":
            return False

        schedule = state["schedule"]
        prerequisites = detect_zero_trust_prerequisites(platform_info)
        prerequisite_readiness = _prerequisite_readiness(prerequisites)
        if not bool(prerequisite_readiness.get("ready")):
            state["run"] = {
                "status": "failed",
                "message": _normalize_string(
                    prerequisite_readiness.get("message"),
                    "Ubuntu prerequisites are incomplete.",
                ),
                "runId": "",
                "trigger": trigger,
                "startedAt": "",
                "finishedAt": "",
                "runDirectory": "",
                "logPath": "",
            }
            record.payload = state
            record.save(update_fields=["payload"])
            return False

        authentication = _normalize_authentication_config(state.get("authentication"))
        readiness = _authentication_readiness(authentication)
        if not bool(readiness.get("ready")):
            state["run"] = {
                "status": "failed",
                "message": _normalize_string(
                    readiness.get("message"),
                    "Certificate settings are incomplete.",
                ),
                "runId": "",
                "trigger": trigger,
                "startedAt": "",
                "finishedAt": "",
                "runDirectory": "",
                "logPath": "",
            }
            record.payload = state
            record.save(update_fields=["payload"])
            return False

        if require_due_schedule:
            if not _normalize_bool(schedule.get("autoRunEnabled"), True):
                return False

            first_run_at = _parse_iso_datetime(schedule.get("firstRunAt"))
            if first_run_at is None:
                return False

            next_run_at = _parse_iso_datetime(schedule.get("nextRunAt"))
            if next_run_at is None:
                interval_days = max(1, int(schedule.get("intervalDays") or ZERO_TRUST_RUN_INTERVAL_DAYS))
                next_run_at = first_run_at + timedelta(days=interval_days)
                schedule["nextRunAt"] = next_run_at.isoformat()

            if next_run_at > timezone.now():
                record.payload = state
                record.save(update_fields=["payload"])
                return False

        try:
            run_context = _prepare_run_context(state, trigger=trigger, started_at=timezone.now())
        except OSError as error:
            state["run"] = {
                "status": "failed",
                "message": f"Unable to prepare assessment workspace: {error}",
                "runId": "",
                "trigger": trigger,
                "startedAt": "",
                "finishedAt": "",
                "runDirectory": "",
                "logPath": "",
            }
            record.payload = state
            record.save(update_fields=["payload"])
            return False

        record.payload = state
        record.save(update_fields=["payload"])

    thread = threading.Thread(
        target=_run_assessment_in_background,
        args=(run_context,),
        daemon=True,
    )
    thread.start()
    return True


def trigger_due_zero_trust_assessment_if_needed() -> bool:
    return _start_run(trigger="scheduled", require_due_schedule=True)


def start_zero_trust_assessment_run(*, trigger: str = "manual") -> dict[str, object]:
    platform_info = detect_linux_platform()
    if not platform_info.get("supported"):
        with transaction.atomic():
            record, _ = PortalState.objects.select_for_update().get_or_create(
                key=ZERO_TRUST_STATE_KEY,
                defaults={"payload": _state_default()},
            )
            state = normalize_zero_trust_state(record.payload)
            state["run"] = {
                "status": "unsupported",
                "message": _normalize_string(platform_info.get("reason"), "Ubuntu is required."),
                "runId": "",
                "trigger": trigger,
                "startedAt": "",
                "finishedAt": "",
                "runDirectory": "",
                "logPath": "",
            }
            record.payload = state
            record.save(update_fields=["payload"])

        return get_zero_trust_assessment_payload(auto_run_due=False)

    runtime_service_error = _runtime_service_requirement_error()
    if runtime_service_error:
        with transaction.atomic():
            record, _ = PortalState.objects.select_for_update().get_or_create(
                key=ZERO_TRUST_STATE_KEY,
                defaults={"payload": _state_default()},
            )
            state = normalize_zero_trust_state(record.payload)
            state["run"] = {
                "status": "failed",
                "message": runtime_service_error,
                "runId": "",
                "trigger": trigger,
                "startedAt": "",
                "finishedAt": "",
                "runDirectory": "",
                "logPath": "",
            }
            record.payload = state
            record.save(update_fields=["payload"])

        return get_zero_trust_assessment_payload(auto_run_due=False)

    _start_run(trigger=trigger, require_due_schedule=False)
    return get_zero_trust_assessment_payload(auto_run_due=False)


def _install_instructions() -> dict[str, object]:
    return {
        "ubuntuPowerShell": {
            "source": POWERSHELL_INSTALL_DOC_URL,
            "commands": [],
        },
        "zeroTrustAssessment": {
            "source": ZERO_TRUST_DOC_URL,
            "commands": [
                "pwsh",
                "Connect-ZtAssessment -ClientId YOUR_APP_ID -TenantId YOUR_TENANT_ID -Certificate YOUR_CERT_SUBJECT",
                "Invoke-ZtAssessment -Path /path/to/output",
            ],
        },
        "graphAppOnlyAuth": {
            "source": GRAPH_APP_ONLY_DOC_URL,
            "commands": [
                "openssl req -x509 -newkey rsa:2048 -sha256 -days 825 -nodes -subj '/CN=ZeroTrustAssessment' -keyout app_only.key -out app_only.pem",
                "openssl x509 -in app_only.pem -outform der -out ZeroTrustAssessmentPublicKey.cer",
                "Connect-MgGraph -ClientId YOUR_APP_ID -TenantId YOUR_TENANT_ID -CertificateName YOUR_CERT_SUBJECT",
                "Get-MgContext",
                "Connect-ZtAssessment -ClientId YOUR_APP_ID -TenantId YOUR_TENANT_ID -Certificate YOUR_CERT_SUBJECT",
                "Invoke-ZtAssessment -Path /path/to/output",
            ],
        },
    }


def _entra_setup_directions() -> list[dict[str, object]]:
    return [
        {
            "title": "Create a trusted X.509 certificate on this Ubuntu server",
            "details": [
                "Use the Generate certificate action in this page so the app creates the certificate with a private key.",
                "The generated certificate is installed into the runtime service PowerShell certificate stores (`CurrentUser/My` and `CurrentUser/Root`).",
                "Download the generated public key in `.cer` format from this page for Entra upload.",
            ],
        },
        {
            "title": "Register an app in Microsoft Entra ID",
            "details": [
                "Create a single-tenant app registration in the target tenant.",
                "Upload the certificate public key under Certificates & secrets.",
                "Capture Application (client) ID and Directory (tenant) ID.",
            ],
        },
        {
            "title": "Grant Microsoft Graph application permissions",
            "details": [
                "Add the required Microsoft Graph Application permissions from the Zero Trust Assessment documentation.",
                "Grant admin consent for the tenant.",
                "Ensure the app-only permissions cover the checks you expect to run.",
            ],
            "referenceUrl": ZERO_TRUST_DOC_URL,
            "referenceLabel": "Zero Trust Assessment required Microsoft Graph permissions",
            "permissions": ZERO_TRUST_REQUIRED_GRAPH_PERMISSIONS,
        },
        {
            "title": "Grant service access used by Connect-ZtAssessment",
            "details": [
                "Configure equivalent app/service principal permissions for Azure, Exchange Online, SharePoint Online, and Security & Compliance where required.",
                "If app-only access is incomplete for a service, related checks can fail or be skipped.",
            ],
        },
        {
            "title": "Configure this portal and validate",
            "details": [
                "In this page, enter Tenant ID and Client ID.",
                "Keep the auto-populated certificate reference from the generated cert, or provide your own trusted certificate reference.",
                "Run the assessment and verify success in the run history and report output.",
            ],
        },
    ]


def update_zero_trust_authentication(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("Authentication payload must be an object.")

    candidate = payload.get("authentication") if isinstance(payload.get("authentication"), dict) else payload

    with transaction.atomic():
        record, _ = PortalState.objects.select_for_update().get_or_create(
            key=ZERO_TRUST_STATE_KEY,
            defaults={"payload": _state_default()},
        )
        state = normalize_zero_trust_state(record.payload)
        run_status = _normalize_string(state.get("run", {}).get("status"))
        if run_status == "running":
            raise ValueError("Cannot update authentication while an assessment run is active.")

        normalized = _validate_authentication_config(candidate)
        existing_authentication = _normalize_authentication_config(state.get("authentication"))
        existing_app_only = (
            existing_authentication.get("appOnly")
            if isinstance(existing_authentication.get("appOnly"), dict)
            else {}
        )
        existing_generated_certificate = _normalize_generated_certificate(
            existing_app_only.get("generatedCertificate")
        )
        normalized_app_only = normalized.get("appOnly") if isinstance(normalized.get("appOnly"), dict) else {}
        normalized_app_only["generatedCertificate"] = existing_generated_certificate
        normalized["appOnly"] = normalized_app_only

        state["authentication"] = normalized
        record.payload = state
        record.save(update_fields=["payload"])

    return get_zero_trust_assessment_payload(auto_run_due=False)


def get_zero_trust_assessment_payload(*, auto_run_due: bool = False) -> dict[str, object]:
    if auto_run_due:
        trigger_due_zero_trust_assessment_if_needed()

    state = _read_zero_trust_state()
    platform_info = detect_linux_platform()
    prerequisites = detect_zero_trust_prerequisites(platform_info)
    authentication = _normalize_authentication_config(state.get("authentication"))
    readiness = _authentication_readiness(authentication)

    return {
        "ubuntuOnly": True,
        "platform": platform_info,
        "prerequisites": prerequisites,
        "authentication": {
            **authentication,
            "ready": bool(readiness.get("ready")),
            "statusMessage": _normalize_string(readiness.get("message")),
        },
        "run": state["run"],
        "schedule": state["schedule"],
        "latestResult": state["latestResult"],
        "history": state["history"],
        "docs": {
            "zeroTrust": ZERO_TRUST_DOC_URL,
            "powerShellUbuntu": POWERSHELL_INSTALL_DOC_URL,
            "graphAppOnlyAuth": GRAPH_APP_ONLY_DOC_URL,
        },
        "installInstructions": _install_instructions(),
        "entraSetupDirections": _entra_setup_directions(),
        "updatedAt": timezone.now().isoformat(),
    }


def get_latest_zero_trust_report_path() -> Path | None:
    state = _read_zero_trust_state()
    latest_result = state.get("latestResult") if isinstance(state.get("latestResult"), dict) else {}
    report_path_raw = _normalize_string(latest_result.get("reportPath"))
    if not report_path_raw:
        return None

    report_path = Path(report_path_raw).expanduser().resolve()
    if not _is_path_within_root(report_path, ZERO_TRUST_RUNS_ROOT):
        return None
    if not report_path.exists() or not report_path.is_file():
        return None

    return report_path
