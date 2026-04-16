from __future__ import annotations

import json
from pathlib import Path

from django.db import migrations
from django.utils import timezone


def load_json(path: Path) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def seed_default_portal_state(apps, schema_editor) -> None:
    PortalState = apps.get_model("portal", "PortalState")
    ReviewChecklistRecommendation = apps.get_model("portal", "ReviewChecklistRecommendation")

    base_dir = Path(__file__).resolve().parents[2]
    controls_payload = load_json(base_dir / "webapp" / "default_controls.json")
    checklist_payload = load_json(base_dir / "webapp" / "default_review_checklist.json")

    controls = controls_payload if isinstance(controls_payload, list) else []
    checklist = checklist_payload if isinstance(checklist_payload, list) else []

    if controls:
        PortalState.objects.get_or_create(
            key="mapping_state",
            defaults={
                "payload": {
                    "generatedAt": timezone.now().isoformat(),
                    "sourceSnapshot": {
                        "controlRegister": "default_controls.json",
                        "reviewSchedule": "default_review_checklist.json" if checklist else "",
                        "runtimeDependency": False,
                    },
                    "controls": controls,
                    "checklist": checklist,
                }
            },
        )

    for item in checklist:
        external_id = str(item.get("id") or "").strip()
        item_text = str(item.get("item") or "").strip()
        if not external_id or not item_text:
            continue
        ReviewChecklistRecommendation.objects.update_or_create(
            external_id=external_id,
            defaults={
                "category": str(item.get("category") or "Custom").strip() or "Custom",
                "item": item_text,
                "frequency": str(item.get("frequency") or "Annual").strip() or "Annual",
                "owner": str(item.get("owner") or "Shared portal").strip() or "Shared portal",
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0009_remove_zerotrustassessment_filesystem_storage"),
    ]

    operations = [
        migrations.RunPython(seed_default_portal_state, migrations.RunPython.noop),
    ]
