import os
import sys
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

from App.models import AdminAuditLog, EmailDeliveryLog
from App.services.email_delivery_log import record_email_delivery


class EmailDeliveryLogServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="employee_email",
            email="employee-email@example.com",
            password="pass-123",
            role="EMPLOYEE",
        )

    def test_record_email_delivery_creates_one_row_per_recipient(self):
        created = record_email_delivery(
            subject="Test subject",
            recipients=["one@example.com", "two@example.com"],
            status="sent",
            email_type="test_email",
            related_user=self.user,
        )

        self.assertEqual(created, 2)
        self.assertEqual(EmailDeliveryLog.objects.filter(email_type="test_email").count(), 2)

    def test_terminal_retry_notice_records_sent_attempt_and_audit(self):
        failed_log = EmailDeliveryLog.objects.create(
            subject="Original failed email",
            recipient=self.user.email,
            status="failed",
            email_type="unit_test_email",
            error_message="SMTP failed",
            related_user=self.user,
        )

        from App.services import email_delivery_log

        answers = iter([
            str(failed_log.id),
            "Retrying failed email",
            "SEND",
            "",
        ])

        with patch("builtins.input", side_effect=lambda _prompt="": next(answers)):
            with patch("App.services.email_delivery_log.EmailMessage.send", return_value=1):
                result = email_delivery_log._send_retry_notice()

        self.assertIsNone(result)
        self.assertTrue(
            EmailDeliveryLog.objects.filter(
                email_type="retry_unit_test_email",
                recipient=self.user.email,
                status="sent",
                metadata__original_email_log_id=failed_log.id,
            ).exists()
        )
        self.assertTrue(
            AdminAuditLog.objects.filter(
                action="EMAIL_RETRY",
                object_id=str(failed_log.id),
                reason="Retrying failed email",
            ).exists()
        )

    def test_terminal_summary_counts_do_not_crash(self):
        EmailDeliveryLog.objects.create(
            subject="Failed email",
            recipient=self.user.email,
            status="failed",
            email_type="summary_test",
            error_message="Failed",
        )

        from App.services import email_delivery_log

        with patch("builtins.input", return_value=""):
            email_delivery_log._show_summary()


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_email_delivery_log_service",
    ])
