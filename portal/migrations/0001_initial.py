from django.db import migrations, models
import django.utils.timezone


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="PortalState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("key", models.CharField(max_length=64, unique=True)),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["key"]},
        ),
        migrations.CreateModel(
            name="RiskRecord",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=64, unique=True)),
                ("risk", models.TextField()),
                ("initial_risk_level", models.PositiveSmallIntegerField()),
                ("date", models.DateField()),
                ("owner", models.CharField(max_length=255)),
                ("closed_date", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={"ordering": ["-updated_at", "-created_at"]},
        ),
        migrations.CreateModel(
            name="UploadedPolicy",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_id", models.CharField(max_length=24, unique=True)),
                ("title", models.CharField(max_length=255)),
                ("document_type", models.CharField(default="Uploaded policy", max_length=80)),
                ("owner", models.CharField(default="Shared portal", max_length=255)),
                ("approver", models.CharField(default="Pending review", max_length=255)),
                ("review_frequency", models.CharField(default="Not scheduled", max_length=120)),
                ("path", models.CharField(default="", max_length=255)),
                ("folder", models.CharField(default="Uploaded", max_length=120)),
                ("purpose", models.TextField(blank=True, default="")),
                ("content_html", models.TextField()),
                ("raw_text", models.TextField(blank=True, default="")),
                ("original_filename", models.CharField(max_length=255)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["document_id"]},
        ),
        migrations.CreateModel(
            name="VendorResponse",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=64, unique=True)),
                ("vendor_name", models.CharField(max_length=255)),
                ("file_name", models.CharField(max_length=255)),
                ("extension", models.CharField(default="file", max_length=16)),
                ("mime_type", models.CharField(default="Unknown", max_length=120)),
                ("file_size", models.BigIntegerField(default=0)),
                ("imported_at", models.DateTimeField(auto_now_add=True)),
                ("preview_text", models.TextField(blank=True, default="")),
                ("summary", models.TextField(blank=True, default="")),
                ("status", models.CharField(default="Metadata only", max_length=80)),
                ("raw_text", models.TextField(blank=True, default="")),
            ],
            options={"ordering": ["-imported_at"]},
        ),
    ]
