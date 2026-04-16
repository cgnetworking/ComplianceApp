from __future__ import annotations

from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

RISK_FACTOR_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]
RISK_SCORE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(25)]


class UploadedPolicy(models.Model):
    document_id = models.CharField(max_length=24, unique=True)
    title = models.CharField(max_length=255)
    document_type = models.CharField(max_length=80, default="Uploaded policy")
    approver = models.CharField(max_length=255, default="Pending review")
    approved_by = models.CharField(max_length=255, blank=True, default="")
    approved_at = models.DateTimeField(blank=True, null=True)
    review_frequency = models.CharField(max_length=120, default="Not scheduled")
    path = models.CharField(max_length=255, default="")
    folder = models.CharField(max_length=120, default="Uploaded")
    purpose = models.TextField(blank=True, default="")
    content_html = models.TextField()
    raw_text = models.TextField(blank=True, default="")
    original_filename = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["document_id"]

    def __str__(self) -> str:
        return self.document_id

    def to_portal_dict(self) -> dict[str, object]:
        return {
            "id": self.document_id,
            "title": self.title,
            "type": self.document_type,
            "approver": self.approver,
            "approvedBy": self.approved_by,
            "approvedAt": self.approved_at.isoformat() if self.approved_at else "",
            "reviewFrequency": self.review_frequency,
            "path": self.path,
            "folder": self.folder,
            "purpose": self.purpose,
            "contentHtml": self.content_html,
            "isUploaded": True,
            "originalFilename": self.original_filename,
            "uploadedAt": self.uploaded_at.isoformat(),
        }


class VendorResponse(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    vendor_name = models.CharField(max_length=255)
    file_name = models.CharField(max_length=255)
    extension = models.CharField(max_length=16, default="file")
    mime_type = models.CharField(max_length=120, default="Unknown")
    file_size = models.BigIntegerField(default=0)
    imported_at = models.DateTimeField(auto_now_add=True)
    preview_text = models.TextField(blank=True, default="")
    summary = models.TextField(blank=True, default="")
    status = models.CharField(max_length=80, default="Metadata only")
    raw_text = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-imported_at"]

    def __str__(self) -> str:
        return self.vendor_name

    def to_portal_dict(self) -> dict[str, object]:
        return {
            "id": self.external_id,
            "vendorName": self.vendor_name,
            "fileName": self.file_name,
            "extension": self.extension,
            "mimeType": self.mime_type,
            "fileSize": self.file_size,
            "importedAt": self.imported_at.isoformat(),
            "previewText": self.preview_text,
            "summary": self.summary,
            "status": self.status,
        }


class RiskRecord(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    risk = models.TextField()
    probability = models.PositiveSmallIntegerField(default=3, validators=RISK_FACTOR_VALIDATORS)
    impact = models.PositiveSmallIntegerField(default=3, validators=RISK_FACTOR_VALIDATORS)
    initial_risk_level = models.PositiveSmallIntegerField(validators=RISK_SCORE_VALIDATORS)
    date = models.DateField()
    owner = models.CharField(max_length=255)
    closed_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-updated_at", "-created_at"]

    def __str__(self) -> str:
        return self.external_id

    def save(self, *args, **kwargs) -> None:
        score = int(self.probability or 0) * int(self.impact or 0)
        if 1 <= score <= 25:
            self.initial_risk_level = score
        super().save(*args, **kwargs)

    def to_portal_dict(self) -> dict[str, object]:
        score = int(self.probability or 0) * int(self.impact or 0)
        initial_risk_level = score if 1 <= score <= 25 else self.initial_risk_level
        return {
            "id": self.external_id,
            "risk": self.risk,
            "probability": self.probability,
            "impact": self.impact,
            "initialRiskLevel": initial_risk_level,
            "date": self.date.isoformat(),
            "owner": self.owner,
            "closedDate": self.closed_date.isoformat() if self.closed_date else "",
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


class ReviewChecklistItem(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    category = models.CharField(max_length=120, default="Custom")
    item = models.TextField()
    frequency = models.CharField(max_length=120, default="Annual")
    start_date = models.DateField(blank=True, null=True)
    owner = models.CharField(max_length=255, default="Shared portal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "created_at", "external_id"]

    def __str__(self) -> str:
        return self.external_id

    def to_portal_dict(self) -> dict[str, str]:
        return {
            "id": self.external_id,
            "category": self.category,
            "item": self.item,
            "frequency": self.frequency,
            "startDate": self.start_date.isoformat() if self.start_date else "",
            "owner": self.owner,
            "createdAt": self.created_at.isoformat(),
        }


class ReviewChecklistRecommendation(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    category = models.CharField(max_length=120, default="Custom")
    item = models.TextField()
    frequency = models.CharField(max_length=120, default="Annual")
    start_date = models.DateField(blank=True, null=True)
    owner = models.CharField(max_length=255, default="Shared portal")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "created_at", "external_id"]

    def __str__(self) -> str:
        return self.external_id

    def to_portal_dict(self) -> dict[str, str]:
        return {
            "id": self.external_id,
            "category": self.category,
            "item": self.item,
            "frequency": self.frequency,
            "startDate": self.start_date.isoformat() if self.start_date else "",
            "owner": self.owner,
        }


class PortalState(models.Model):
    key = models.CharField(max_length=64, unique=True)
    payload = models.JSONField(default=dict, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]

    def __str__(self) -> str:
        return self.key


class ZeroTrustRunStatus(models.TextChoices):
    QUEUED = "queued", "Queued"
    CLAIMED = "claimed", "Claimed"
    RUNNING = "running", "Running"
    INGESTING = "ingesting", "Ingesting"
    SUCCEEDED = "succeeded", "Succeeded"
    SUCCEEDED_WITH_WARNINGS = "succeeded_with_warnings", "Succeeded with warnings"
    FAILED = "failed", "Failed"
    STALE = "stale", "Stale"


class ZeroTrustTenantProfile(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    display_name = models.CharField(max_length=255, blank=True, default="")
    tenant_id = models.CharField(max_length=128)
    client_id = models.CharField(max_length=128)
    certificate_thumbprint = models.CharField(max_length=64, blank=True, default="")
    is_active = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_name", "tenant_id", "client_id", "external_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant_id", "client_id"],
                name="portal_zt_prof_tenant_cli_uq",
            )
        ]
        indexes = [
            models.Index(fields=["tenant_id"], name="portal_zt_prof_tenant_idx"),
            models.Index(fields=["last_run_at"], name="portal_zt_prof_lastrun_idx"),
        ]

    def __str__(self) -> str:
        return self.display_name or self.tenant_id

    def to_portal_dict(self) -> dict[str, object]:
        return {
            "id": self.external_id,
            "displayName": self.display_name,
            "tenantId": self.tenant_id,
            "clientId": self.client_id,
            "certificateThumbprint": self.certificate_thumbprint,
            "isActive": self.is_active,
            "lastRunAt": self.last_run_at.isoformat() if self.last_run_at else "",
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


class ZeroTrustCertificate(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    profile = models.ForeignKey(
        ZeroTrustTenantProfile,
        on_delete=models.CASCADE,
        related_name="certificates",
    )
    thumbprint = models.CharField(max_length=64)
    subject = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=128, default="")
    not_before = models.DateTimeField()
    not_after = models.DateTimeField()
    key_algorithm = models.CharField(max_length=64, default="RSA")
    key_size = models.PositiveIntegerField(default=2048)
    public_certificate_der = models.BinaryField()
    pfx_bytes = models.BinaryField(default=b"", blank=True)
    is_current = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "external_id"]
        constraints = [
            models.UniqueConstraint(
                fields=["profile", "thumbprint"],
                name="portal_zt_cert_prof_thumb_uq",
            )
        ]
        indexes = [
            models.Index(fields=["profile", "is_current"], name="portal_zt_cert_current_idx"),
            models.Index(fields=["not_after"], name="portal_zt_cert_expiry_idx"),
        ]

    def __str__(self) -> str:
        return self.thumbprint

    def to_portal_dict(self) -> dict[str, object]:
        return {
            "id": self.external_id,
            "profileId": self.profile.external_id,
            "thumbprint": self.thumbprint,
            "subject": self.subject,
            "serialNumber": self.serial_number,
            "notBefore": self.not_before.isoformat(),
            "notAfter": self.not_after.isoformat(),
            "keyAlgorithm": self.key_algorithm,
            "keySize": self.key_size,
            "isCurrent": self.is_current,
            "createdAt": self.created_at.isoformat(),
        }


class ZeroTrustAssessmentRun(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    profile = models.ForeignKey(
        ZeroTrustTenantProfile,
        on_delete=models.CASCADE,
        related_name="assessment_runs",
    )
    certificate = models.ForeignKey(
        ZeroTrustCertificate,
        on_delete=models.SET_NULL,
        related_name="assessment_runs",
        blank=True,
        null=True,
    )
    status = models.CharField(
        max_length=32,
        choices=ZeroTrustRunStatus.choices,
        default=ZeroTrustRunStatus.QUEUED,
    )
    status_message = models.TextField(blank=True, default="")
    warning_summary = models.TextField(blank=True, default="")
    error_summary = models.TextField(blank=True, default="")
    worker_id = models.CharField(max_length=128, blank=True, default="")
    attempt_count = models.PositiveIntegerField(default=0)
    exit_code = models.IntegerField(blank=True, null=True)
    claimed_at = models.DateTimeField(blank=True, null=True)
    lease_expires_at = models.DateTimeField(blank=True, null=True)
    last_heartbeat_at = models.DateTimeField(blank=True, null=True)
    started_at = models.DateTimeField(blank=True, null=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    ingested_at = models.DateTimeField(blank=True, null=True)
    entrypoint_relative_path = models.CharField(max_length=512, blank=True, default="")
    module_version = models.CharField(max_length=64, blank=True, default="")
    powershell_version = models.CharField(max_length=64, blank=True, default="")
    input_snapshot = models.JSONField(default=dict, blank=True)
    summary_json = models.JSONField(default=dict, blank=True)
    requested_by = models.CharField(max_length=255, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "external_id"]
        indexes = [
            models.Index(fields=["profile", "created_at"], name="portal_zt_run_prof_cr_idx"),
            models.Index(fields=["profile", "status"], name="portal_zt_run_prof_stat_idx"),
            models.Index(fields=["status", "created_at"], name="portal_zt_run_stat_cr_idx"),
            models.Index(fields=["completed_at"], name="portal_zt_run_done_idx"),
        ]

    def __str__(self) -> str:
        return self.external_id

    @property
    def has_report(self) -> bool:
        return bool(self.entrypoint_relative_path)

    def to_portal_dict(self) -> dict[str, object]:
        return {
            "id": self.external_id,
            "profileId": self.profile.external_id,
            "certificateId": self.certificate.external_id if self.certificate_id else "",
            "status": self.status,
            "statusLabel": self.get_status_display(),
            "statusMessage": self.status_message,
            "warningSummary": self.warning_summary,
            "errorSummary": self.error_summary,
            "workerId": self.worker_id,
            "attemptCount": self.attempt_count,
            "exitCode": self.exit_code,
            "claimedAt": self.claimed_at.isoformat() if self.claimed_at else "",
            "leaseExpiresAt": self.lease_expires_at.isoformat() if self.lease_expires_at else "",
            "lastHeartbeatAt": self.last_heartbeat_at.isoformat() if self.last_heartbeat_at else "",
            "startedAt": self.started_at.isoformat() if self.started_at else "",
            "completedAt": self.completed_at.isoformat() if self.completed_at else "",
            "ingestedAt": self.ingested_at.isoformat() if self.ingested_at else "",
            "entrypointRelativePath": self.entrypoint_relative_path,
            "moduleVersion": self.module_version,
            "powershellVersion": self.powershell_version,
            "inputSnapshot": self.input_snapshot,
            "summary": self.summary_json,
            "requestedBy": self.requested_by,
            "hasReport": self.has_report,
            "createdAt": self.created_at.isoformat(),
            "updatedAt": self.updated_at.isoformat(),
        }


class ZeroTrustAssessmentRunLog(models.Model):
    run = models.ForeignKey(
        ZeroTrustAssessmentRun,
        on_delete=models.CASCADE,
        related_name="logs",
    )
    sequence = models.PositiveIntegerField()
    level = models.CharField(max_length=16, default="info")
    stream = models.CharField(max_length=16, default="system")
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["run_id", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "sequence"],
                name="portal_zt_run_log_seq_uq",
            )
        ]
        indexes = [
            models.Index(fields=["run", "created_at"], name="portal_zt_run_log_cr_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.run.external_id}:{self.sequence}"

    def to_portal_dict(self) -> dict[str, object]:
        return {
            "sequence": self.sequence,
            "level": self.level,
            "stream": self.stream,
            "message": self.message,
            "createdAt": self.created_at.isoformat(),
        }


class ZeroTrustAssessmentArtifact(models.Model):
    run = models.ForeignKey(
        ZeroTrustAssessmentRun,
        on_delete=models.CASCADE,
        related_name="artifacts",
    )
    relative_path = models.CharField(max_length=512)
    artifact_type = models.CharField(max_length=32, default="file")
    content_type = models.CharField(max_length=255, default="application/octet-stream")
    size_bytes = models.BigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, default="")
    is_entrypoint = models.BooleanField(default=False)
    content = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["relative_path"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "relative_path"],
                name="portal_zt_artifact_path_uq",
            )
        ]
        indexes = [
            models.Index(fields=["run", "is_entrypoint"], name="portal_zt_artifact_entry_idx"),
        ]

    def __str__(self) -> str:
        return self.relative_path
