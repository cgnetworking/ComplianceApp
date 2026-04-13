from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("portal", "0002_reviewchecklistitem"),
    ]

    operations = [
        migrations.CreateModel(
            name="ReviewChecklistRecommendation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("external_id", models.CharField(max_length=64, unique=True)),
                ("category", models.CharField(default="Custom", max_length=120)),
                ("item", models.TextField()),
                ("frequency", models.CharField(default="Annual", max_length=120)),
                ("owner", models.CharField(default="Shared portal", max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["category", "created_at", "external_id"]},
        ),
    ]
