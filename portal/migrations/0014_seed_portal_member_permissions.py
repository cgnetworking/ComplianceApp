from django.conf import settings
from django.db import migrations


POLICY_READER_GROUP_NAME = "Policy Reader"
PORTAL_MEMBER_GROUP_NAME = "Portal Member"
PORTAL_MEMBER_GRANTS = (
    ("policy_document", "view", "Portal member policy view"),
    ("policy_document", "add", "Portal member policy add"),
    ("policy_document", "delete", "Portal member policy delete"),
    ("policy_document", "export", "Portal member policy export"),
    ("policy_document", "approve", "Portal member policy approve"),
    ("mapping", "view", "Portal member mapping view"),
    ("mapping", "change", "Portal member mapping change"),
    ("control_state", "view", "Portal member control state view"),
    ("control_state", "change", "Portal member control state change"),
    ("review_state", "view", "Portal member review state view"),
    ("review_state", "add", "Portal member review state add"),
    ("review_state", "change", "Portal member review state change"),
    ("review_state", "delete", "Portal member review state delete"),
    ("vendor_response", "view", "Portal member vendor response view"),
    ("vendor_response", "add", "Portal member vendor response add"),
    ("vendor_response", "delete", "Portal member vendor response delete"),
    ("vendor_response", "export", "Portal member vendor response export"),
    ("risk_record", "view", "Portal member risk record view"),
    ("risk_record", "add", "Portal member risk record add"),
    ("risk_record", "change", "Portal member risk record change"),
    ("risk_record", "delete", "Portal member risk record delete"),
    ("risk_record", "export", "Portal member risk record export"),
)


def seed_portal_member_group(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    grant_model = apps.get_model("portal", "PortalPermissionGrant")
    user_model = apps.get_model(*settings.AUTH_USER_MODEL.split("."))

    policy_reader_group, _ = group_model.objects.get_or_create(name=POLICY_READER_GROUP_NAME)
    portal_member_group, _ = group_model.objects.get_or_create(name=PORTAL_MEMBER_GROUP_NAME)

    for resource, action, name in PORTAL_MEMBER_GRANTS:
        grant_model.objects.update_or_create(
            group=portal_member_group,
            resource=resource,
            action=action,
            defaults={
                "name": name,
                "description": f"Seeded permission for the {PORTAL_MEMBER_GROUP_NAME} group.",
                "constraints": {},
                "enabled": True,
            },
        )

    eligible_users = user_model.objects.filter(is_active=True, is_staff=False).exclude(groups=policy_reader_group)
    for user in eligible_users.iterator():
        user.groups.add(portal_member_group)


def remove_portal_member_group(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    group_model.objects.filter(name=PORTAL_MEMBER_GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0001_initial"),
        ("portal", "0013_portalpermissiongrant"),
    ]

    operations = [
        migrations.RunPython(seed_portal_member_group, remove_portal_member_group),
    ]
