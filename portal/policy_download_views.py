from __future__ import annotations

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET

from .services.bootstrap import append_portal_audit_entry
from .services.policy_downloads import (
    ValidationError,
    build_all_policies_download,
    build_attachment_content_disposition,
    build_policy_document_download,
)
from .view_helpers import api_login_required, current_audit_actor, policy_reader_api_access


def policy_download_actor(request: HttpRequest) -> tuple[str, str]:
    return current_audit_actor(request)


@api_login_required
@policy_reader_api_access(allow_policy_reader=True)
@require_GET
def policy_document_download(request: HttpRequest, document_id: str) -> HttpResponse:
    try:
        artifact = build_policy_document_download(document_id)
    except ValidationError as error:
        detail = str(error)
        status_code = 404 if detail == "Policy document was not found." else 400
        return JsonResponse({"detail": detail}, status=status_code)

    response = HttpResponse(artifact.content, content_type=artifact.content_type)
    response["Content-Disposition"] = build_attachment_content_disposition(artifact.filename)
    response["X-Content-Type-Options"] = "nosniff"

    actor_username, actor_display_name = policy_download_actor(request)
    append_portal_audit_entry(
        action="export_policy_document",
        entity_type="policy",
        entity_id=document_id,
        summary=f"Exported policy file {artifact.filename}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "policies",
            "exportType": "single_policy",
            "policyId": document_id,
            "fileName": artifact.filename,
        },
    )
    return response


@api_login_required
@policy_reader_api_access(allow_policy_reader=True)
@require_GET
def policy_documents_download_all(request: HttpRequest) -> HttpResponse:
    try:
        artifact = build_all_policies_download()
    except ValidationError as error:
        detail = str(error)
        status_code = 404 if detail == "No policy documents are available for download." else 400
        return JsonResponse({"detail": detail}, status=status_code)

    response = HttpResponse(artifact.content, content_type=artifact.content_type)
    response["Content-Disposition"] = build_attachment_content_disposition(artifact.filename)
    response["X-Content-Type-Options"] = "nosniff"

    actor_username, actor_display_name = policy_download_actor(request)
    append_portal_audit_entry(
        action="export_policy_documents",
        entity_type="policy",
        entity_id="all",
        summary=f"Exported policy archive {artifact.filename}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "policies",
            "exportType": "all_policies",
            "fileName": artifact.filename,
        },
    )
    return response
