from __future__ import annotations

import hashlib
import json
import mimetypes
import os
import re
import shutil
import socket
import subprocess
import uuid
from datetime import datetime, timedelta, timezone as dt_timezone
from pathlib import Path, PurePosixPath

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
from django.conf import settings
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from .models import (
    ZeroTrustAssessmentArtifact,
    ZeroTrustAssessmentRun,
    ZeroTrustAssessmentRunLog,
    ZeroTrustCertificate,
    ZeroTrustRunStatus,
    ZeroTrustTenantProfile,
)


RUN_WARNING_RE = re.compile(r"\b(?:warn(?:ing)?|skip(?:ped|ping)?)\b", re.IGNORECASE)
ENTRYPOINT_CANDIDATE_NAMES = ("ZeroTrustAssessmentReport.html",)


class AssessmentValidationError(Exception):
    pass


def normalize_string(value: object, fallback: str = "") -> str:
    if value is None:
        return fallback
    normalized = str(value).strip()
    return normalized if normalized else fallback


def normalize_thumbprint(value: object) -> str:
    return re.sub(r"[^A-Fa-f0-9]", "", normalize_string(value)).upper()


def make_external_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def assessment_storage_root() -> Path:
    return Path(settings.ASSESSMENT_STORAGE_ROOT)


def assessment_certificate_root() -> Path:
    return Path(settings.ASSESSMENT_CERTIFICATE_ROOT)


def assessment_staging_root() -> Path:
    return Path(settings.ASSESSMENT_STAGING_ROOT)


def ensure_directory(path: Path, mode: int = 0o700) -> Path:
    try:
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, mode)
        return path
    except OSError as error:
        raise AssessmentValidationError(
            f"Unable to access assessment storage at {path}. Check ASSESSMENT_STORAGE_ROOT permissions."
        ) from error


def ensure_assessment_roots() -> None:
    ensure_directory(assessment_storage_root())
    ensure_directory(assessment_certificate_root())
    ensure_directory(assessment_staging_root())


def safe_relative_path(file_path: Path, root_path: Path) -> str:
    try:
        relative_path = file_path.relative_to(root_path)
    except ValueError as error:
        raise AssessmentValidationError("Assessment artifact path escaped the staging root.") from error

    normalized = PurePosixPath(relative_path.as_posix())
    if normalized.is_absolute() or ".." in normalized.parts:
        raise AssessmentValidationError("Assessment artifact path is invalid.")
    return str(normalized)


def guess_content_type(path_value: str) -> str:
    content_type, _ = mimetypes.guess_type(path_value)
    return content_type or "application/octet-stream"


def infer_artifact_type(relative_path: str) -> str:
    suffix = Path(relative_path).suffix.lower()
    if suffix == ".html":
        return "html"
    if suffix == ".css":
        return "css"
    if suffix == ".js":
        return "js"
    if suffix == ".json":
        return "json"
    if suffix in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}:
        return "image"
    if suffix in {".woff", ".woff2", ".ttf", ".otf", ".eot"}:
        return "font"
    return "file"


def powershell_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def certificate_directory(profile: ZeroTrustTenantProfile, certificate_id: str) -> Path:
    return assessment_certificate_root() / profile.external_id / certificate_id


def run_staging_directory(run: ZeroTrustAssessmentRun) -> Path:
    return assessment_staging_root() / run.external_id


def current_profile_certificate(profile: ZeroTrustTenantProfile) -> ZeroTrustCertificate | None:
    return profile.certificates.filter(is_current=True).order_by("-created_at").first()


def current_run_log_sequence(run: ZeroTrustAssessmentRun) -> int:
    return int(
        ZeroTrustAssessmentRunLog.objects.filter(run=run).aggregate(max_sequence=Max("sequence")).get("max_sequence")
        or 0
    )


def create_run_log(
    run: ZeroTrustAssessmentRun,
    message: str,
    *,
    level: str = "info",
    stream: str = "system",
    sequence: int | None = None,
) -> ZeroTrustAssessmentRunLog:
    next_sequence = sequence or current_run_log_sequence(run) + 1
    return ZeroTrustAssessmentRunLog.objects.create(
        run=run,
        sequence=next_sequence,
        level=level,
        stream=stream,
        message=message,
    )


def build_profile_payload(profile: ZeroTrustTenantProfile) -> dict[str, object]:
    payload = profile.to_portal_dict()
    certificate = current_profile_certificate(profile)
    latest_run = profile.assessment_runs.select_related("certificate").order_by("-created_at").first()
    payload["currentCertificate"] = certificate.to_portal_dict() if certificate else None
    payload["latestRun"] = build_run_payload(latest_run) if latest_run else None
    return payload


def build_run_payload(run: ZeroTrustAssessmentRun | None) -> dict[str, object] | None:
    if run is None:
        return None
    payload = run.to_portal_dict()
    payload["reportUrl"] = f"/assessments/runs/{run.external_id}/report/" if run.has_report else ""
    payload["assetBaseUrl"] = f"/assessments/runs/{run.external_id}/files/"
    return payload


def list_zero_trust_profiles() -> list[dict[str, object]]:
    return [build_profile_payload(profile) for profile in ZeroTrustTenantProfile.objects.all()]


def get_zero_trust_profile(profile_id: str) -> ZeroTrustTenantProfile:
    normalized_profile_id = normalize_string(profile_id)
    if not normalized_profile_id:
        raise AssessmentValidationError("Assessment profile id is required.")

    try:
        return ZeroTrustTenantProfile.objects.get(external_id=normalized_profile_id)
    except ZeroTrustTenantProfile.DoesNotExist as error:
        raise AssessmentValidationError("Assessment profile was not found.") from error


def get_zero_trust_profile_detail(profile_id: str) -> dict[str, object]:
    profile = get_zero_trust_profile(profile_id)
    runs = profile.assessment_runs.select_related("certificate").order_by("-created_at")[:25]
    return {
        "profile": build_profile_payload(profile),
        "runs": [build_run_payload(run) for run in runs],
    }


def save_zero_trust_profile(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise AssessmentValidationError("Assessment profile payload must be an object.")

    profile_id = normalize_string(payload.get("id"))
    tenant_id = normalize_string(payload.get("tenantId"))
    client_id = normalize_string(payload.get("clientId"))
    display_name = normalize_string(payload.get("displayName"))
    requested_thumbprint = normalize_thumbprint(payload.get("certificateThumbprint"))

    if not tenant_id:
        raise AssessmentValidationError("TenantId is required.")
    if not client_id:
        raise AssessmentValidationError("ClientId is required.")

    with transaction.atomic():
        if profile_id:
            profile = get_zero_trust_profile(profile_id)
        else:
            profile = (
                ZeroTrustTenantProfile.objects.select_for_update()
                .filter(tenant_id=tenant_id, client_id=client_id)
                .first()
            )
            if profile is None:
                profile = ZeroTrustTenantProfile(
                    external_id=make_external_id("zt-profile"),
                    tenant_id=tenant_id,
                    client_id=client_id,
                )

        profile.tenant_id = tenant_id
        profile.client_id = client_id
        profile.display_name = display_name or tenant_id

        if (
            ZeroTrustTenantProfile.objects.exclude(pk=profile.pk)
            .filter(tenant_id=tenant_id, client_id=client_id)
            .exists()
        ):
            raise AssessmentValidationError("An assessment profile already exists for this TenantId and ClientId.")

        certificate = current_profile_certificate(profile) if profile.pk else None
        if requested_thumbprint:
            if certificate is None or certificate.thumbprint != requested_thumbprint:
                raise AssessmentValidationError(
                    "CertificateThumbprint must match the current certificate generated for this profile."
                )
            profile.certificate_thumbprint = requested_thumbprint
        elif certificate is not None:
            profile.certificate_thumbprint = certificate.thumbprint
        else:
            profile.certificate_thumbprint = ""

        profile.save()

    return build_profile_payload(profile)


def make_certificate_subject(profile: ZeroTrustTenantProfile) -> str:
    tenant_label = re.sub(r"[^A-Za-z0-9-]", "-", profile.tenant_id)[:48] or "tenant"
    return f"CN=ZeroTrustAssessment-{tenant_label}"


def aware_certificate_datetime(value: datetime) -> datetime:
    if timezone.is_aware(value):
        return value
    return timezone.make_aware(value, dt_timezone.utc)


def generate_zero_trust_certificate(profile_id: str) -> dict[str, object]:
    ensure_assessment_roots()
    profile = get_zero_trust_profile(profile_id)

    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject_string = make_certificate_subject(profile)
    common_name = subject_string.split("=", 1)[-1]
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = timezone.now()
    not_before = now - timedelta(minutes=5)
    not_after = now + timedelta(days=730)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(rsa_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(not_before)
        .not_valid_after(not_after)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=True,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=False,
        )
        .sign(private_key=rsa_key, algorithm=hashes.SHA256())
    )

    thumbprint = certificate.fingerprint(hashes.SHA1()).hex().upper()
    certificate_id = make_external_id("zt-cert")
    certificate_dir = ensure_directory(certificate_directory(profile, certificate_id))
    public_der = certificate.public_bytes(serialization.Encoding.DER)
    public_pem = certificate.public_bytes(serialization.Encoding.PEM)
    private_key_pem = rsa_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pfx_bytes = pkcs12.serialize_key_and_certificates(
        name=common_name.encode("utf-8"),
        key=rsa_key,
        cert=certificate,
        cas=None,
        encryption_algorithm=serialization.NoEncryption(),
    )

    public_certificate_path = certificate_dir / "certificate.cer"
    public_pem_path = certificate_dir / "certificate.pem"
    private_key_path = certificate_dir / "private.key"
    pfx_path = certificate_dir / "certificate.pfx"

    public_certificate_path.write_bytes(public_der)
    public_pem_path.write_bytes(public_pem)
    private_key_path.write_bytes(private_key_pem)
    pfx_path.write_bytes(pfx_bytes)

    os.chmod(public_certificate_path, 0o600)
    os.chmod(public_pem_path, 0o600)
    os.chmod(private_key_path, 0o600)
    os.chmod(pfx_path, 0o600)

    with transaction.atomic():
        ZeroTrustCertificate.objects.filter(profile=profile, is_current=True).update(is_current=False)
        stored_certificate = ZeroTrustCertificate.objects.create(
            external_id=certificate_id,
            profile=profile,
            thumbprint=thumbprint,
            subject=subject_string,
            serial_number=format(certificate.serial_number, "x").upper(),
            not_before=aware_certificate_datetime(
                getattr(certificate, "not_valid_before_utc", certificate.not_valid_before)
            ),
            not_after=aware_certificate_datetime(
                getattr(certificate, "not_valid_after_utc", certificate.not_valid_after)
            ),
            key_algorithm="RSA",
            key_size=2048,
            public_certificate_der=public_der,
            certificate_path=str(public_certificate_path),
            private_key_path=str(private_key_path),
            pfx_path=str(pfx_path),
            is_current=True,
        )
        profile.certificate_thumbprint = thumbprint
        profile.save(update_fields=["certificate_thumbprint", "updated_at"])

    return {
        "profile": build_profile_payload(profile),
        "certificate": stored_certificate.to_portal_dict(),
        "downloadUrl": f"/api/assessments/{profile.external_id}/certificate.cer",
    }


def get_zero_trust_certificate_download(profile_id: str) -> tuple[str, bytes]:
    profile = get_zero_trust_profile(profile_id)
    certificate = current_profile_certificate(profile)
    if certificate is None:
        raise AssessmentValidationError("Generate a certificate for this profile before downloading it.")

    file_name = f"{profile.tenant_id}-{certificate.thumbprint}.cer"
    return file_name, bytes(certificate.public_certificate_der)


def create_zero_trust_run(profile_id: str, *, actor_username: str = "") -> dict[str, object]:
    profile = get_zero_trust_profile(profile_id)
    certificate = current_profile_certificate(profile)
    if certificate is None:
        raise AssessmentValidationError("Generate a certificate before starting an assessment.")

    active_statuses = [
        ZeroTrustRunStatus.QUEUED,
        ZeroTrustRunStatus.CLAIMED,
        ZeroTrustRunStatus.RUNNING,
        ZeroTrustRunStatus.INGESTING,
    ]
    if profile.assessment_runs.filter(status__in=active_statuses).exists():
        raise AssessmentValidationError("An assessment is already queued or running for this tenant.")

    run = ZeroTrustAssessmentRun.objects.create(
        external_id=make_external_id("zt-run"),
        profile=profile,
        certificate=certificate,
        status=ZeroTrustRunStatus.QUEUED,
        status_message="Queued for background execution.",
        input_snapshot={
            "tenantId": profile.tenant_id,
            "clientId": profile.client_id,
            "certificateThumbprint": certificate.thumbprint,
        },
        requested_by=normalize_string(actor_username),
    )
    create_run_log(run, "Assessment run queued.", level="info", stream="system")
    return build_run_payload(run) or {}


def get_zero_trust_run(run_id: str) -> ZeroTrustAssessmentRun:
    normalized_run_id = normalize_string(run_id)
    if not normalized_run_id:
        raise AssessmentValidationError("Assessment run id is required.")
    try:
        return ZeroTrustAssessmentRun.objects.select_related("profile", "certificate").get(external_id=normalized_run_id)
    except ZeroTrustAssessmentRun.DoesNotExist as error:
        raise AssessmentValidationError("Assessment run was not found.") from error


def list_zero_trust_run_logs(run_id: str, *, after_sequence: int = 0, limit: int = 200) -> list[dict[str, object]]:
    run = get_zero_trust_run(run_id)
    logs = run.logs.filter(sequence__gt=max(0, after_sequence)).order_by("sequence")[: max(1, min(limit, 500))]
    return [log.to_portal_dict() for log in logs]


def get_zero_trust_run_detail(run_id: str) -> dict[str, object]:
    run = get_zero_trust_run(run_id)
    return {
        "run": build_run_payload(run),
        "logs": list_zero_trust_run_logs(run_id),
    }


def stale_run_candidates() -> list[ZeroTrustAssessmentRun]:
    now = timezone.now()
    return list(
        ZeroTrustAssessmentRun.objects.filter(
            status__in=[
                ZeroTrustRunStatus.CLAIMED,
                ZeroTrustRunStatus.RUNNING,
                ZeroTrustRunStatus.INGESTING,
            ],
            lease_expires_at__lt=now,
        )
    )


def mark_stale_zero_trust_runs() -> int:
    marked = 0
    for run in stale_run_candidates():
        run.status = ZeroTrustRunStatus.STALE
        run.status_message = "Worker lease expired before the run finished."
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "status_message", "completed_at", "updated_at"])
        create_run_log(run, run.status_message, level="error", stream="system")
        marked += 1
    return marked


def claim_next_zero_trust_run(*, worker_id: str) -> ZeroTrustAssessmentRun | None:
    with transaction.atomic():
        run = (
            ZeroTrustAssessmentRun.objects.select_for_update(skip_locked=True)
            .select_related("profile", "certificate")
            .filter(status=ZeroTrustRunStatus.QUEUED)
            .order_by("created_at")
            .first()
        )
        if run is None:
            return None

        now = timezone.now()
        run.status = ZeroTrustRunStatus.CLAIMED
        run.status_message = f"Claimed by worker {worker_id}."
        run.worker_id = worker_id
        run.attempt_count += 1
        run.claimed_at = now
        run.last_heartbeat_at = now
        run.lease_expires_at = now + timedelta(seconds=settings.ASSESSMENT_WORKER_LEASE_SECONDS)
        run.save(
            update_fields=[
                "status",
                "status_message",
                "worker_id",
                "attempt_count",
                "claimed_at",
                "last_heartbeat_at",
                "lease_expires_at",
                "updated_at",
            ]
        )

    create_run_log(run, f"Run claimed by worker {worker_id}.", level="info", stream="system")
    return run


def heartbeat_zero_trust_run(run: ZeroTrustAssessmentRun) -> None:
    now = timezone.now()
    run.last_heartbeat_at = now
    run.lease_expires_at = now + timedelta(seconds=settings.ASSESSMENT_WORKER_LEASE_SECONDS)
    run.save(update_fields=["last_heartbeat_at", "lease_expires_at", "updated_at"])


def update_zero_trust_run_metadata(run: ZeroTrustAssessmentRun, metadata: dict[str, object]) -> None:
    changed_fields: list[str] = []
    module_version = normalize_string(metadata.get("moduleVersion"))
    powershell_version = normalize_string(metadata.get("powershellVersion"))
    if module_version and run.module_version != module_version:
        run.module_version = module_version
        changed_fields.append("module_version")
    if powershell_version and run.powershell_version != powershell_version:
        run.powershell_version = powershell_version
        changed_fields.append("powershell_version")
    if changed_fields:
        changed_fields.append("updated_at")
        run.save(update_fields=changed_fields)


def initial_worker_sequence(run: ZeroTrustAssessmentRun) -> int:
    return current_run_log_sequence(run)


def assessment_script_contents(run: ZeroTrustAssessmentRun, output_root: Path) -> str:
    certificate = run.certificate
    if certificate is None:
        raise AssessmentValidationError("Assessment run is missing a certificate.")

    script_lines = [
        "$ErrorActionPreference = 'Stop'",
        "$ProgressPreference = 'SilentlyContinue'",
        "$InformationPreference = 'Continue'",
        "try {",
        "  if (Get-Command Set-PSRepository -ErrorAction SilentlyContinue) {",
        "    Set-PSRepository -Name PSGallery -InstallationPolicy Trusted -ErrorAction SilentlyContinue | Out-Null",
        "  }",
        "  if (-not (Get-Module -ListAvailable -Name ZeroTrustAssessment)) {",
        "    if (Get-Command Install-PSResource -ErrorAction SilentlyContinue) {",
        "      Install-PSResource -Name ZeroTrustAssessment -Scope CurrentUser -TrustRepository -Quiet",
        "    } else {",
        "      Install-Module ZeroTrustAssessment -Scope CurrentUser -Force -AllowClobber",
        "    }",
        "  }",
        "  Import-Module ZeroTrustAssessment -Force",
        "  $moduleVersion = ''",
        "  $module = Get-Module ZeroTrustAssessment | Select-Object -First 1",
        "  if ($module) { $moduleVersion = $module.Version.ToString() }",
        "  $metadata = @{",
        "    moduleVersion = $moduleVersion",
        "    powershellVersion = $PSVersionTable.PSVersion.ToString()",
        "  }",
        "  Write-Host ('ZTA_META::' + ($metadata | ConvertTo-Json -Compress))",
        f"  $certificate = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new({powershell_literal(certificate.pfx_path)}, '', [System.Security.Cryptography.X509Certificates.X509KeyStorageFlags]::Exportable)",
        f"  Connect-ZtAssessment -ClientId {powershell_literal(run.profile.client_id)} -TenantId {powershell_literal(run.profile.tenant_id)} -Certificate $certificate -Force",
        f"  Invoke-ZtAssessment -Path {powershell_literal(str(output_root))} -ExportLog",
        "} catch {",
        "  Write-Error $_",
        "  exit 1",
        "}",
    ]
    return "\n".join(script_lines) + "\n"


def log_level_for_output(line: str) -> str:
    lowered = line.lower()
    if "error" in lowered or lowered.startswith("write-error"):
        return "error"
    if RUN_WARNING_RE.search(line):
        return "warning"
    return "info"


def ingest_assessment_artifacts(run: ZeroTrustAssessmentRun, export_root: Path) -> dict[str, object]:
    if not export_root.exists():
        raise AssessmentValidationError("Assessment output folder was not created.")

    files = [path for path in export_root.rglob("*") if path.is_file()]
    if not files:
        raise AssessmentValidationError("Assessment output folder did not contain any files.")

    entrypoint_relative_path = ""
    artifact_rows: list[ZeroTrustAssessmentArtifact] = []
    total_bytes = 0
    for path in sorted(files):
        if path.is_symlink():
            raise AssessmentValidationError("Symbolic links are not allowed in assessment artifacts.")
        relative_path = safe_relative_path(path, export_root)
        if not entrypoint_relative_path and Path(relative_path).name in ENTRYPOINT_CANDIDATE_NAMES:
            entrypoint_relative_path = relative_path

        content = path.read_bytes()
        sha256 = hashlib.sha256(content).hexdigest()
        total_bytes += len(content)
        artifact_rows.append(
            ZeroTrustAssessmentArtifact(
                run=run,
                relative_path=relative_path,
                artifact_type=infer_artifact_type(relative_path),
                content_type=guess_content_type(relative_path),
                size_bytes=len(content),
                sha256=sha256,
                is_entrypoint=False,
                content=content,
            )
        )

    if not entrypoint_relative_path:
        html_artifacts = [row for row in artifact_rows if row.relative_path.lower().endswith(".html")]
        if not html_artifacts:
            raise AssessmentValidationError("Assessment output did not include an HTML report.")
        entrypoint_relative_path = html_artifacts[0].relative_path

    for row in artifact_rows:
        row.is_entrypoint = row.relative_path == entrypoint_relative_path

    summary = {
        "artifactCount": len(artifact_rows),
        "totalBytes": total_bytes,
        "entrypointRelativePath": entrypoint_relative_path,
    }

    with transaction.atomic():
        ZeroTrustAssessmentArtifact.objects.filter(run=run).delete()
        ZeroTrustAssessmentArtifact.objects.bulk_create(artifact_rows)
        run.entrypoint_relative_path = entrypoint_relative_path
        run.ingested_at = timezone.now()
        run.summary_json = summary
        run.save(update_fields=["entrypoint_relative_path", "ingested_at", "summary_json", "updated_at"])

    return summary


def cleanup_assessment_staging(path_value: str) -> bool:
    target = Path(path_value)
    if not path_value:
        return True
    if not target.exists():
        return True
    shutil.rmtree(target)
    return not target.exists()


def finalize_zero_trust_run(
    run: ZeroTrustAssessmentRun,
    *,
    status: str,
    status_message: str,
    warning_summary: str = "",
    error_summary: str = "",
    exit_code: int | None = None,
) -> None:
    now = timezone.now()
    run.status = status
    run.status_message = status_message
    run.warning_summary = warning_summary
    run.error_summary = error_summary
    run.exit_code = exit_code
    run.completed_at = now
    run.last_heartbeat_at = now
    run.lease_expires_at = now
    run.save(
        update_fields=[
            "status",
            "status_message",
            "warning_summary",
            "error_summary",
            "exit_code",
            "completed_at",
            "last_heartbeat_at",
            "lease_expires_at",
            "updated_at",
        ]
    )
    if status in {ZeroTrustRunStatus.SUCCEEDED, ZeroTrustRunStatus.SUCCEEDED_WITH_WARNINGS}:
        run.profile.last_run_at = now
        run.profile.save(update_fields=["last_run_at", "updated_at"])


def process_zero_trust_run(run_id: str, *, worker_id: str) -> ZeroTrustAssessmentRun:
    run = get_zero_trust_run(run_id)
    ensure_assessment_roots()

    staging_dir = ensure_directory(run_staging_directory(run))
    output_dir = ensure_directory(staging_dir / "output")
    script_path = staging_dir / "run_assessment.ps1"
    script_path.write_text(assessment_script_contents(run, output_dir), encoding="utf-8")
    os.chmod(script_path, 0o600)

    run.status = ZeroTrustRunStatus.RUNNING
    run.status_message = "PowerShell assessment is running."
    run.started_at = timezone.now()
    run.staged_path = str(staging_dir)
    run.last_heartbeat_at = run.started_at
    run.lease_expires_at = run.started_at + timedelta(seconds=settings.ASSESSMENT_WORKER_LEASE_SECONDS)
    run.worker_id = worker_id
    run.save(
        update_fields=[
            "status",
            "status_message",
            "started_at",
            "staged_path",
            "last_heartbeat_at",
            "lease_expires_at",
            "worker_id",
            "updated_at",
        ]
    )

    sequence = initial_worker_sequence(run)
    warning_lines: list[str] = []
    last_heartbeat = timezone.now()
    create_run_log(run, "Launching PowerShell assessment process.", level="info", stream="system", sequence=sequence + 1)
    sequence += 1

    try:
        process = subprocess.Popen(
            ["pwsh", "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
    except FileNotFoundError as error:
        finalize_zero_trust_run(
            run,
            status=ZeroTrustRunStatus.FAILED,
            status_message="PowerShell 7 is not installed on the server.",
            error_summary=str(error),
        )
        create_run_log(run, run.status_message, level="error", stream="system", sequence=sequence + 1)
        cleanup_assessment_staging(run.staged_path)
        raise

    try:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip()
            if not line:
                continue
            if line.startswith("ZTA_META::"):
                try:
                    metadata = json.loads(line.split("::", 1)[1])
                except json.JSONDecodeError:
                    metadata = {}
                update_zero_trust_run_metadata(run, metadata if isinstance(metadata, dict) else {})
                continue

            log_level = log_level_for_output(line)
            if log_level == "warning" and line not in warning_lines:
                warning_lines.append(line)
            sequence += 1
            create_run_log(run, line, level=log_level, stream="stdout", sequence=sequence)

            now = timezone.now()
            if (now - last_heartbeat).total_seconds() >= 5:
                heartbeat_zero_trust_run(run)
                last_heartbeat = now

        process.wait()
        heartbeat_zero_trust_run(run)

        if process.returncode != 0:
            finalize_zero_trust_run(
                run,
                status=ZeroTrustRunStatus.FAILED,
                status_message="PowerShell assessment failed.",
                warning_summary="\n".join(warning_lines[:10]),
                error_summary=f"PowerShell exited with code {process.returncode}.",
                exit_code=process.returncode,
            )
            sequence += 1
            create_run_log(run, run.error_summary, level="error", stream="system", sequence=sequence)
            return run

        run.status = ZeroTrustRunStatus.INGESTING
        run.status_message = "Assessment completed. Ingesting report artifacts."
        run.exit_code = process.returncode
        run.save(update_fields=["status", "status_message", "exit_code", "updated_at"])
        sequence += 1
        create_run_log(run, run.status_message, level="info", stream="system", sequence=sequence)

        summary = ingest_assessment_artifacts(run, output_dir)
        status = (
            ZeroTrustRunStatus.SUCCEEDED_WITH_WARNINGS
            if warning_lines
            else ZeroTrustRunStatus.SUCCEEDED
        )
        status_message = "Assessment artifacts ingested into PostgreSQL."
        finalize_zero_trust_run(
            run,
            status=status,
            status_message=status_message,
            warning_summary="\n".join(warning_lines[:10]),
            exit_code=process.returncode,
        )
        sequence += 1
        create_run_log(
            run,
            f"Stored {summary['artifactCount']} assessment artifact(s) in PostgreSQL.",
            level="info",
            stream="system",
            sequence=sequence,
        )
        return run
    except AssessmentValidationError as error:
        finalize_zero_trust_run(
            run,
            status=ZeroTrustRunStatus.FAILED,
            status_message="Assessment completed but artifact ingestion failed.",
            warning_summary="\n".join(warning_lines[:10]),
            error_summary=str(error),
            exit_code=process.returncode if process.poll() is not None else None,
        )
        sequence += 1
        create_run_log(run, str(error), level="error", stream="system", sequence=sequence)
        return run
    finally:
        try:
            if cleanup_assessment_staging(run.staged_path):
                run.cleaned_up_at = timezone.now()
                run.save(update_fields=["cleaned_up_at", "updated_at"])
        except OSError as error:
            warning_message = f"Unable to remove staging directory: {error}"
            if warning_message not in warning_lines:
                warning_lines.append(warning_message)
            run.warning_summary = "\n".join(warning_lines[:10])
            run.status = (
                ZeroTrustRunStatus.SUCCEEDED_WITH_WARNINGS
                if run.status == ZeroTrustRunStatus.SUCCEEDED
                else run.status
            )
            run.save(update_fields=["warning_summary", "status", "updated_at"])
            sequence += 1
            create_run_log(run, warning_message, level="warning", stream="system", sequence=sequence)


def get_zero_trust_artifact(run_id: str, *, relative_path: str | None = None) -> ZeroTrustAssessmentArtifact:
    run = get_zero_trust_run(run_id)
    if relative_path is None:
        if not run.entrypoint_relative_path:
            raise AssessmentValidationError("This assessment run does not have a stored report.")
        relative_path = run.entrypoint_relative_path

    normalized_relative_path = str(PurePosixPath(normalize_string(relative_path)))
    if not normalized_relative_path or normalized_relative_path == "." or ".." in PurePosixPath(normalized_relative_path).parts:
        raise AssessmentValidationError("Assessment artifact path is invalid.")

    try:
        return run.artifacts.get(relative_path=normalized_relative_path)
    except ZeroTrustAssessmentArtifact.DoesNotExist as error:
        raise AssessmentValidationError("Assessment artifact was not found.") from error


def inject_report_base_href(html: str, *, run: ZeroTrustAssessmentRun) -> str:
    if "<base " in html.lower():
        return html

    base_tag = f'<base href="/assessments/runs/{run.external_id}/files/">'
    head_match = re.search(r"<head[^>]*>", html, flags=re.IGNORECASE)
    if head_match:
        insert_at = head_match.end()
        return html[:insert_at] + base_tag + html[insert_at:]
    return base_tag + html


def get_zero_trust_report_html(run_id: str) -> str:
    run = get_zero_trust_run(run_id)
    artifact = get_zero_trust_artifact(run_id)
    html = bytes(artifact.content).decode("utf-8", errors="replace")
    return inject_report_base_href(html, run=run)


def worker_identity() -> str:
    return f"{socket.gethostname()}:{os.getpid()}"
