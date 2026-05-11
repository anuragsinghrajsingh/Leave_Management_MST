from django.db import migrations


def remove_seeded_work_from_home_day(apps, schema_editor):
    WorkFromHomeDay = apps.get_model("App", "WorkFromHomeDay")
    rows = list(WorkFromHomeDay.objects.all())

    if len(rows) == 1 and rows[0].weekday == 2 and rows[0].is_active:
        rows[0].delete()


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0007_workfromhomeday"),
    ]

    operations = [
        migrations.RunPython(remove_seeded_work_from_home_day, migrations.RunPython.noop),
    ]
