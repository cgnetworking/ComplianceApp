from __future__ import annotations

from django.db import transaction

from ..contracts import serialize_risk_record
from ..models import RiskRecord
from .common import ValidationError, normalize_string
from .risk_csv import parse_risk_csv_text
from .risk_validation import RISK_RECORD_MODEL_FIELDS, normalize_risk_record

RISK_RECORD_UPDATE_FIELDS = RISK_RECORD_MODEL_FIELDS + ("created_by",)


def list_risk_register() -> list[dict[str, object]]:
    return [serialize_risk_record(item) for item in RiskRecord.objects.all()]


def risk_record_model_values(record: dict[str, object]) -> dict[str, object]:
    return {
        "risk": record["risk"],
        "probability": record["probability"],
        "impact": record["impact"],
        "initial_risk_level": record["initial_risk_level"],
        "date": record["date"],
        "owner": record["owner"],
        "created_by": normalize_string(record.get("created_by")),
        "closed_date": record["closed_date"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def _payload_created_by(payload: object) -> str:
    if not isinstance(payload, dict):
        return ""
    return normalize_string(payload.get("createdBy"))


def _normalize_risk_record_with_creator(payload: object) -> dict[str, object]:
    normalized = normalize_risk_record(payload)
    requested_created_by = _payload_created_by(payload)
    if not requested_created_by:
        raise ValidationError("Each risk requires createdBy.")
    normalized["created_by"] = requested_created_by
    return normalized


def _prepare_risk_upsert_items(items: object) -> list[object]:
    if isinstance(items, list):
        return items
    if isinstance(items, str):
        return parse_risk_csv_text(items)
    raise ValidationError("Risk register payload must be a list.")


def upsert_risk_register(items: object) -> list[dict[str, object]]:
    records_to_upsert = _prepare_risk_upsert_items(items)

    with transaction.atomic():
        for item in records_to_upsert:
            if not isinstance(item, dict):
                raise ValidationError("Each risk record must be an object.")
            record = _normalize_risk_record_with_creator(item)
            RiskRecord.objects.update_or_create(
                external_id=record["external_id"],
                defaults=risk_record_model_values(record),
            )

    return list_risk_register()


def replace_risk_register(items: object) -> list[dict[str, object]]:
    return upsert_risk_register(items)


def create_risk_record(payload: object) -> dict[str, object]:
    record = _normalize_risk_record_with_creator(payload)
    if RiskRecord.objects.filter(external_id=record["external_id"]).exists():
        raise ValidationError("Risk record already exists.")

    created = RiskRecord.objects.create(
        external_id=record["external_id"],
        **risk_record_model_values(record),
    )
    return serialize_risk_record(created)


def update_risk_record(external_id: str, payload: object) -> dict[str, object]:
    normalized_external_id = normalize_string(external_id)
    if not normalized_external_id:
        raise ValidationError("Risk id is required.")
    if not isinstance(payload, dict):
        raise ValidationError("Risk payload must be an object.")

    try:
        existing = RiskRecord.objects.get(external_id=normalized_external_id)
    except RiskRecord.DoesNotExist as error:
        raise ValidationError("Risk record was not found.") from error

    payload_id = normalize_string(payload.get("id"))
    if payload_id and payload_id != normalized_external_id:
        raise ValidationError("Risk id does not match request path.")

    merged_payload = serialize_risk_record(existing)
    merged_payload.update(payload)
    merged_payload["id"] = normalized_external_id
    normalized_record = _normalize_risk_record_with_creator(merged_payload)
    next_values = risk_record_model_values(normalized_record)

    for field_name in RISK_RECORD_UPDATE_FIELDS:
        setattr(existing, field_name, next_values[field_name])
    existing.save(update_fields=list(RISK_RECORD_UPDATE_FIELDS))
    return serialize_risk_record(existing)


def delete_risk_record(external_id: str) -> dict[str, object]:
    normalized_external_id = normalize_string(external_id)
    if not normalized_external_id:
        raise ValidationError("Risk id is required.")

    try:
        record = RiskRecord.objects.get(external_id=normalized_external_id)
    except RiskRecord.DoesNotExist as error:
        raise ValidationError("Risk record was not found.") from error

    deleted = serialize_risk_record(record)
    record.delete()
    return deleted


__all__ = [
    "list_risk_register",
    "upsert_risk_register",
    "replace_risk_register",
    "create_risk_record",
    "update_risk_record",
    "delete_risk_record",
    "risk_record_model_values",
    "ValidationError",
]
