from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0006_communicationseen_leavenotificationseen"),
    ]

    operations = [
        migrations.AddField(
            model_name="leave",
            name="approved_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="leave",
            name="no_of_times_updated",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="leave",
            name="rejected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="leave",
            name="updated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
