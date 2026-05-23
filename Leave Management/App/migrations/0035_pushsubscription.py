from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("App", "0034_customuser_must_change_password"),
    ]

    operations = [
        migrations.CreateModel(
            name="PushSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("endpoint", models.URLField(max_length=500, unique=True)),
                ("p256dh", models.CharField(max_length=255)),
                ("auth", models.CharField(max_length=255)),
                ("browser", models.CharField(blank=True, max_length=120)),
                ("device_label", models.CharField(blank=True, max_length=120)),
                ("is_active", models.BooleanField(db_index=True, default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("last_sent_at", models.DateTimeField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="push_subscriptions",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Push subscription",
                "verbose_name_plural": "Push subscriptions",
                "ordering": ["-last_seen_at", "-id"],
            },
        ),
        migrations.AddIndex(
            model_name="pushsubscription",
            index=models.Index(fields=["user", "is_active"], name="App_pushsub_user_id_28d7f5_idx"),
        ),
    ]
