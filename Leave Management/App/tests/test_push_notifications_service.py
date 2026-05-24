import os
import sys
import types
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
os.environ.setdefault("LMS_USE_SQLITE_TEST_DB", "1")

import django
from django.apps import apps

if not apps.ready:
    django.setup()

from django.contrib.auth import get_user_model
from django.core.management import execute_from_command_line
from django.test import TestCase

from App.models import AdminAuditLog, PushSubscription


class PushNotificationsServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="employee_one",
            email="employee@example.com",
            password="pass-123",
            role="EMPLOYEE",
        )

    def test_invalid_subscription_is_deactivated(self):
        subscription = PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/1",
            p256dh="p256dh-key",
            auth="auth-key",
            is_active=True,
        )

        class FakeResponse:
            status_code = 410

        class FakeWebPushException(Exception):
            def __init__(self):
                super().__init__("Gone")
                self.response = FakeResponse()

        def fake_webpush(**_kwargs):
            raise FakeWebPushException()

        fake_module = types.SimpleNamespace(
            WebPushException=FakeWebPushException,
            webpush=fake_webpush,
        )

        with patch("App.services.push_notifications.push_is_configured", return_value=True):
            with patch.dict(sys.modules, {"pywebpush": fake_module}):
                from App.services.push_notifications import send_push_payload_to_user

                result = send_push_payload_to_user(self.user, {"title": "Test"})

        subscription.refresh_from_db()
        self.assertEqual(result, {"sent": 0, "failed": 1, "skipped": False})
        self.assertFalse(subscription.is_active)
        self.assertIn("Gone", subscription.last_error)

    def test_terminal_deactivate_one_subscription_deactivates_selected_subscription(self):
        first = PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/first",
            p256dh="p256dh-key-1",
            auth="auth-key-1",
            browser="Brave",
            device_label="Windows",
            is_active=True,
        )
        second = PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/second",
            p256dh="p256dh-key-2",
            auth="auth-key-2",
            browser="Edge",
            device_label="Windows",
            is_active=True,
        )

        from App.services import push_notifications

        answers = iter([
            "2",
            self.user.username,
            "1",
            f"id {second.id}",
            "Edge token is failing",
            "DEACTIVATE",
            "",
        ])

        with patch("builtins.input", side_effect=lambda _prompt="": next(answers)):
            result = push_notifications._deactivate_one_subscription()

        first.refresh_from_db()
        second.refresh_from_db()
        self.assertIsNone(result)
        self.assertTrue(first.is_active)
        self.assertFalse(second.is_active)
        self.assertTrue(
            AdminAuditLog.objects.filter(
                action="PUSH_DEACTIVATE",
                object_id=str(second.id),
                reason="Edge token is failing",
            ).exists()
        )

    def test_terminal_summary_counts_do_not_crash(self):
        PushSubscription.objects.create(
            user=self.user,
            endpoint="https://push.example.test/subscription/summary",
            p256dh="p256dh-key",
            auth="auth-key",
            last_error="Previous failure",
            is_active=False,
        )

        from App.services import push_notifications

        with patch("builtins.input", return_value=""):
            push_notifications._show_summary()


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_push_notifications_service",
    ])
