from __future__ import annotations

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db.models import Q
from django.db import models
from django.utils import timezone

RISK_FACTOR_VALIDATORS = [MinValueValidator(1), MaxValueValidator(5)]
RISK_SCORE_VALIDATORS = [MinValueValidator(1), MaxValueValidator(25)]


class PortalResource(models.TextChoices):
    POLICY_DOCUMENT = "policy_document", "Policy document"
    MAPPING = "mapping", "Mapping"
    CONTROL_STATE = "control_state", "Control state"
    REVIEW_STATE = "review_state", "Review state"
    VENDOR_RESPONSE = "vendor_response", "Vendor response"
    RISK_RECORD = "risk_record", "Risk record"
    AUDIT_LOG = "audit_log", "Audit log"
    ASSESSMENT = "assessment", "Assessment"


class PortalAction(models.TextChoices):
    VIEW = "view", "View"
    ADD = "add", "Add"
    CHANGE = "change", "Change"
    DELETE = "delete", "Delete"
    EXPORT = "export", "Export"
    APPROVE = "approve", "Approve"
    ASSIGN = "assign", "Assign"
    VIEW_RAW = "view_raw", "View raw"


class PortalPermissionGrant(models.Model):
    name = models.CharField(max_length=120, blank=True, default="")
    description = models.TextField(blank=True, default="")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="portal_permission_grants",
    )
    group = models.ForeignKey(
        "auth.Group",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="portal_permission_grants",
    )
    resource = models.CharField(max_length=64, choices=PortalResource.choices)
    action = models.CharField(max_length=32, choices=PortalAction.choices)
    constraints = models.JSONField(default=dict, blank=True)
    enabled = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["resource", "action", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    (Q(group__isnull=True, user__isnull=False))
                    | (Q(group__isnull=False, user__isnull=True))
                ),
                name="portal_perm_one_principal_ck",
            ),
            models.UniqueConstraint(
                fields=["user", "resource", "action"],
                condition=Q(user__isnull=False),
                name="portal_perm_user_uq",
            ),
            models.UniqueConstraint(
                fields=["group", "resource", "action"],
                condition=Q(group__isnull=False),
                name="portal_perm_group_uq",
            ),
        ]

    def __str__(self) -> str:
        principal = ""
        if self.user_id:
            principal = f"user:{self.user_id}"
        elif self.group_id:
            principal = f"group:{self.group_id}"
        return self.name or f"{principal}:{self.resource}:{self.action}"


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
        from .contracts import serialize_uploaded_policy

        return serialize_uploaded_policy(self)


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
        from .contracts import serialize_vendor_response

        return serialize_vendor_response(self)


class RiskRecord(models.Model):
    external_id = models.CharField(max_length=64, unique=True)
    risk = models.TextField()
    probability = models.PositiveSmallIntegerField(default=3, validators=RISK_FACTOR_VALIDATORS)
    impact = models.PositiveSmallIntegerField(default=3, validators=RISK_FACTOR_VALIDATORS)
    initial_risk_level = models.PositiveSmallIntegerField(validators=RISK_SCORE_VALIDATORS)
    date = models.DateField()
    owner = models.CharField(max_length=255)
    created_by = models.CharField(max_length=255, blank=True, default="")
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
        from .contracts import serialize_risk_record

        return serialize_risk_record(self)


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
        from .contracts import serialize_review_checklist_item

        return serialize_review_checklist_item(self)


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
        from .contracts import serialize_review_checklist_recommendation

        return serialize_review_checklist_recommendation(self)


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
        from .contracts import serialize_zero_trust_tenant_profile

        return serialize_zero_trust_tenant_profile(self)


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
    pfx_path = models.CharField(max_length=512, blank=True, default="")
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
        from .contracts import serialize_zero_trust_certificate

        return serialize_zero_trust_certificate(self)


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
        from .contracts import serialize_zero_trust_run

        return serialize_zero_trust_run(self)


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
        from .contracts import serialize_zero_trust_run_log

        return serialize_zero_trust_run_log(self)


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
