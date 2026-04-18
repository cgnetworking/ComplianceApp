from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


POLICY_READER_GROUP_NAME = "Policy Reader"
POLICY_READER_GRANTS = (
    ("policy_document", "view", "Policy document view"),
    ("policy_document", "export", "Policy document export"),
    ("mapping", "view", "Mapping view"),
)


def seed_policy_reader_grants(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    grant_model = apps.get_model("portal", "PortalPermissionGrant")
    group, _ = group_model.objects.get_or_create(name=POLICY_READER_GROUP_NAME)
    for resource, action, name in POLICY_READER_GRANTS:
        grant_model.objects.update_or_create(
            group=group,
            resource=resource,
            action=action,
            defaults={
                "name": name,
                "description": f"Seeded permission for the {POLICY_READER_GROUP_NAME} group.",
                "constraints": {},
                "enabled": True,
            },
        )


def remove_policy_reader_grants(apps, schema_editor):
    grant_model = apps.get_model("portal", "PortalPermissionGrant")
    grant_model.objects.filter(
        group__name=POLICY_READER_GROUP_NAME,
        resource__in=[resource for resource, _, _ in POLICY_READER_GRANTS],
        action__in=[action for _, action, _ in POLICY_READER_GRANTS],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("auth", "0001_initial"),
        ("portal", "0012_zerotrustcertificate_restore_filesystem_pfx"),
    ]

    operations = [
        migrations.CreateModel(
            name="PortalPermissionGrant",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(blank=True, default="", max_length=120)),
                ("description", models.TextField(blank=True, default="")),
                (
                    "resource",
                    models.CharField(
                        choices=[
                            ("policy_document", "Policy document"),
                            ("mapping", "Mapping"),
                            ("control_state", "Control state"),
                            ("review_state", "Review state"),
                            ("vendor_response", "Vendor response"),
                            ("risk_record", "Risk record"),
                            ("audit_log", "Audit log"),
                            ("assessment", "Assessment"),
                        ],
                        max_length=64,
                    ),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[
                            ("view", "View"),
                            ("add", "Add"),
                            ("change", "Change"),
                            ("delete", "Delete"),
                            ("export", "Export"),
                            ("approve", "Approve"),
                            ("assign", "Assign"),
                            ("view_raw", "View raw"),
                        ],
                        max_length=32,
                    ),
                ),
                ("constraints", models.JSONField(blank=True, default=dict)),
                ("enabled", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "group",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_permission_grants",
                        to="auth.group",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="portal_permission_grants",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["resource", "action", "id"],
            },
        ),
        migrations.AddConstraint(
            model_name="portalpermissiongrant",
            constraint=models.CheckConstraint(
                condition=(
                    (models.Q(("group__isnull", True), ("user__isnull", False)))
                    | (models.Q(("group__isnull", False), ("user__isnull", True)))
                ),
                name="portal_perm_one_principal_ck",
            ),
        ),
        migrations.AddConstraint(
            model_name="portalpermissiongrant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("user__isnull", False)),
                fields=("user", "resource", "action"),
                name="portal_perm_user_uq",
            ),
        ),
        migrations.AddConstraint(
            model_name="portalpermissiongrant",
            constraint=models.UniqueConstraint(
                condition=models.Q(("group__isnull", False)),
                fields=("group", "resource", "action"),
                name="portal_perm_group_uq",
            ),
        ),
        migrations.RunPython(seed_policy_reader_grants, remove_policy_reader_grants),
    ]
