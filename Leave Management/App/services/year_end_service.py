import logging
from datetime import date
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from App.models import LeaveBalance, YearEndCarryForwardRun

logger = logging.getLogger(__name__)


def process_year_end_carry_forward(user, today=None, balance=None):

    balance = balance or user.leavebalance

    today = today or date.today()
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

    # Run automatically during January so the rollover still happens
    # even if the app was idle on January 1.
    if today.month != 1:
        return False

    processing_year = today.year

    user_model = get_user_model()
    with transaction.atomic():
        run_record, _ = YearEndCarryForwardRun.objects.select_for_update().get_or_create(
            year=processing_year,
            defaults={"completed_at": None},
        )

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
        processing_year,
        processed_count,
        skipped_count,
    )
    return True
