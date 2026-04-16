from __future__ import annotations

from datetime import date

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from .services.bootstrap import append_portal_audit_entry
from .services.risk_csv import serialize_risk_records_to_csv
from .services.risks import ValidationError, list_risk_register, replace_risk_register
from .views import api_login_required, parse_json_body_or_400, policy_reader_api_access


def risk_csv_actor(request: HttpRequest) -> tuple[str, str]:
    username = request.user.get_username() if request.user.is_authenticated else ""
    display_name = request.user.get_full_name().strip() if request.user.is_authenticated else ""
    normalized_username = username or "system"
    normalized_display_name = display_name or username or "System"
    return normalized_username, normalized_display_name


@api_login_required
@policy_reader_api_access(allow_policy_reader=False)
@require_GET
def risk_register_csv_export(request: HttpRequest) -> HttpResponse:
    risk_register = list_risk_register()
    csv_payload = serialize_risk_records_to_csv(risk_register)
    export_file_name = f"risk-register-{date.today().isoformat()}.csv"
    response = HttpResponse(csv_payload, content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{export_file_name}"'

    actor_username, actor_display_name = risk_csv_actor(request)
    append_portal_audit_entry(
        action="export_risk_register",
        entity_type="risk_register",
        entity_id=export_file_name,
        summary=f"Exported risk register file {export_file_name}.",
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "risks",
            "exportType": "risk_csv",
            "fileName": export_file_name,
            "recordCount": len(risk_register),
        },
    )
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

    actor_username, actor_display_name = risk_csv_actor(request)
    risk_name_preview = ", ".join(
        [
            str(item.get("risk") or "").strip()
            for item in risk_register_payload
            if isinstance(item, dict) and str(item.get("risk") or "").strip()
        ][:3]
    )
    if len(risk_register_payload) > 3 and risk_name_preview:
        risk_name_preview = f"{risk_name_preview}, +{len(risk_register_payload) - 3} more"
    append_portal_audit_entry(
        action="import_risk_csv",
        entity_type="risk_register",
        entity_id=f"{len(risk_register_payload)}",
        summary=(
            f"Imported risk entries: {risk_name_preview}."
            if risk_name_preview
            else f"Imported risk CSV with {len(risk_register_payload)} risk record{'s' if len(risk_register_payload) != 1 else ''}."
        ),
        actor_username=actor_username,
        actor_display_name=actor_display_name,
        metadata={
            "source": "risks",
            "importType": "risk_csv",
            "recordCount": len(risk_register_payload),
        },
    )

    return JsonResponse({"riskRegister": risk_register_payload})


__all__ = [
    "risk_register_csv_export",
    "risk_register_csv_import",
]
