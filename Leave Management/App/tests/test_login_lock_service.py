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
from django.core.cache import cache
from django.core.management import execute_from_command_line
from django.test import TestCase

from App.models import AdminAuditLog
from App.services.login_lock_service import (
    detect_user_portal,
    get_login_lock_status,
    lock_user_login,
    record_login_lock_audit,
    unlock_user_login,
)


class LoginLockServiceTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = get_user_model().objects.create_user(
            username="employee_one",
            email="employee@example.com",
            password="pass-123",
            first_name="Employee",
            last_name="One",
            role="EMPLOYEE",
        )

    def test_login_lock_and_unlock_status_can_be_audited(self):
        portal = detect_user_portal(self.user)
        old_status = get_login_lock_status(portal, self.user.username)

        locked_status = lock_user_login(self.user, 5, portal=portal)
        self.assertTrue(locked_status.is_locked)
        self.assertEqual(locked_status.reason, "Manual/admin lock")

        unlocked_status = unlock_user_login(self.user, portal=portal)
        self.assertFalse(unlocked_status.is_locked)

        record_login_lock_audit(
            self.user,
            action="LOGIN_UNLOCK",
            source="TEST",
            reason="Unlock verified by automated test.",
            old_status=old_status,
            new_status=unlocked_status,
            duration_minutes=5,
            mode="manual",
        )

        audit = AdminAuditLog.objects.get(action="LOGIN_UNLOCK")
        self.assertEqual(audit.reason, "Unlock verified by automated test.")
        self.assertEqual(audit.changes["login_lock_control"]["new"]["status"], "unlocked")


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_login_lock_service",
    ])
