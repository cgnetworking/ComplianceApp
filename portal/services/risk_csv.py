from __future__ import annotations

import csv
import io
import uuid

from .common import ValidationError, normalize_string

RISK_CSV_REQUIRED_FIELDS = ("risk", "probability", "impact", "date", "owner")
RISK_CSV_EXPORT_COLUMNS = (
    "id",
    "risk",
    "probability",
    "impact",
    "initialRiskLevel",
    "date",
    "owner",
    "createdBy",
    "closedDate",
    "createdAt",
    "updatedAt",
)
RISK_CSV_IMPORT_ALIASES = {
    "id": ("id", "riskid", "externalid"),
    "risk": ("risk", "description", "riskdescription"),
    "probability": ("probability", "likelihood"),
    "impact": ("impact", "severity"),
    "initialRiskLevel": ("initialrisklevel", "score", "risklevel"),
    "date": ("date", "raiseddate", "riskdate"),
    "owner": ("owner", "riskowner"),
    "createdBy": ("createdby", "creator"),
    "closedDate": ("closeddate", "riskcloseddate"),
    "createdAt": ("createdat",),
    "updatedAt": ("updatedat",),
}


def _normalize_csv_column(value: object) -> str:
    return "".join(character for character in str(value or "").strip().lower() if character.isalnum())


def _csv_row_lookup(row: dict[str, str], field: str) -> str:
    aliases = RISK_CSV_IMPORT_ALIASES.get(field, ())
    for alias in aliases:
        value = normalize_string(row.get(alias))
        if value:
            return value
    return ""


def _parse_required_int(value: str, *, field: str, row_number: int, minimum: int, maximum: int) -> int:
    normalized = normalize_string(value)
    if not normalized:
        raise ValidationError(f"Row {row_number}: {field} is required.")

    try:
        parsed = int(normalized)
    except ValueError as error:
        raise ValidationError(f"Row {row_number}: {field} must be an integer.") from error

    if parsed < minimum or parsed > maximum:
        raise ValidationError(f"Row {row_number}: {field} must be between {minimum} and {maximum}.")
    return parsed


def _parse_optional_int(value: str, *, field: str, row_number: int, minimum: int, maximum: int) -> int | None:
    normalized = normalize_string(value)
    if not normalized:
        return None

    try:
        parsed = int(normalized)
    except ValueError as error:
        raise ValidationError(f"Row {row_number}: {field} must be an integer.") from error

    if parsed < minimum or parsed > maximum:
        raise ValidationError(f"Row {row_number}: {field} must be between {minimum} and {maximum}.")
    return parsed


def parse_risk_csv_text(value: object) -> list[dict[str, object]]:
    csv_text = str(value or "")
    if not csv_text.strip():
        raise ValidationError("Risk CSV import is empty.")

    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValidationError("Risk CSV import must include a header row.")

    normalized_header_fields = {
        _normalize_csv_column(field_name.lstrip("\ufeff"))
        for field_name in reader.fieldnames
        if _normalize_csv_column(field_name.lstrip("\ufeff"))
    }

    missing = []
    for required_field in RISK_CSV_REQUIRED_FIELDS:
        aliases = RISK_CSV_IMPORT_ALIASES[required_field]
        if not any(alias in normalized_header_fields for alias in aliases):
            missing.append(required_field)
    if missing:
        raise ValidationError(
            "Risk CSV import is missing required columns: " + ", ".join(missing) + "."
        )

    records: list[dict[str, object]] = []
    for row_number, raw_row in enumerate(reader, start=2):
        normalized_row = {
            _normalize_csv_column(str(column_name or "").lstrip("\ufeff")): normalize_string(raw_value)
            for column_name, raw_value in (raw_row or {}).items()
            if _normalize_csv_column(str(column_name or "").lstrip("\ufeff"))
        }
        if not any(normalized_row.values()):
            continue

        risk_text = _csv_row_lookup(normalized_row, "risk")
        if not risk_text:
            raise ValidationError(f"Row {row_number}: risk is required.")

        raised_date = _csv_row_lookup(normalized_row, "date")
        if not raised_date:
            raise ValidationError(f"Row {row_number}: date is required.")

        owner = _csv_row_lookup(normalized_row, "owner")
        if not owner:
            raise ValidationError(f"Row {row_number}: owner is required.")

        probability = _parse_required_int(
            _csv_row_lookup(normalized_row, "probability"),
            field="probability",
            row_number=row_number,
            minimum=1,
            maximum=5,
        )
        impact = _parse_required_int(
            _csv_row_lookup(normalized_row, "impact"),
            field="impact",
            row_number=row_number,
            minimum=1,
            maximum=5,
        )

        record: dict[str, object] = {
            "id": _csv_row_lookup(normalized_row, "id") or f"risk-import-{uuid.uuid4().hex[:12]}",
            "risk": risk_text,
            "probability": probability,
            "impact": impact,
            "date": raised_date,
            "owner": owner,
        }

        initial_risk_level = _parse_optional_int(
            _csv_row_lookup(normalized_row, "initialRiskLevel"),
            field="initialRiskLevel",
            row_number=row_number,
            minimum=1,
            maximum=25,
        )
        if initial_risk_level is not None:
            record["initialRiskLevel"] = initial_risk_level

        created_by = _csv_row_lookup(normalized_row, "createdBy")
        if created_by:
            record["createdBy"] = created_by

        closed_date = _csv_row_lookup(normalized_row, "closedDate")
        if closed_date:
            record["closedDate"] = closed_date

        created_at = _csv_row_lookup(normalized_row, "createdAt")
        if created_at:
            record["createdAt"] = created_at

        updated_at = _csv_row_lookup(normalized_row, "updatedAt")
        if updated_at:
            record["updatedAt"] = updated_at

        records.append(record)

    if not records:
        raise ValidationError("Risk CSV import must include at least one populated row.")
    return records


def serialize_risk_records_to_csv(records: list[dict[str, object]]) -> str:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(RISK_CSV_EXPORT_COLUMNS), lineterminator="\r\n")
    writer.writeheader()

    for record in records:
        row = {
            "id": record.get("id") or "",
            "risk": record.get("risk") or "",
            "probability": record.get("probability") or "",
            "impact": record.get("impact") or "",
            "initialRiskLevel": record.get("initialRiskLevel") or "",
            "date": record.get("date") or "",
            "owner": record.get("owner") or "",
            "createdBy": record.get("createdBy") or "",
            "closedDate": record.get("closedDate") or "",
            "createdAt": record.get("createdAt") or "",
            "updatedAt": record.get("updatedAt") or "",
        }
        writer.writerow(row)

    return stream.getvalue()


__all__ = [
    "parse_risk_csv_text",
    "serialize_risk_records_to_csv",
    "RISK_CSV_EXPORT_COLUMNS",
    "RISK_CSV_REQUIRED_FIELDS",
    "ValidationError",
]
