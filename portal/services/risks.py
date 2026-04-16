from __future__ import annotations

from django.db import transaction

from ..models import RiskRecord
from .common import (
    RISK_RECORD_MODEL_FIELDS,
    ValidationError,
    normalize_risk_record,
    normalize_string,
)


def list_risk_register() -> list[dict[str, object]]:
    return [item.to_portal_dict() for item in RiskRecord.objects.all()]


def risk_record_model_values(record: dict[str, object]) -> dict[str, object]:
    return {
        "risk": record["risk"],
        "probability": record["probability"],
        "impact": record["impact"],
        "initial_risk_level": record["initial_risk_level"],
        "date": record["date"],
        "owner": record["owner"],
        "closed_date": record["closed_date"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def upsert_risk_register(items: list[object]) -> list[dict[str, object]]:
    if not isinstance(items, list):
        raise ValidationError("Risk register payload must be a list.")

    with transaction.atomic():
        for item in items:
            record = normalize_risk_record(item)
            RiskRecord.objects.update_or_create(
                external_id=record["external_id"],
                defaults=risk_record_model_values(record),
            )

    return list_risk_register()


def replace_risk_register(items: list[object]) -> list[dict[str, object]]:
    return upsert_risk_register(items)


def create_risk_record(payload: object) -> dict[str, object]:
    record = normalize_risk_record(payload)
    if RiskRecord.objects.filter(external_id=record["external_id"]).exists():
        raise ValidationError("Risk record already exists.")

    created = RiskRecord.objects.create(
        external_id=record["external_id"],
        **risk_record_model_values(record),
    )
    return created.to_portal_dict()


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

    merged_payload = existing.to_portal_dict()
    merged_payload.update(payload)
    merged_payload["id"] = normalized_external_id
    normalized_record = normalize_risk_record(merged_payload)
    next_values = risk_record_model_values(normalized_record)

    for field_name in RISK_RECORD_MODEL_FIELDS:
        setattr(existing, field_name, next_values[field_name])
    existing.save(update_fields=list(RISK_RECORD_MODEL_FIELDS))
    return existing.to_portal_dict()


def delete_risk_record(external_id: str) -> dict[str, object]:
    normalized_external_id = normalize_string(external_id)
    if not normalized_external_id:
        raise ValidationError("Risk id is required.")

    try:
        record = RiskRecord.objects.get(external_id=normalized_external_id)
    except RiskRecord.DoesNotExist as error:
        raise ValidationError("Risk record was not found.") from error

    deleted = record.to_portal_dict()
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

