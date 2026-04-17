from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0011_riskrecord_created_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="zerotrustcertificate",
            name="pfx_path",
            field=models.CharField(blank=True, default="", max_length=512),
        ),
        migrations.RemoveField(
            model_name="zerotrustcertificate",
            name="pfx_bytes",
        ),
    ]
