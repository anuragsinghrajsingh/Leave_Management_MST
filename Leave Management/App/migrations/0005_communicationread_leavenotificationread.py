from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0004_alter_leave_status_alter_profile_phone_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunicationRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                ("communication", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="read_receipts", to="App.communication")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="communication_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-read_at"],
                "unique_together": {("user", "communication")},
            },
        ),
        migrations.CreateModel(
            name="LeaveNotificationRead",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("read_at", models.DateTimeField(auto_now_add=True)),
                ("leave", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_reads", to="App.leave")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_notification_reads", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-read_at"],
                "unique_together": {("user", "leave")},
            },
        ),
    ]
