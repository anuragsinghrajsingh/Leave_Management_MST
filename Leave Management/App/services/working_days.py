from datetime import timedelta
def calculate_working_days(start_date, end_date):
    """
    Returns number of working days between two dates,
    excluding:
        - Saturdays
        - Sundays
    Company holidays are counted as leave days when they fall inside a
    selected leave range.
    """

    total_days = 0
    current = start_date

    while current <= end_date:

        is_weekend = current.weekday() in (5, 6)  # 5=Saturday, 6=Sunday

        if not is_weekend:
            total_days += 1

        current += timedelta(days=1)

    return total_days
