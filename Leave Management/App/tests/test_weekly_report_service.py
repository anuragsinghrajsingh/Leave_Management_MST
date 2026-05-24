import os
import sys
import tempfile
from datetime import date, time, timedelta
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
from django.test import TestCase, override_settings
from django.utils import timezone

from App.models import AdminAuditLog, Leave, LeaveBalance, Profile
from App.services.weekly_report_service import (
    _get_active_hr_emails,
    _record_weekly_report_audit,
    build_weekly_hr_report_context,
    generate_weekly_hr_report_pdf_file,
)


class WeeklyReportServiceTests(TestCase):
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
        LeaveBalance.objects.update_or_create(
            user=self.employee,
            defaults={
                "sick_used": 2,
                "earned_used": 3,
                "unpaid": 1,
            },
        )

    def make_leave(self, created_day, **overrides):
        start = timezone.make_aware(timezone.datetime.combine(created_day, time(10, 0)))
        values = {
            "user": self.employee,
            "leave_type": "Sick",
            "from_date": created_day,
            "to_date": created_day,
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

    def test_custom_date_range_context_counts_matching_leave_and_balance(self):
        self.make_leave(date(2026, 5, 20))
        self.make_leave(date(2026, 5, 28))

        context = build_weekly_hr_report_context(
            week="custom",
            start_day=date(2026, 5, 18),
            end_day=date(2026, 5, 24),
            include_system_health=False,
        )

        self.assertEqual(context["period_start_iso"], "2026-05-18")
        self.assertEqual(context["period_end_iso"], "2026-05-24")
        self.assertEqual(context["total_requests"], 1)
        self.assertEqual(context["selected_employee_scope"], "all")
        self.assertEqual(context["selected_employee_count"], 1)
        self.assertFalse(context["show_system_health"])
        self.assertEqual(context["reports"][0]["sick_used"], 2)
        self.assertEqual(context["reports"][0]["earned_used"], 3)
        self.assertEqual(context["reports"][0]["unpaid_used"], 1)

    def test_pdf_only_generation_saves_file_to_generated_pdfs(self):
        context = build_weekly_hr_report_context(
            week="custom",
            start_day=date(2026, 5, 18),
            end_day=date(2026, 5, 24),
            include_system_health=False,
        )

        temp_root = Path("C:/tmp")
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
            with override_settings(BASE_DIR=Path(temp_dir)):
                with patch(
                    "App.services.weekly_report_service.generate_weekly_hr_report_pdf_bytes",
                    return_value=b"%PDF-test",
                ):
                    output_path = generate_weekly_hr_report_pdf_file(context=context)

            self.assertEqual(output_path.parent, Path(temp_dir) / "generated_pdfs")
            self.assertTrue(output_path.name.startswith("weekly_hr_report_2026-05-18_to_2026-05-24_"))
            self.assertEqual(output_path.read_bytes(), b"%PDF-test")

    def test_active_hr_email_lookup_excludes_blank_email(self):
        User = get_user_model()
        User.objects.create_user(
            username="hr_with_email",
            email="hr@example.com",
            password="pass12345",
            role="HR",
        )
        User.objects.create_user(
            username="hr_without_email",
            email="",
            password="pass12345",
            role="HR",
        )

        self.assertEqual(_get_active_hr_emails(), ["hr@example.com"])

    def test_weekly_report_audit_records_reason_and_metadata(self):
        context = build_weekly_hr_report_context(
            week="custom",
            start_day=date(2026, 5, 18),
            end_day=date(2026, 5, 24),
            include_system_health=True,
        )

        _record_weekly_report_audit(
            "SERVICE_WEEKLY_PDF",
            context,
            result="success",
            reason="Testing weekly report PDF.",
            output_path=Path("generated_pdfs/report.pdf"),
            hr_emails=["hr@example.com"],
        )

        audit = AdminAuditLog.objects.get(action="SERVICE_WEEKLY_PDF")
        self.assertEqual(audit.model_label, "WeeklyReportService")
        self.assertEqual(audit.reason, "Testing weekly report PDF.")
        self.assertEqual(audit.changes["result"], "success")
        self.assertEqual(audit.changes["period"]["start"], "2026-05-18")
        self.assertEqual(audit.changes["output_path"], str(Path("generated_pdfs/report.pdf")))
        self.assertEqual(audit.changes["hr_recipients"], ["hr@example.com"])


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_weekly_report_service",
    ])
