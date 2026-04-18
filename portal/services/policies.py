from __future__ import annotations

import uuid

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.db import transaction
from django.utils import timezone

from ..authorization import PortalAction, PortalResource, has_portal_permission, restrict_queryset
from ..contracts import (
    serialize_review_checklist_item,
    serialize_review_checklist_recommendation,
    serialize_uploaded_policy,
    serialize_vendor_response,
)
from ..models import UploadedPolicy, VendorResponse
from .common import (
    PENDING_POLICY_APPROVER,
    ValidationError,
    get_state_payload,
    normalize_string,
    normalize_review_state,
    set_state_payload,
)
from .mapping import get_mapping_payload
from .uploads import (
    SUPPORTED_POLICY_EXTENSIONS,
    build_preview_text,
    decode_upload,
    extract_purpose_from_markdown,
    file_extension,
    file_name_base,
    format_uploaded_policy_id,
    infer_vendor_name,
    is_text_like_file,
    markdown_to_html,
    sanitize_uploaded_html,
    summarize_vendor_survey,
)


def serialize_policy_document_payload(document: dict[str, object], *, include_content: bool) -> dict[str, object]:
    payload = dict(document) if isinstance(document, dict) else {}
    content_html = normalize_string(payload.get("contentHtml"))
    payload["contentAvailable"] = bool(content_html)
    payload["contentLoaded"] = include_content
    payload["contentHtml"] = content_html if include_content else ""
    return payload


def get_mapping_bootstrap_payload(*, include_document_content: bool) -> dict[str, object]:
    mapping_payload = get_mapping_payload()
    mapping_documents = [
        serialize_policy_document_payload(item, include_content=include_document_content)
        for item in mapping_payload.get("documents", [])
        if isinstance(item, dict)
    ]
    next_payload = dict(mapping_payload)
    next_payload["documents"] = mapping_documents
    return next_payload


def list_uploaded_documents(*, include_content: bool, viewer: object | None = None) -> list[dict[str, object]]:
    return [
        serialize_policy_document_payload(serialize_uploaded_policy(item), include_content=include_content)
        for item in restrict_queryset(
            UploadedPolicy.objects.all(),
            viewer,
            PortalAction.VIEW,
            resource=PortalResource.POLICY_DOCUMENT,
        )
    ]


def get_policy_document(
    document_id: str,
    *,
    include_content: bool = True,
    viewer: object | None = None,
) -> dict[str, object]:
    normalized_id = normalize_string(document_id)
    if not normalized_id:
        raise ValidationError("Policy id is required.")

    try:
        uploaded = UploadedPolicy.objects.get(document_id=normalized_id)
    except UploadedPolicy.DoesNotExist:
        uploaded = None

    if uploaded is not None:
        if viewer is not None and not has_portal_permission(viewer, PortalResource.POLICY_DOCUMENT, PortalAction.VIEW):
            raise ValidationError("You do not have permission to access this policy document.")
        return serialize_policy_document_payload(serialize_uploaded_policy(uploaded), include_content=include_content)

    mapping_payload = get_mapping_payload()
    mapping_documents = mapping_payload.get("documents")
    if isinstance(mapping_documents, list):
        for item in mapping_documents:
            if not isinstance(item, dict):
                continue
            if normalize_string(item.get("id")) == normalized_id:
                if viewer is not None and not (
                    has_portal_permission(viewer, PortalResource.MAPPING, PortalAction.VIEW)
                    or has_portal_permission(viewer, PortalResource.POLICY_DOCUMENT, PortalAction.VIEW)
                ):
                    raise ValidationError("You do not have permission to access this policy document.")
                return serialize_policy_document_payload(item, include_content=include_content)

    raise ValidationError("Policy document was not found.")


def resolve_assignable_username(identifier: str) -> str:
    normalized_identifier = normalize_string(identifier)
    if not normalized_identifier:
        return ""

    user_model = get_user_model()
    username_field = getattr(user_model, "USERNAME_FIELD", "username")
    user = user_model.objects.filter(is_active=True).filter(**{f"{username_field}__iexact": normalized_identifier}).first()
    if user is None:
        has_email_field = any(getattr(field, "name", "") == "email" for field in user_model._meta.get_fields())
        if has_email_field:
            user = user_model.objects.filter(is_active=True, email__iexact=normalized_identifier).first()
    if user is None:
        return ""

    return normalize_string(getattr(user, username_field, ""))


def normalize_policy_approver_value(value: object) -> str:
    normalized = normalize_string(value)
    if not normalized:
        return PENDING_POLICY_APPROVER
    if normalized.lower() == PENDING_POLICY_APPROVER.lower():
        return PENDING_POLICY_APPROVER

    resolved_username = resolve_assignable_username(normalized)
    normalized_value = resolved_username or normalized
    if len(normalized_value) > 255:
        raise ValidationError("Approver value is too long.")
    return normalized_value


def list_review_checklist_items(*, viewer: object | None = None) -> list[dict[str, str]]:
    from ..models import ReviewChecklistItem

    return [
        serialize_review_checklist_item(item)
        for item in restrict_queryset(
            ReviewChecklistItem.objects.all(),
            viewer,
            PortalAction.VIEW,
            resource=PortalResource.REVIEW_STATE,
        )
    ]


def list_review_checklist_recommendations(*, viewer: object | None = None) -> list[dict[str, str]]:
    from ..models import ReviewChecklistRecommendation

    return [
        serialize_review_checklist_recommendation(item)
        for item in restrict_queryset(
            ReviewChecklistRecommendation.objects.all(),
            viewer,
            PortalAction.VIEW,
            resource=PortalResource.REVIEW_STATE,
        )
    ]


def create_uploaded_policies(files: list[UploadedFile]) -> tuple[list[dict[str, object]], list[str]]:
    created_items: list[UploadedPolicy] = []
    messages: list[str] = []

    for uploaded_file in files:
        extension = file_extension(uploaded_file.name)
        if extension not in SUPPORTED_POLICY_EXTENSIONS:
            messages.append(
                f"{uploaded_file.name} was skipped because only markdown, text, and HTML files are supported."
            )
            continue

        raw_text = decode_upload(
            uploaded_file,
            max_bytes=int(settings.POLICY_UPLOAD_MAX_FILE_BYTES),
        )
        content_html = sanitize_uploaded_html(raw_text) if extension in {"html", "htm"} else markdown_to_html(raw_text)
        policy = UploadedPolicy.objects.create(
            document_id=f"UPL-TEMP-{uuid.uuid4().hex[:12]}",
            title=file_name_base(uploaded_file.name),
            document_type="Uploaded policy",
            approver=PENDING_POLICY_APPROVER,
            review_frequency="Not scheduled",
            path=f"Portal upload / {uploaded_file.name}",
            folder="Uploaded",
            purpose=extract_purpose_from_markdown(raw_text) or f"Uploaded from {uploaded_file.name}.",
            content_html=content_html or "<p>No content was found in the uploaded file.</p>",
            raw_text=raw_text,
            original_filename=uploaded_file.name,
        )
        policy.document_id = format_uploaded_policy_id(policy.pk or 0)
        policy.save(update_fields=["document_id"])
        created_items.append(policy)

    if not created_items and messages:
        raise ValidationError(messages[0])

    return [serialize_uploaded_policy(item) for item in created_items], messages


def delete_uploaded_policy(document_id: str) -> dict[str, object]:
    normalized_id = normalize_string(document_id)
    if not normalized_id:
        raise ValidationError("Policy id is required.")

    try:
        policy = UploadedPolicy.objects.get(document_id=normalized_id)
    except UploadedPolicy.DoesNotExist as error:
        raise ValidationError("Uploaded policy was not found.") from error

    deleted_payload = serialize_uploaded_policy(policy)
    policy.delete()
    return deleted_payload


def update_uploaded_policy_approver(document_id: str, approver: object) -> dict[str, object]:
    normalized_id = normalize_string(document_id)
    if not normalized_id:
        raise ValidationError("Policy id is required.")

    try:
        policy = UploadedPolicy.objects.get(document_id=normalized_id)
    except UploadedPolicy.DoesNotExist as error:
        raise ValidationError("Uploaded policy was not found.") from error

    next_approver = normalize_policy_approver_value(approver)
    update_fields = []
    if normalize_string(policy.approver).lower() != next_approver.lower():
        policy.approver = next_approver
        policy.approved_by = ""
        policy.approved_at = None
        update_fields.extend(["approver", "approved_by", "approved_at"])
    elif policy.approver != next_approver:
        policy.approver = next_approver
        update_fields.append("approver")
    if update_fields:
        policy.save(update_fields=update_fields)
    return serialize_uploaded_policy(policy)


def approve_uploaded_policy(
    document_id: str,
    *,
    actor_username: str,
    actor_display_name: str,
) -> tuple[dict[str, object], dict[str, object]]:
    from .bootstrap import append_review_state_audit_entries, build_policy_approval_audit_entry

    normalized_id = normalize_string(document_id)
    if not normalized_id:
        raise ValidationError("Policy id is required.")

    normalized_actor_username = normalize_string(actor_username)
    if not normalized_actor_username:
        raise ValidationError("A valid approver is required.")

    with transaction.atomic():
        try:
            policy = UploadedPolicy.objects.select_for_update().get(document_id=normalized_id)
        except UploadedPolicy.DoesNotExist as error:
            raise ValidationError("Uploaded policy was not found.") from error

        assigned_approver = normalize_policy_approver_value(policy.approver)
        if assigned_approver == PENDING_POLICY_APPROVER:
            raise ValidationError("This policy is not assigned to an approver.")
        if assigned_approver.lower() != normalized_actor_username.lower():
            raise ValidationError("Only the assigned approver can approve this policy.")

        if policy.approved_at:
            review_state = normalize_review_state(get_state_payload("review_state", {}))
            return serialize_uploaded_policy(policy), review_state

        approval_time = timezone.now()
        policy.approved_by = normalized_actor_username
        policy.approved_at = approval_time
        policy.save(update_fields=["approved_by", "approved_at"])

    review_state = append_review_state_audit_entries(
        [
            build_policy_approval_audit_entry(
                policy,
                actor_username=normalized_actor_username,
                actor_display_name=normalize_string(actor_display_name),
                occurred_at=approval_time,
            )
        ]
    )
    return serialize_uploaded_policy(policy), review_state


def create_vendor_responses(files: list[UploadedFile]) -> list[dict[str, object]]:
    created_items: list[VendorResponse] = []

    for uploaded_file in files:
        extension = file_extension(uploaded_file.name)
        raw_text = (
            decode_upload(
                uploaded_file,
                max_bytes=int(settings.VENDOR_UPLOAD_MAX_FILE_BYTES),
            ).replace("\x00", "").strip()
            if is_text_like_file(uploaded_file, extension)
            else ""
        )
        preview_text = build_preview_text(raw_text, 1400, 20)
        response = VendorResponse.objects.create(
            external_id=f"vendor-{uuid.uuid4().hex[:16]}",
            vendor_name=infer_vendor_name(uploaded_file.name, raw_text, extension),
            file_name=uploaded_file.name,
            extension=extension or "file",
            mime_type=uploaded_file.content_type or "Unknown",
            file_size=uploaded_file.size or 0,
            preview_text=preview_text,
            summary=summarize_vendor_survey(uploaded_file.name, raw_text, extension, preview_text),
            status="Preview ready" if preview_text else "Metadata only",
            raw_text=raw_text,
        )
        created_items.append(response)

    return [serialize_vendor_response(item) for item in created_items]


def list_vendor_responses(*, viewer: object | None = None) -> list[dict[str, object]]:
    return [
        serialize_vendor_response(item)
        for item in restrict_queryset(
            VendorResponse.objects.all(),
            viewer,
            PortalAction.VIEW,
            resource=PortalResource.VENDOR_RESPONSE,
        )
    ]


def delete_vendor_response(response_id: str) -> dict[str, object]:
    normalized_id = normalize_string(response_id)
    if not normalized_id:
        raise ValidationError("Vendor response id is required.")

    try:
        response = VendorResponse.objects.get(external_id=normalized_id)
    except VendorResponse.DoesNotExist as error:
        raise ValidationError("Vendor response was not found.") from error

    deleted_payload = serialize_vendor_response(response)
    response.delete()
    return deleted_payload


__all__ = [
    "ValidationError",
    "serialize_policy_document_payload",
    "get_mapping_bootstrap_payload",
    "list_uploaded_documents",
    "get_policy_document",
    "resolve_assignable_username",
    "normalize_policy_approver_value",
    "list_review_checklist_items",
    "list_review_checklist_recommendations",
    "create_uploaded_policies",
    "delete_uploaded_policy",
    "update_uploaded_policy_approver",
    "approve_uploaded_policy",
    "create_vendor_responses",
    "list_vendor_responses",
    "delete_vendor_response",
]
