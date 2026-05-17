import App.services.profile_photo_storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0009_profile_profile_photo_update_count"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="profile_photo",
            field=models.ImageField(
                blank=True,
                default=None,
                null=True,
                storage=App.services.profile_photo_storage.ProfilePhotoStorage(),
                upload_to="profile_photos/",
            ),
        ),
    ]
