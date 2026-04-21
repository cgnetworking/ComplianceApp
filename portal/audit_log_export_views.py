from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from .authorization import PortalAction, PortalResource, has_portal_permission
from .services.bootstrap import append_portal_audit_entry
from .services.audit_log_exports import build_portal_audit_log_export
from .view_helpers import api_login_required, current_audit_actor, portal_api_forbidden_response


@api_login_required
@require_GET
def audit_log_export_csv(request: HttpRequest) -> HttpResponse:
    if not has_portal_permission(request.user, PortalResource.AUDIT_LOG, PortalAction.EXPORT):
        return portal_api_forbidden_response("You do not have permission to export the audit log.")
    file_name, csv_content = build_portal_audit_log_export()
    username, display_name = current_audit_actor(request)
    append_portal_audit_entry(
        action="export_audit_log",
        entity_type="audit_log",
        entity_id="audit_log",
        summary=f"Exported audit log file {file_name}.",
        actor_username=username,
        actor_display_name=display_name,
        metadata={
            "source": "audit-log",
            "exportType": "audit_log_csv",
            "fileName": file_name,
        },
    )
    response = HttpResponse(csv_content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    response["Cache-Control"] = "no-store"
    return response
