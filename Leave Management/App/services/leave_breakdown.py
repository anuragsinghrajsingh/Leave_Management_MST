from datetime import timedelta

from App.models import CompanyHoliday
from App.models import Leave


WEEKEND_WEEKDAYS = {5, 6}
WORK_FROM_HOME_WEEKDAYS = {1, 4}  # Tuesday, Friday
FULL_DAY_LEAVE_TYPES = {"Unpaid", "Sick", "Earned"}


def _iter_dates(start_date, end_date):
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _is_wfh_day(target_date, holidays):
    return target_date not in holidays and target_date.weekday() in WORK_FROM_HOME_WEEKDAYS


def _is_bridge_day(target_date, holidays):
    return (
        target_date in holidays
        or target_date.weekday() in WEEKEND_WEEKDAYS
        or _is_wfh_day(target_date, holidays)
    )


def _resolve_requested_range(start_date, end_date, requested_start_date=None, requested_end_date=None):
    return (
        requested_start_date or start_date,
        requested_end_date or end_date,
    )


def _starts_after_consecutive_weekend(requested_start_date):
    previous_day = requested_start_date - timedelta(days=1)
    two_days_before = requested_start_date - timedelta(days=2)
    return previous_day.weekday() == 6 and two_days_before.weekday() == 5


def expand_full_day_leave_range(user, start_date, end_date, exclude_id=None):
    """
    Auto-expands a full-day leave request across bridge days when it is
    separated from another full-day leave only by WFH/weekend/holiday dates.

    Example:
        Existing leave: Monday
        New request: Wednesday
        Gap: Tuesday (WFH)
        Result: Tuesday -> Wednesday
    """

    adjusted_start = start_date
    adjusted_end = end_date
    auto_added_dates = set()
    holidays = set(
        CompanyHoliday.objects.filter(date__range=(start_date - timedelta(days=10), end_date + timedelta(days=10))).values_list("date", flat=True)
    )

    queryset = Leave.objects.filter(
        user=user,
        status__in=["Pending", "Approved"],
        leave_type__in=FULL_DAY_LEAVE_TYPES,
    ).order_by("from_date")

    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)

    changed = True
    while changed:
        changed = False

        previous_leave = queryset.filter(to_date__lt=adjusted_start).order_by("-to_date").first()
        if previous_leave:
            gap_dates = list(_iter_dates(previous_leave.to_date + timedelta(days=1), adjusted_start - timedelta(days=1)))
            if (
                gap_dates
                and any(_is_wfh_day(current, holidays) for current in gap_dates)
                and all(_is_bridge_day(current, holidays) for current in gap_dates)
            ):
                auto_added_dates.update(gap_dates)
                adjusted_start = gap_dates[0]
                changed = True

        next_leave = queryset.filter(from_date__gt=adjusted_end).order_by("from_date").first()
        if next_leave:
            gap_dates = list(_iter_dates(adjusted_end + timedelta(days=1), next_leave.from_date - timedelta(days=1)))
            if (
                gap_dates
                and any(_is_wfh_day(current, holidays) for current in gap_dates)
                and all(_is_bridge_day(current, holidays) for current in gap_dates)
            ):
                auto_added_dates.update(gap_dates)
                adjusted_end = gap_dates[-1]
                changed = True

    return {
        "start_date": adjusted_start,
        "end_date": adjusted_end,
        "auto_added_dates": sorted(auto_added_dates),
    }


def calculate_leave_breakdown(start_date, end_date, requested_start_date=None, requested_end_date=None):
    """
    Returns detailed breakdown of leave days.

    Rule order:
        A. Sandwich weekend rule
        B. Work-from-home (Tuesday/Friday) informational rule
    """

    total_days = (end_date - start_date).days + 1
    weekend_days = 0
    holiday_days = 0
    company_holiday_days = 0
    working_days = 0
    excluded_dates = []

    requested_start_date, requested_end_date = _resolve_requested_range(
        start_date,
        end_date,
        requested_start_date=requested_start_date,
        requested_end_date=requested_end_date,
    )

    company_holidays = set(
        CompanyHoliday.objects.filter(date__range=(start_date, end_date)).values_list("date", flat=True)
    )
    all_dates = list(_iter_dates(start_date, end_date))
    requested_dates = list(_iter_dates(requested_start_date, requested_end_date))

    included_weekend_dates = set()
    if _starts_after_consecutive_weekend(requested_start_date):
        interior_weekend_dates = [
            current for current in requested_dates
            if requested_start_date < current < requested_end_date and current.weekday() in WEEKEND_WEEKDAYS and current not in company_holidays
        ]
        included_weekend_dates.update(interior_weekend_dates)

    # Part B: WFH informational rule applies after part A.
    included_wfh_dates = [
        current for current in all_dates
        if current not in company_holidays
        and current.weekday() in WORK_FROM_HOME_WEEKDAYS
        and (current in requested_dates or current < requested_start_date or current > requested_end_date)
    ]

    for current in all_dates:
        is_company_holiday = current in company_holidays
        is_weekend = current.weekday() in WEEKEND_WEEKDAYS

        if is_company_holiday:
            company_holiday_days += 1

        if is_weekend and current not in included_weekend_dates:
            weekend_days += 1
            excluded_dates.append((current, "Weekend"))
            continue

        working_days += 1

    return {
        "total_days": total_days,
        "weekend_days": weekend_days,
        "holiday_days": holiday_days,
        "company_holiday_days": company_holiday_days,
        "working_days": working_days,
        "excluded_dates": excluded_dates,
        "included_weekend_days": len(included_weekend_dates),
        "included_weekend_dates": sorted(included_weekend_dates),
        "included_wfh_days": len(included_wfh_dates),
        "included_wfh_dates": included_wfh_dates,
    }


def calculate_leave_breakdown_for_leave(leave):
    return calculate_leave_breakdown(
        leave.from_date,
        leave.to_date,
        requested_start_date=getattr(leave, "requested_from_date", None),
        requested_end_date=getattr(leave, "requested_to_date", None),
    )
