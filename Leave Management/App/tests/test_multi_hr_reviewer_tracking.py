import os
import sys
from datetime import timedelta
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
from django.urls import reverse
from django.utils import timezone

from App.models import Leave
from App.views import build_employee_notifications


class MultiHrReviewerTrackingTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.employee = User.objects.create_user(
            username="employee_one",
            email="employee@example.com",
            password="pass12345",
            first_name="Employee",
            last_name="One",
            role="EMPLOYEE",
        )
        self.hr_a = User.objects.create_user(
            username="hr_a",
            email="hra@example.com",
            password="pass12345",
            first_name="HR",
            last_name="Alpha",
            role="HR",
        )
        self.hr_b = User.objects.create_user(
            username="hr_b",
            email="hrb@example.com",
            password="pass12345",
            first_name="HR",
            last_name="Beta",
            role="HR",
        )

    def make_leave(self, **overrides):
        start = timezone.now() + timedelta(days=3)
        start = start.replace(hour=11, minute=0, second=0, microsecond=0)
        end = start + timedelta(hours=2)
        values = {
            "user": self.employee,
            "leave_type": "Short",
            "from_date": start.date(),
            "to_date": start.date(),
            "from_datetime": start,
            "to_datetime": end,
            "reason": "Personal work",
            "status": "Pending",
            "deducted_from": "Sick",
        }
        values.update(overrides)
        return Leave.objects.create(**values)

    @patch("App.views.send_branded_email")
    def test_hr_approval_stores_reviewer(self, _send_email):
        leave = self.make_leave()
        self.client.force_login(self.hr_a)

        response = self.client.post(
            reverse("approve_leave", args=[leave.id]),
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "Approved")
        self.assertEqual(leave.reviewed_by, self.hr_a)
        self.assertIsNotNone(leave.approved_at)
        self.assertIsNone(leave.rejected_at)

    @patch("App.views.send_branded_email")
    def test_hr_rejection_stores_reviewer_and_reason(self, _send_email):
        leave = self.make_leave()
        self.client.force_login(self.hr_b)

        response = self.client.post(
            reverse("reject_leave", args=[leave.id]),
            {"rejection_reason": "Need more details."},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )

        self.assertEqual(response.status_code, 200)
        leave.refresh_from_db()
        self.assertEqual(leave.status, "Rejected")
        self.assertEqual(leave.reviewed_by, self.hr_b)
        self.assertEqual(leave.rejection_reason, "Need more details.")
        self.assertIsNotNone(leave.rejected_at)
        self.assertIsNone(leave.approved_at)

    def test_employee_notifications_include_reviewer_names_and_fallback(self):
        approved_leave = self.make_leave(
            status="Approved",
            reviewed_by=self.hr_a,
            approved_at=timezone.now(),
        )
        rejected_leave = self.make_leave(
            status="Rejected",
            reviewed_by=self.hr_b,
            rejected_at=timezone.now(),
            rejection_reason="Need more details.",
        )
        old_leave_without_reviewer = self.make_leave(
            status="Approved",
            reviewed_by=None,
            approved_at=timezone.now(),
        )

        payload = build_employee_notifications([
            approved_leave,
            rejected_leave,
            old_leave_without_reviewer,
        ])
        notifications_by_id = {
            item["id"]: item
            for item in payload["notifications"]
        }

        self.assertEqual(notifications_by_id[approved_leave.id]["reviewer_name"], "HR Alpha")
        self.assertEqual(notifications_by_id[rejected_leave.id]["reviewer_name"], "HR Beta")
        self.assertEqual(notifications_by_id[old_leave_without_reviewer.id]["reviewer_name"], "HR Team")


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_multi_hr_reviewer_tracking",
    ])
