from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0004_riskrecord_probability_impact"),
    ]

    operations = [
        migrations.AddField(
            model_name="reviewchecklistitem",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="reviewchecklistrecommendation",
            name="start_date",
            field=models.DateField(blank=True, null=True),
        ),
    ]
