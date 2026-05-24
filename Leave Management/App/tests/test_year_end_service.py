import os
import sys
from datetime import date
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

from App.models import LeaveBalance, Profile, YearEndCarryForwardRun
from App.services.year_end_service import (
    get_year_end_carry_forward_status,
    run_year_end_carry_forward_if_due,
)


class YearEndServiceTests(TestCase):
    def create_user_with_balance(self, *, username, role, employee_id, active=True, joining=date(2020, 1, 1)):
        user = get_user_model().objects.create_user(
            username=username,
            email=f"{username}@example.com",
            password="pass-123",
            role=role,
            is_active=active,
        )
        Profile.objects.update_or_create(
            user=user,
            defaults={
                "employee_id": employee_id,
                "department": "Engineering",
                "role": role,
                "date_of_joining": joining,
            },
        )
        balance, _created = LeaveBalance.objects.update_or_create(
            user=user,
            defaults={
                "earned_total": 15,
                "earned_used": 5,
                "sick_total": 12,
                "sick_used": 3,
                "total_leave_balance": 27,
                "total_leave_remaining": 19,
                "last_year_end_processed": None,
            },
        )
        return user, balance

    def test_status_counts_employee_only_and_ignores_hr_admin(self):
        self.create_user_with_balance(username="employee_one", role="EMPLOYEE", employee_id="EMP001")
        self.create_user_with_balance(username="employee_two", role="EMPLOYEE", employee_id="EMP002", active=False)
        self.create_user_with_balance(username="hr_one", role="HR", employee_id="HR001")
        self.create_user_with_balance(username="admin_one", role="Admin", employee_id="ADM001")

        status = get_year_end_carry_forward_status(today=date(2027, 1, 1))

        self.assertEqual(status["eligible_count"], 2)
        self.assertEqual(status["processable_count"], 1)
        self.assertEqual(status["ignored_non_employee_count"], 2)
        self.assertTrue(status["should_run"])

    def test_run_processes_only_active_employees(self):
        employee, employee_balance = self.create_user_with_balance(
            username="employee_one",
            role="EMPLOYEE",
            employee_id="EMP001",
            joining=date(2020, 1, 1),
        )
        inactive_employee, inactive_balance = self.create_user_with_balance(
            username="employee_two",
            role="EMPLOYEE",
            employee_id="EMP002",
            active=False,
        )
        hr_user, hr_balance = self.create_user_with_balance(username="hr_one", role="HR", employee_id="HR001")
        admin_user, admin_balance = self.create_user_with_balance(username="admin_one", role="Admin", employee_id="ADM001")

        did_run = run_year_end_carry_forward_if_due(today=date(2027, 1, 1))

        self.assertTrue(did_run)
        employee_balance.refresh_from_db()
        inactive_balance.refresh_from_db()
        hr_balance.refresh_from_db()
        admin_balance.refresh_from_db()

        self.assertEqual(employee_balance.last_year_end_processed, 2027)
        self.assertEqual(employee_balance.earned_used, 0)
        self.assertEqual(employee_balance.sick_used, 0)

        self.assertIsNone(inactive_balance.last_year_end_processed)
        self.assertIsNone(hr_balance.last_year_end_processed)
        self.assertIsNone(admin_balance.last_year_end_processed)
        self.assertTrue(YearEndCarryForwardRun.objects.filter(year=2027, completed_at__isnull=False).exists())

    def test_protected_year_is_skipped(self):
        _employee, balance = self.create_user_with_balance(
            username="employee_one",
            role="EMPLOYEE",
            employee_id="EMP001",
        )

        did_run = run_year_end_carry_forward_if_due(today=date(2026, 1, 1))

        balance.refresh_from_db()
        self.assertFalse(did_run)
        self.assertIsNone(balance.last_year_end_processed)
        self.assertFalse(YearEndCarryForwardRun.objects.filter(year=2026).exists())


if __name__ == "__main__":
    execute_from_command_line([
        sys.argv[0],
        "test",
        "App.tests.test_year_end_service",
    ])
