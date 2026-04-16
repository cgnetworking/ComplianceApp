from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0010_seed_default_portal_state"),
    ]

    operations = [
        migrations.AddField(
            model_name="riskrecord",
            name="created_by",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
