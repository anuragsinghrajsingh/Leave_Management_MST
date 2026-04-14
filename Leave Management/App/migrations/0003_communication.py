from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0002_alter_customuser_role_alter_leavebalance_sick_total_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="Communication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("message_type", models.CharField(choices=[("ANNOUNCEMENT", "Announcement"), ("DIRECT", "Direct Message")], max_length=20)),
                ("audience_role", models.CharField(blank=True, choices=[("HR", "HR"), ("EMPLOYEE", "Employee")], max_length=20, null=True)),
                ("title", models.CharField(blank=True, max_length=140)),
                ("body", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("recipient", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="received_communications", to=settings.AUTH_USER_MODEL)),
                ("sender", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="sent_communications", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
