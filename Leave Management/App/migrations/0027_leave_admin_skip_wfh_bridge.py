from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0026_admincommunicationaudit"),
    ]

    operations = [
        migrations.AddField(
            model_name="leave",
            name="admin_skip_wfh_bridge",
            field=models.BooleanField(
                default=False,
                help_text="Admin-only override to keep this leave out of WFH bridge auto-expansion.",
            ),
        ),
    ]
