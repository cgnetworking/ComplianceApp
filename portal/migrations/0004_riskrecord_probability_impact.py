from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


def _closest_pair(score):
    target = min(max(score, 1), 25)
    candidates = []
    for probability in range(1, 6):
        for impact in range(1, 6):
            product = probability * impact
            if product < target:
                continue
            candidates.append(
                (
                    product - target,
                    abs(probability - impact),
                    -product,
                    -max(probability, impact),
                    probability,
                    impact,
                )
            )
    if not candidates:
        return 5, 5
    best = min(candidates)
    return best[4], best[5]


def _risk_factors_from_legacy_level(level_value):
    try:
        level = int(level_value)
    except (TypeError, ValueError):
        return 3, 3

    level = min(max(level, 1), 25)
    if level <= 5:
        return level, level
    return _closest_pair(level)


def backfill_probability_and_impact(apps, schema_editor):
    risk_record_model = apps.get_model("portal", "RiskRecord")
    for record in risk_record_model.objects.all().iterator():
        probability, impact = _risk_factors_from_legacy_level(record.initial_risk_level)
        record.probability = probability
        record.impact = impact
        record.initial_risk_level = probability * impact
        record.save(update_fields=["probability", "impact", "initial_risk_level"])


def noop_reverse(apps, schema_editor):
    return None


class Migration(migrations.Migration):

    dependencies = [
        ("portal", "0003_reviewchecklistrecommendation"),
    ]

    operations = [
        migrations.AddField(
            model_name="riskrecord",
            name="impact",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[MinValueValidator(1), MaxValueValidator(5)],
            ),
        ),
        migrations.AddField(
            model_name="riskrecord",
            name="probability",
            field=models.PositiveSmallIntegerField(
                default=3,
                validators=[MinValueValidator(1), MaxValueValidator(5)],
            ),
        ),
        migrations.AlterField(
            model_name="riskrecord",
            name="initial_risk_level",
            field=models.PositiveSmallIntegerField(
                validators=[MinValueValidator(1), MaxValueValidator(25)],
            ),
        ),
        migrations.RunPython(backfill_probability_and_impact, noop_reverse),
    ]
