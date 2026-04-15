from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0006_policy_reader_role"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="uploadedpolicy",
            name="owner",
        ),
        migrations.AddField(
            model_name="uploadedpolicy",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="uploadedpolicy",
            name="approved_by",
            field=models.CharField(blank=True, default="", max_length=255),
        ),
    ]
