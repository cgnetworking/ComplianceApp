from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0007_uploadedpolicy_approval_state"),
    ]

    operations = [
        migrations.CreateModel(
            name="ZeroTrustTenantProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=64, unique=True)),
                ("display_name", models.CharField(blank=True, default="", max_length=255)),
                ("tenant_id", models.CharField(max_length=128)),
                ("client_id", models.CharField(max_length=128)),
                ("certificate_thumbprint", models.CharField(blank=True, default="", max_length=64)),
                ("is_active", models.BooleanField(default=True)),
                ("last_run_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["display_name", "tenant_id", "client_id", "external_id"],
                "indexes": [
                    models.Index(fields=["tenant_id"], name="portal_zt_profile_tenant_idx"),
                    models.Index(fields=["last_run_at"], name="portal_zt_profile_last_run_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("tenant_id", "client_id"),
                        name="portal_zt_profile_tenant_client_unique",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ZeroTrustCertificate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=64, unique=True)),
                ("thumbprint", models.CharField(max_length=64)),
                ("subject", models.CharField(max_length=255)),
                ("serial_number", models.CharField(default="", max_length=128)),
                ("not_before", models.DateTimeField()),
                ("not_after", models.DateTimeField()),
                ("key_algorithm", models.CharField(default="RSA", max_length=64)),
                ("key_size", models.PositiveIntegerField(default=2048)),
                ("public_certificate_der", models.BinaryField()),
                ("certificate_path", models.CharField(default="", max_length=512)),
                ("private_key_path", models.CharField(default="", max_length=512)),
                ("pfx_path", models.CharField(default="", max_length=512)),
                ("is_current", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="certificates",
                        to="portal.zerotrusttenantprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "external_id"],
                "indexes": [
                    models.Index(fields=["profile", "is_current"], name="portal_zt_cert_current_idx"),
                    models.Index(fields=["not_after"], name="portal_zt_cert_not_after_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("profile", "thumbprint"),
                        name="portal_zt_cert_profile_thumbprint_unique",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ZeroTrustAssessmentRun",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("queued", "Queued"),
                            ("claimed", "Claimed"),
                            ("running", "Running"),
                            ("ingesting", "Ingesting"),
                            ("succeeded", "Succeeded"),
                            ("succeeded_with_warnings", "Succeeded with warnings"),
                            ("failed", "Failed"),
                            ("stale", "Stale"),
                        ],
                        default="queued",
                        max_length=32,
                    ),
                ),
                ("status_message", models.TextField(blank=True, default="")),
                ("warning_summary", models.TextField(blank=True, default="")),
                ("error_summary", models.TextField(blank=True, default="")),
                ("worker_id", models.CharField(blank=True, default="", max_length=128)),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("exit_code", models.IntegerField(blank=True, null=True)),
                ("claimed_at", models.DateTimeField(blank=True, null=True)),
                ("lease_expires_at", models.DateTimeField(blank=True, null=True)),
                ("last_heartbeat_at", models.DateTimeField(blank=True, null=True)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("staged_path", models.CharField(blank=True, default="", max_length=512)),
                ("cleaned_up_at", models.DateTimeField(blank=True, null=True)),
                ("ingested_at", models.DateTimeField(blank=True, null=True)),
                ("entrypoint_relative_path", models.CharField(blank=True, default="", max_length=512)),
                ("module_version", models.CharField(blank=True, default="", max_length=64)),
                ("powershell_version", models.CharField(blank=True, default="", max_length=64)),
                ("input_snapshot", models.JSONField(blank=True, default=dict)),
                ("summary_json", models.JSONField(blank=True, default=dict)),
                ("requested_by", models.CharField(blank=True, default="", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "certificate",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="assessment_runs",
                        to="portal.zerotrustcertificate",
                    ),
                ),
                (
                    "profile",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="assessment_runs",
                        to="portal.zerotrusttenantprofile",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at", "external_id"],
                "indexes": [
                    models.Index(fields=["profile", "created_at"], name="portal_zt_run_profile_created_idx"),
                    models.Index(fields=["profile", "status"], name="portal_zt_run_profile_status_idx"),
                    models.Index(fields=["status", "created_at"], name="portal_zt_run_status_created_idx"),
                    models.Index(fields=["completed_at"], name="portal_zt_run_completed_idx"),
                ],
            },
        ),
        migrations.CreateModel(
            name="ZeroTrustAssessmentRunLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("sequence", models.PositiveIntegerField()),
                ("level", models.CharField(default="info", max_length=16)),
                ("stream", models.CharField(default="system", max_length=16)),
                ("message", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="portal.zerotrustassessmentrun",
                    ),
                ),
            ],
            options={
                "ordering": ["run_id", "sequence"],
                "indexes": [
                    models.Index(fields=["run", "created_at"], name="portal_zt_run_log_created_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("run", "sequence"),
                        name="portal_zt_run_log_sequence_unique",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="ZeroTrustAssessmentArtifact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("relative_path", models.CharField(max_length=512)),
                ("artifact_type", models.CharField(default="file", max_length=32)),
                ("content_type", models.CharField(default="application/octet-stream", max_length=255)),
                ("size_bytes", models.BigIntegerField(default=0)),
                ("sha256", models.CharField(default="", max_length=64)),
                ("is_entrypoint", models.BooleanField(default=False)),
                ("content", models.BinaryField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="artifacts",
                        to="portal.zerotrustassessmentrun",
                    ),
                ),
            ],
            options={
                "ordering": ["relative_path"],
                "indexes": [
                    models.Index(fields=["run", "is_entrypoint"], name="portal_zt_artifact_entry_idx"),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        fields=("run", "relative_path"),
                        name="portal_zt_artifact_run_path_unique",
                    )
                ],
            },
        ),
    ]
