from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0005_communicationread_leavenotificationread"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommunicationSeen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seen_at", models.DateTimeField(auto_now_add=True)),
                ("communication", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="seen_receipts", to="App.communication")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="communication_seen_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-seen_at"],
                "unique_together": {("user", "communication")},
            },
        ),
        migrations.CreateModel(
            name="LeaveNotificationSeen",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("seen_at", models.DateTimeField(auto_now_add=True)),
                ("leave", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="notification_seen_receipts", to="App.leave")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_notification_seen_entries", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-seen_at"],
                "unique_together": {("user", "leave")},
            },
        ),
    ]
