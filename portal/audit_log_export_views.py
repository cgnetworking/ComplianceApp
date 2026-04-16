from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from .services.bootstrap import append_portal_audit_entry
from .services.audit_log_exports import build_review_state_audit_log_export
from .views import api_login_required, policy_reader_api_access


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def audit_log_export_csv(request: HttpRequest) -> HttpResponse:
    file_name, csv_content = build_review_state_audit_log_export()
    username = request.user.get_username() if request.user.is_authenticated else ""
    display_name = request.user.get_full_name().strip() if request.user.is_authenticated else ""
    append_portal_audit_entry(
        action="export_audit_log",
        entity_type="audit_log",
        entity_id="review_state",
        summary=f"Exported audit log file {file_name}.",
        actor_username=username or "system",
        actor_display_name=display_name or username or "System",
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
