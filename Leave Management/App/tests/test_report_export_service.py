import os
import sys
from datetime import date, time, timedelta
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
from django.utils import timezone

from App.models import Leave, Profile
from App.services.report_export_service import build_report_export


class ReportExportServiceTests(TestCase):
    def setUp(self):
        self.employee = get_user_model().objects.create_user(
            username="employee_one",
            email="employee@example.com",
            password="pass-123",
            first_name="Employee",
            last_name="One",
            role="EMPLOYEE",
        )
        Profile.objects.update_or_create(
            user=self.employee,
            defaults={
                "employee_id": "EMP001",
                "department": "Engineering",
                "role": "EMPLOYEE",
                "date_of_joining": date(2026, 1, 1),
                "phone": "9000000001",
            },
        )

    def make_leave(self, day, **overrides):
        start = timezone.make_aware(timezone.datetime.combine(day, time(10, 0)))
        values = {
            "user": self.employee,
            "leave_type": "Sick",
            "from_date": day,
            "to_date": day,
            "from_datetime": start,
            "to_datetime": start + timedelta(hours=9),
            "reason": "Medical",
            "status": "Approved",
            "deducted_from": "Sick",
        }
        values.update(overrides)
        leave = Leave.objects.create(**values)
        Leave.objects.filter(pk=leave.pk).update(created_at=start)
        leave.refresh_from_db()
        return leave

    def test_leave_request_csv_export_uses_date_status_and_employee_filters(self):
        self.make_leave(date(2026, 5, 20))
        self.make_leave(date(2026, 6, 1))

        export = build_report_export({
            "report_type": "leave_request",
            "period_type": "custom",
            "date_from": date(2026, 5, 1),
            "date_to": date(2026, 5, 31),
            "export_format": "csv",
            "employee": self.employee,
            "leave_status": "Approved",
        })

        content = export["content"].decode("utf-8-sig")
        self.assertEqual(export["content_type"], "text/csv")
        self.assertEqual(export["row_count"], 1)
        self.assertIn("Leave ID", content)
        self.assertIn("Employee One", content)


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_report_export_service",
    ])
