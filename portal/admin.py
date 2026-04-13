from django.contrib import admin

from .models import (
    PortalState,
    ReviewChecklistItem,
    ReviewChecklistRecommendation,
    RiskRecord,
    UploadedPolicy,
    VendorResponse,
)


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
    list_display = ("external_id", "owner", "initial_risk_level", "date", "closed_date")
    search_fields = ("external_id", "owner", "risk")


@admin.register(ReviewChecklistItem)
class ReviewChecklistItemAdmin(admin.ModelAdmin):
    list_display = ("external_id", "category", "frequency", "owner", "updated_at")
    search_fields = ("external_id", "category", "item", "frequency", "owner")


@admin.register(ReviewChecklistRecommendation)
class ReviewChecklistRecommendationAdmin(admin.ModelAdmin):
    list_display = ("external_id", "category", "frequency", "owner", "updated_at")
    search_fields = ("external_id", "category", "item", "frequency", "owner")


@admin.register(PortalState)
class PortalStateAdmin(admin.ModelAdmin):
    list_display = ("key", "updated_at")
