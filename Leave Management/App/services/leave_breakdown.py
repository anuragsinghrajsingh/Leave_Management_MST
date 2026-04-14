from datetime import timedelta
from App.models import CompanyHoliday


def calculate_leave_breakdown(start_date, end_date):
    """
    Returns detailed breakdown of leave days:
        - total calendar days
        - weekend days
        - holiday days
        - working leave days
        - excluded dates list
    """

    total_days = (end_date - start_date).days + 1
    weekend_days = 0
    holiday_days = 0
    working_days = 0
    excluded_dates = []

    holidays = set(CompanyHoliday.objects.filter(date__range=(start_date, end_date)).values_list("date", flat=True))

    current = start_date

    while current <= end_date:

        is_weekend = current.weekday() in (5, 6)
        is_holiday = current in holidays

        if is_weekend:
            weekend_days += 1
            excluded_dates.append((current, "Weekend"))

        elif is_holiday:
            holiday_days += 1
            excluded_dates.append((current, "Holiday"))

        else:
            working_days += 1

        current += timedelta(days=1)

    return {"total_days": total_days, "weekend_days": weekend_days, "holiday_days": holiday_days, "working_days": working_days, "excluded_dates": excluded_dates,}