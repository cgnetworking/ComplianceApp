from django.db import migrations


POLICY_READER_GROUP_NAME = "Policy Reader"


def create_policy_reader_group(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    group_model.objects.get_or_create(name=POLICY_READER_GROUP_NAME)


def remove_policy_reader_group(apps, schema_editor):
    group_model = apps.get_model("auth", "Group")
    group_model.objects.filter(name=POLICY_READER_GROUP_NAME).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("auth", "0001_initial"),
        ("portal", "0005_reviewchecklist_start_date"),
    ]

    operations = [
        migrations.RunPython(create_policy_reader_group, remove_policy_reader_group),
    ]
