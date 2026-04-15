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
    owner = models.CharField(max_length=255, default="Shared portal")
    approver = models.CharField(max_length=255, default="Pending review")
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
            "owner": self.owner,
            "approver": self.approver,
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
