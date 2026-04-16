from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.views.decorators.http import require_GET

from .services.audit_log_exports import build_review_state_audit_log_export
from .views import api_login_required, policy_reader_api_access


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def audit_log_export_csv(request: HttpRequest) -> HttpResponse:
    file_name, csv_content = build_review_state_audit_log_export()
    response = HttpResponse(csv_content, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{file_name}"'
    response["Cache-Control"] = "no-store"
    return response
