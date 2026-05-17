from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0008_remove_seeded_workfromhomeday"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="profile_photo_update_count",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
