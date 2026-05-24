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

logger = logging.getLogger("lms_service_year_end")

SKIP_YEAR_END_YEARS = {2026}


def get_year_end_carry_forward_status(today=None):
    today = today or timezone.localdate()
    processing_year = today.year
    run_record = YearEndCarryForwardRun.objects.filter(year=processing_year).first()
    is_protected = processing_year in SKIP_YEAR_END_YEARS
    is_completed = bool(run_record and run_record.completed_at)
    eligible_count = (
        LeaveBalance.objects
        .filter(user__role="EMPLOYEE", user__profile__isnull=False)
        .exclude(last_year_end_processed=processing_year)
        .count()
    )
    processable_count = (
        LeaveBalance.objects
        .filter(user__role="EMPLOYEE", user__is_active=True, user__profile__isnull=False)
        .exclude(last_year_end_processed=processing_year)
        .count()
    )
    already_processed_count = LeaveBalance.objects.filter(
        user__role="EMPLOYEE",
        last_year_end_processed=processing_year,
    ).count()
    missing_profile_count = LeaveBalance.objects.filter(
        user__role="EMPLOYEE",
        user__profile__isnull=True,
    ).count()
    ignored_non_employee_count = LeaveBalance.objects.exclude(user__role="EMPLOYEE").count()

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

    status = {
        "year": processing_year,
        "today": today,
        "is_protected": is_protected,
        "is_completed": is_completed,
        "completed_at": run_record.completed_at if run_record else None,
        "eligible_count": eligible_count,
        "processable_count": processable_count,
        "already_processed_count": already_processed_count,
        "missing_profile_count": missing_profile_count,
        "ignored_non_employee_count": ignored_non_employee_count,
        "should_run": should_run,
        "reason": reason,
    }
    logger.info(
        "YEAR_END | STATUS | Year=%s | Protected=%s | Completed=%s | Eligible=%s | ShouldRun=%s | Reason=%s",
        processing_year,
        is_protected,
        is_completed,
        eligible_count,
        should_run,
        reason,
    )
    return status


def process_year_end_carry_forward(user, today=None, balance=None):

    balance = balance or user.leavebalance

    today = today or timezone.localdate()
    processing_year = today.year

    if balance.last_year_end_processed == processing_year:
        logger.info("YEAR_END | BALANCE_SKIP | User=%s | Year=%s | Already processed.", user.pk, processing_year)
        return False

    profile = getattr(user, "profile", None)
    if not profile or not profile.date_of_joining:
        logger.warning("YEAR_END | BALANCE_SKIP | User=%s | Missing profile/date_of_joining.", user.pk)
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

    logger.info(
        "YEAR_END | BALANCE_PROCESSED | User=%s | Year=%s | YearsOfService=%s | CarryForward=%s",
        user.pk,
        processing_year,
        years_of_service,
        carry_forward,
    )
    return True


def run_year_end_carry_forward_if_due(today=None):
    today = today or timezone.localdate()

    processing_year = today.year

    if processing_year in SKIP_YEAR_END_YEARS:
        logger.info(
            "YEAR_END | SKIPPED | Protected year %s.",
            processing_year,
        )
        return False

    user_model = get_user_model()
    with transaction.atomic():
        run_record, _ = YearEndCarryForwardRun.objects.select_for_update().get_or_create(
            year=processing_year, defaults={"completed_at": None},)

        if run_record.completed_at:
            logger.info("YEAR_END | SKIPPED | Year=%s | Already completed at %s.", processing_year, run_record.completed_at)
            return False

        eligible_balances = (
            LeaveBalance.objects
            .select_for_update()
            .select_related("user", "user__profile")
            .filter(user__role="EMPLOYEE", user__is_active=True, user__profile__isnull=False)
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
        "YEAR_END | COMPLETED | Year=%s | Processed=%s | Skipped=%s",
        processing_year, processed_count,skipped_count,
    )
    return True


def print_year_end_dry_run():
    status = get_year_end_carry_forward_status()
    logger.info(
        "YEAR_END | DRY_RUN | Year=%s | Decision=%s | Reason=%s | Eligible=%s",
        status["year"],
        "would run" if status["should_run"] else "would skip",
        status["reason"],
        status["eligible_count"],
    )
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
    print(f"Pending balance records: {status['eligible_count']}")
    print(f"Active users that can be processed: {status['processable_count']}")
    print(f"Already processed this year: {status['already_processed_count']}")
    print(f"Balance records missing profile: {status['missing_profile_count']}")
    print(f"HR/Admin balance records ignored: {status['ignored_non_employee_count']}")
    print(f"Decision: {'would run' if status['should_run'] else 'would skip'}")
    print(f"Reason: {status['reason']}")
    print("")
    print("Meaning:")
    print("- Pending balance records = employee leave balances not processed for this year yet.")
    print("- Active users that can be processed = pending employee balances for active employees with a profile.")
    print("- Already processed this year = users skipped because year-end already ran for them.")
    print("- HR/Admin balance records ignored = non-employee balances are never processed by year-end.")
    print("- Each processed user may carry forward 0, 7.5, or 10.5 days depending on earned balance and service years.")
    return status


def main():
    logger.info("YEAR_END | MANUAL_RUN | Opened direct runner.")
    parser = argparse.ArgumentParser(description="Inspect or run year-end leave carry forward.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen and exit.")
    args = parser.parse_args()

    status = print_year_end_dry_run()

    if args.dry_run:
        logger.info("YEAR_END | MANUAL_RUN | Dry-run only requested.")
        return

    if not status["should_run"]:
        logger.info("YEAR_END | MANUAL_RUN | No action needed | Reason=%s", status["reason"])
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
        logger.info("YEAR_END | MANUAL_RUN | Cancelled by confirmation.")
        print("Cancelled. Year-end carry forward was not run.")
        return

    logger.info("YEAR_END | MANUAL_RUN | Confirmation accepted.")
    did_run = run_year_end_carry_forward_if_due()
    if did_run:
        print("SUCCESS: Year-end carry forward completed.")
    else:
        print("SKIPPED: Year-end carry forward did not run.")


if __name__ == "__main__":
    main()
