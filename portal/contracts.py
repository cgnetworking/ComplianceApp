from __future__ import annotations

from .models import (
    PortalAuditLogEntry,
    ReviewChecklistItem,
    ReviewChecklistRecommendation,
    RiskRecord,
    UploadedPolicy,
    VendorResponse,
    ZeroTrustAssessmentRun,
    ZeroTrustAssessmentRunLog,
    ZeroTrustCertificate,
    ZeroTrustTenantProfile,
)


def serialize_uploaded_policy(policy: UploadedPolicy) -> dict[str, object]:
    content_html = policy.content_html or ""
    return {
        "id": policy.document_id,
        "title": policy.title,
        "type": policy.document_type,
        "approver": policy.approver,
        "approvedBy": policy.approved_by,
        "approvedAt": policy.approved_at.isoformat() if policy.approved_at else "",
        "reviewFrequency": policy.review_frequency,
        "path": policy.path,
        "folder": policy.folder,
        "purpose": policy.purpose,
        "contentHtml": content_html,
        "contentAvailable": bool(content_html),
        "contentLoaded": True,
        "isUploaded": True,
        "originalFilename": policy.original_filename,
        "uploadedAt": policy.uploaded_at.isoformat(),
    }


def serialize_vendor_response(response: VendorResponse) -> dict[str, object]:
    return {
        "id": response.external_id,
        "vendorName": response.vendor_name,
        "fileName": response.file_name,
        "extension": response.extension,
        "mimeType": response.mime_type,
        "fileSize": response.file_size,
        "importedAt": response.imported_at.isoformat(),
        "previewText": response.preview_text,
        "summary": response.summary,
        "status": response.status,
    }


def serialize_portal_audit_log_entry(entry: PortalAuditLogEntry) -> dict[str, object]:
    return {
        "id": entry.external_id,
        "action": entry.action,
        "entityType": entry.entity_type,
        "entityId": entry.entity_id,
        "summary": entry.summary,
        "actor": {
            "username": entry.actor_username,
            "displayName": entry.actor_display_name,
        },
        "occurredAt": entry.occurred_at.isoformat(),
        "metadata": entry.metadata if isinstance(entry.metadata, dict) else {},
    }


def serialize_risk_record(record: RiskRecord) -> dict[str, object]:
    score = int(record.probability or 0) * int(record.impact or 0)
    initial_risk_level = score if 1 <= score <= 25 else record.initial_risk_level
    return {
        "id": record.external_id,
        "risk": record.risk,
        "probability": record.probability,
        "impact": record.impact,
        "initialRiskLevel": initial_risk_level,
        "date": record.date.isoformat(),
        "owner": record.owner,
        "createdBy": record.created_by,
        "closedDate": record.closed_date.isoformat() if record.closed_date else "",
        "createdAt": record.created_at.isoformat(),
        "updatedAt": record.updated_at.isoformat(),
    }


def serialize_review_checklist_item(item: ReviewChecklistItem) -> dict[str, str]:
    return {
        "id": item.external_id,
        "category": item.category,
        "item": item.item,
        "frequency": item.frequency,
        "startDate": item.start_date.isoformat() if item.start_date else "",
        "owner": item.owner,
        "createdAt": item.created_at.isoformat(),
    }


def serialize_review_checklist_recommendation(item: ReviewChecklistRecommendation) -> dict[str, str]:
    return {
        "id": item.external_id,
        "category": item.category,
        "item": item.item,
        "frequency": item.frequency,
        "startDate": item.start_date.isoformat() if item.start_date else "",
        "owner": item.owner,
    }


def serialize_zero_trust_tenant_profile(profile: ZeroTrustTenantProfile) -> dict[str, object]:
    return {
        "id": profile.external_id,
        "displayName": profile.display_name,
        "tenantId": profile.tenant_id,
        "clientId": profile.client_id,
        "certificateThumbprint": profile.certificate_thumbprint,
        "isActive": profile.is_active,
        "lastRunAt": profile.last_run_at.isoformat() if profile.last_run_at else "",
        "createdAt": profile.created_at.isoformat(),
        "updatedAt": profile.updated_at.isoformat(),
    }


def serialize_zero_trust_certificate(certificate: ZeroTrustCertificate) -> dict[str, object]:
    return {
        "id": certificate.external_id,
        "profileId": certificate.profile.external_id,
        "thumbprint": certificate.thumbprint,
        "subject": certificate.subject,
        "serialNumber": certificate.serial_number,
        "notBefore": certificate.not_before.isoformat(),
        "notAfter": certificate.not_after.isoformat(),
        "keyAlgorithm": certificate.key_algorithm,
        "keySize": certificate.key_size,
        "isCurrent": certificate.is_current,
        "createdAt": certificate.created_at.isoformat(),
    }


def serialize_zero_trust_run(run: ZeroTrustAssessmentRun) -> dict[str, object]:
    return {
        "id": run.external_id,
        "profileId": run.profile.external_id,
        "certificateId": run.certificate.external_id if run.certificate_id else "",
        "status": run.status,
        "statusLabel": run.get_status_display(),
        "statusMessage": run.status_message,
        "warningSummary": run.warning_summary,
        "errorSummary": run.error_summary,
        "workerId": run.worker_id,
        "attemptCount": run.attempt_count,
        "exitCode": run.exit_code,
        "claimedAt": run.claimed_at.isoformat() if run.claimed_at else "",
        "leaseExpiresAt": run.lease_expires_at.isoformat() if run.lease_expires_at else "",
        "lastHeartbeatAt": run.last_heartbeat_at.isoformat() if run.last_heartbeat_at else "",
        "startedAt": run.started_at.isoformat() if run.started_at else "",
        "completedAt": run.completed_at.isoformat() if run.completed_at else "",
        "ingestedAt": run.ingested_at.isoformat() if run.ingested_at else "",
        "entrypointRelativePath": run.entrypoint_relative_path,
        "moduleVersion": run.module_version,
        "powershellVersion": run.powershell_version,
        "inputSnapshot": run.input_snapshot,
        "summary": run.summary_json,
        "requestedBy": run.requested_by,
        "hasReport": run.has_report,
        "createdAt": run.created_at.isoformat(),
        "updatedAt": run.updated_at.isoformat(),
    }


def serialize_zero_trust_run_log(log: ZeroTrustAssessmentRunLog) -> dict[str, object]:
    return {
        "sequence": log.sequence,
        "level": log.level,
        "stream": log.stream,
        "message": log.message,
        "createdAt": log.created_at.isoformat(),
    }
