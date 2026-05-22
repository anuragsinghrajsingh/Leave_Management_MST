from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0031_reportexportcontrol"),
    ]

    operations = [
        migrations.AddField(
            model_name="profile",
            name="welcome_sent_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
