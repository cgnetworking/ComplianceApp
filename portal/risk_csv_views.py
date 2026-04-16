from __future__ import annotations

from datetime import date

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from .services.risk_csv import serialize_risk_records_to_csv
from .services.risks import ValidationError, list_risk_register, replace_risk_register
from .views import api_login_required, parse_json_body_or_400, policy_reader_api_access


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def risk_register_csv_export(request: HttpRequest) -> HttpResponse:
    csv_payload = serialize_risk_records_to_csv(list_risk_register())
    response = HttpResponse(csv_payload, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="risk-register-{date.today().isoformat()}.csv"'
    return response


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_http_methods(["POST"])
def risk_register_csv_import(request: HttpRequest) -> JsonResponse:
    body, error_response = parse_json_body_or_400(request)
    if error_response is not None:
        return error_response

    if isinstance(body, dict):
        csv_payload = body.get("csv") or body.get("riskCsv") or body.get("content")
    else:
        csv_payload = body

    if not isinstance(csv_payload, str) or not csv_payload.strip():
        return JsonResponse({"detail": "Risk CSV content is required."}, status=400)

    try:
        risk_register_payload = replace_risk_register(csv_payload)
    except ValidationError as error:
        return JsonResponse({"detail": str(error)}, status=400)

    return JsonResponse({"riskRegister": risk_register_payload})


__all__ = [
    "risk_register_csv_export",
    "risk_register_csv_import",
]
