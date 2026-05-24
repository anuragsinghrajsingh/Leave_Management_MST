import os
import sys
from pathlib import Path

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

from App.models import AdminAuditLog
from App.services.user_password_reset_service import reset_password_only


class UserPasswordResetServiceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="employee_one",
            email="employee@example.com",
            password="old-pass-123",
            first_name="Employee",
            last_name="One",
            role="EMPLOYEE",
        )

    def test_password_reset_changes_password_and_requires_audit_reason(self):
        with self.assertRaises(ValueError):
            reset_password_only(self.user, "new-pass-123", "")

        reset_password_only(self.user, "new-pass-123", "Security reset requested by HR.")
        self.user.refresh_from_db()

        self.assertTrue(self.user.check_password("new-pass-123"))
        audit = AdminAuditLog.objects.get(action="PASSWORD_RESET")
        self.assertEqual(audit.object_id, str(self.user.pk))
        self.assertEqual(audit.reason, "Security reset requested by HR.")
        self.assertEqual(audit.changes["password"]["new"], "[reset from terminal]")


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_user_password_reset_service",
    ])
