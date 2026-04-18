from django.contrib import admin

from .models import (
    PortalPermissionGrant,
    PortalState,
    ReviewChecklistItem,
    ReviewChecklistRecommendation,
    RiskRecord,
    UploadedPolicy,
    VendorResponse,
    ZeroTrustAssessmentArtifact,
    ZeroTrustAssessmentRun,
    ZeroTrustAssessmentRunLog,
    ZeroTrustCertificate,
    ZeroTrustTenantProfile,
)


@admin.register(PortalPermissionGrant)
class PortalPermissionGrantAdmin(admin.ModelAdmin):
    list_display = ("resource", "action", "user", "group", "enabled", "updated_at")
    list_filter = ("resource", "action", "enabled")
    search_fields = ("name", "description", "user__username", "group__name")


@admin.register(UploadedPolicy)
class UploadedPolicyAdmin(admin.ModelAdmin):
    list_display = ("document_id", "title", "uploaded_at")
    search_fields = ("document_id", "title", "original_filename")


@admin.register(VendorResponse)
class VendorResponseAdmin(admin.ModelAdmin):
    list_display = ("vendor_name", "file_name", "status", "imported_at")
    search_fields = ("vendor_name", "file_name", "summary")


@admin.register(RiskRecord)
class RiskRecordAdmin(admin.ModelAdmin):
    list_display = ("external_id", "owner", "probability", "impact", "initial_risk_level", "date", "closed_date")
    search_fields = ("external_id", "owner", "risk")


@admin.register(ReviewChecklistItem)
class ReviewChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("external_id", "category", "frequency", "start_date", "owner", "updated_at")
    search_fields = ("external_id", "category", "item", "frequency", "owner")


@admin.register(ReviewChecklistRecommendation)
class ReviewChecklistRecommendationAdmin(admin.ModelAdmin):
    list_display = ("external_id", "category", "frequency", "start_date", "owner", "updated_at")
    search_fields = ("external_id", "category", "item", "frequency", "owner")


@admin.register(PortalState)
class PortalStateAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")


@admin.register(ZeroTrustTenantProfile)
class ZeroTrustTenantProfileAdmin(admin.ModelAdmin):
    list_display = ("display_name", "tenant_id", "client_id", "certificate_thumbprint", "last_run_at", "updated_at")
    search_fields = ("display_name", "tenant_id", "client_id", "certificate_thumbprint")


@admin.register(ZeroTrustCertificate)
class ZeroTrustCertificateAdmin(admin.ModelAdmin):
    list_display = ("profile", "thumbprint", "subject", "not_after", "is_current", "created_at")
    search_fields = ("thumbprint", "subject", "serial_number", "profile__tenant_id", "profile__client_id")


@admin.register(ZeroTrustAssessmentRun)
class ZeroTrustAssessmentRunAdmin(admin.ModelAdmin):
    list_display = ("external_id", "profile", "status", "started_at", "completed_at", "requested_by", "worker_id")
    search_fields = ("external_id", "profile__tenant_id", "profile__client_id", "requested_by", "worker_id")


@admin.register(ZeroTrustAssessmentRunLog)
class ZeroTrustAssessmentRunLogAdmin(admin.ModelAdmin):
    list_display = ("run", "sequence", "level", "stream", "created_at")
    search_fields = ("run__external_id", "message")


@admin.register(ZeroTrustAssessmentArtifact)
class ZeroTrustAssessmentArtifactAdmin(admin.ModelAdmin):
    list_display = ("run", "relative_path", "content_type", "size_bytes", "is_entrypoint", "created_at")
    search_fields = ("run__external_id", "relative_path", "content_type", "sha256")
