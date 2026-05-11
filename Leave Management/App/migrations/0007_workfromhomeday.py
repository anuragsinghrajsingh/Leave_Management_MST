from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0006_remove_leavebalance_total_leaves"),
    ]

    operations = [
        migrations.CreateModel(
            name="WorkFromHomeDay",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("weekday", models.PositiveSmallIntegerField(choices=[(0, "Monday"), (1, "Tuesday"), (2, "Wednesday"), (3, "Thursday"), (4, "Friday"), (5, "Saturday"), (6, "Sunday")], unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "verbose_name": "Work From Home Day",
                "verbose_name_plural": "Work From Home Days",
                "ordering": ["weekday"],
            },
        ),
    ]
