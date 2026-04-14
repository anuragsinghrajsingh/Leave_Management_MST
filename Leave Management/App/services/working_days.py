from datetime import timedelta
from App.models import CompanyHoliday


def calculate_working_days(start_date, end_date):
    """
    Returns number of working days between two dates,
    excluding:
        - Saturdays
        - Sundays
        - Company holidays
    """

    total_days = 0
    current = start_date

    # Fetch holidays in range
    holidays = set(CompanyHoliday.objects.filter(date__range=(start_date, end_date)).values_list("date", flat=True))

    while current <= end_date:

        is_weekend = current.weekday() in (5, 6)  # 5=Saturday, 6=Sunday
        is_holiday = current in holidays

        if not is_weekend and not is_holiday:
            total_days += 1

        current += timedelta(days=1)

    return total_days