from __future__ import annotations

from .common import (
    ValidationError,
    parse_iso_date,
    parse_iso_datetime,
    parse_optional_iso_date,
)

RISK_RECORD_MODEL_FIELDS = (
    "risk",
    "probability",
    "impact",
    "initial_risk_level",
    "date",
    "owner",
    "closed_date",
    "created_at",
    "updated_at",
)


def normalize_risk_factor(value: object) -> int:
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 0
    return level if 1 <= level <= 5 else 0


def normalize_risk_score(value: object) -> int:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return score if 1 <= score <= 25 else 0


def normalize_risk_record(item: object) -> dict[str, object]:
    if not isinstance(item, dict):
        raise ValidationError("Each risk record must be an object.")

    external_id = str(item.get("id") or "").strip()
    risk_text = str(item.get("risk") or "").strip()
    owner = str(item.get("owner") or "").strip()
    probability = normalize_risk_factor(item.get("probability"))
    impact = normalize_risk_factor(item.get("impact"))
    stated_initial_risk_level = normalize_risk_score(item.get("initialRiskLevel"))
    initial_risk_level = probability * impact
    raised_date = parse_iso_date(item.get("date"))
    closed_date = parse_optional_iso_date(item.get("closedDate"))
    created_at = parse_iso_datetime(item.get("createdAt"))
    updated_at = parse_iso_datetime(item.get("updatedAt"))

    if not external_id or not risk_text or not owner or not probability or not impact:
        raise ValidationError(
            "Each risk requires an id, description, owner, probability, impact, createdAt, updatedAt, and date."
        )
    if stated_initial_risk_level and stated_initial_risk_level != initial_risk_level:
        raise ValidationError("Risk initialRiskLevel must equal probability multiplied by impact.")
    if closed_date and closed_date < raised_date:
        raise ValidationError("Risk closed date cannot be earlier than the raised date.")

    return {
        "external_id": external_id,
        "risk": risk_text,
        "owner": owner,
        "probability": probability,
        "impact": impact,
        "initial_risk_level": initial_risk_level,
        "date": raised_date,
        "closed_date": closed_date,
        "created_at": created_at,
        "updated_at": updated_at,
    }


__all__ = [
    "RISK_RECORD_MODEL_FIELDS",
    "normalize_risk_factor",
    "normalize_risk_score",
    "normalize_risk_record",
    "ValidationError",
]
