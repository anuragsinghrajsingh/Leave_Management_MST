import argparse
import logging
import os
import sys
from pathlib import Path


def _setup_django_for_direct_run():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


if __name__ == "__main__":
    _setup_django_for_direct_run()

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from App.models import LeaveBalance, YearEndCarryForwardRun

logger = logging.getLogger(__name__)

SKIP_YEAR_END_YEARS = {2026}


def get_year_end_carry_forward_status(today=None):
    today = today or timezone.localdate()
    processing_year = today.year
    run_record = YearEndCarryForwardRun.objects.filter(year=processing_year).first()
    is_protected = processing_year in SKIP_YEAR_END_YEARS
    is_completed = bool(run_record and run_record.completed_at)
    eligible_count = (
        LeaveBalance.objects
        .filter(user__profile__isnull=False)
        .exclude(last_year_end_processed=processing_year)
        .count()
    )

    if is_protected:
        reason = f"protected year {processing_year}"
        should_run = False
    elif is_completed:
        reason = "already completed"
        should_run = False
    elif eligible_count <= 0:
        reason = "no eligible balances"
        should_run = False
    else:
        reason = "not completed"
        should_run = True

    return {
        "year": processing_year,
        "today": today,
        "is_protected": is_protected,
        "is_completed": is_completed,
        "completed_at": run_record.completed_at if run_record else None,
        "eligible_count": eligible_count,
        "should_run": should_run,
        "reason": reason,
    }


def process_year_end_carry_forward(user, today=None, balance=None):

    balance = balance or user.leavebalance

    today = today or timezone.localdate()
    processing_year = today.year

    if balance.last_year_end_processed == processing_year:
        return False

    profile = getattr(user, "profile", None)
    if not profile or not profile.date_of_joining:
        logger.warning("Skipping year-end carry forward for user %s due to missing profile or date_of_joining.", user.pk)
        return False

    years_of_service = (today - profile.date_of_joining).days // 365

    if years_of_service <= 3:
        carry_limit = 7.5
    else:
        carry_limit = 10.5

    earned_remaining = balance.earned_total - balance.earned_used

    carry_forward = min(earned_remaining, carry_limit)
    fresh_earned_quota = LeaveBalance._meta.get_field("earned_total").default
    fresh_sick_quota = LeaveBalance._meta.get_field("sick_total").default

    balance.earned_total = fresh_earned_quota + carry_forward
    balance.earned_used = 0
    balance.sick_total = fresh_sick_quota
    balance.sick_used = 0

    earned_remaining = balance.earned_total - balance.earned_used
    sick_remaining = balance.sick_total - balance.sick_used
    balance.total_leave_balance = balance.earned_total + balance.sick_total
    balance.total_leave_remaining = earned_remaining + sick_remaining
    balance.last_year_end_processed = processing_year

    balance.save(update_fields=[
        "total_leave_balance",
        "total_leave_remaining",
        "earned_total",
        "earned_used",
        "sick_total",
        "sick_used",
        "last_year_end_processed",
    ])

    return True


def run_year_end_carry_forward_if_due(today=None):
    today = today or timezone.localdate()

    processing_year = today.year

    if processing_year in SKIP_YEAR_END_YEARS:
        logger.info(
            "Year-end carry forward skipped for protected year %s.",
            processing_year,
        )
        return False

    user_model = get_user_model()
    with transaction.atomic():
        run_record, _ = YearEndCarryForwardRun.objects.select_for_update().get_or_create(
            year=processing_year, defaults={"completed_at": None},)

        if run_record.completed_at:
            return False

        eligible_balances = (
            LeaveBalance.objects
            .select_for_update()
            .select_related("user", "user__profile")
            .filter(user__profile__isnull=False)
            .exclude(last_year_end_processed=processing_year)
            .order_by("pk")
        )

        processed_count = 0
        skipped_count = 0

        for balance in eligible_balances:
            user = balance.user
            if process_year_end_carry_forward(user, today=today, balance=balance):
                processed_count += 1
            else:
                skipped_count += 1

        run_record.completed_at = timezone.now()
        run_record.save(update_fields=["completed_at"])

    logger.info(
        "Year-end carry forward completed for %s. Processed=%s, Skipped=%s",
        processing_year, processed_count,skipped_count,
    )
    return True


def print_year_end_dry_run():
    status = get_year_end_carry_forward_status()
    completed_at = status["completed_at"]
    completed_text = (
        timezone.localtime(completed_at).strftime("%b %d, %Y %I:%M %p")
        if completed_at
        else "not completed"
    )

    print("--- Year-End Carry Forward Dry Run ---")
    print("No leave balances will be changed in this summary.")
    print(f"Year: {status['year']}")
    print(f"Date: {status['today']}")
    print(f"Protected year: {'yes' if status['is_protected'] else 'no'}")
    print(f"Run status: {completed_text}")
    print(f"Eligible balances: {status['eligible_count']}")
    print(f"Decision: {'would run' if status['should_run'] else 'would skip'}")
    print(f"Reason: {status['reason']}")
    return status


def main():
    parser = argparse.ArgumentParser(description="Inspect or run year-end leave carry forward.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen and exit.")
    args = parser.parse_args()

    status = print_year_end_dry_run()

    if args.dry_run:
        return

    if not status["should_run"]:
        print("No action needed. Year-end carry forward was not run.")
        return

    print("\nThis will update employee leave balances.")
    print("Take a database backup before running this.")
    confirmation_phrase = (
        "PRODUCTION_RUN_YEAR_END_CARRY_FORWARD"
        if not settings.DEBUG
        else "RUN_YEAR_END_CARRY_FORWARD"
    )
    if not settings.DEBUG:
        print("PRODUCTION MODE DETECTED.")
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = input(f"Type {confirmation_phrase} to continue: ").strip()

    if confirmation != confirmation_phrase:
        print("Cancelled. Year-end carry forward was not run.")
        return

    did_run = run_year_end_carry_forward_if_due()
    if did_run:
        print("SUCCESS: Year-end carry forward completed.")
    else:
        print("SKIPPED: Year-end carry forward did not run.")


if __name__ == "__main__":
    main()
