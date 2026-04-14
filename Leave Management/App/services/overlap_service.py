from datetime import date
from typing import List, Dict
from App.models import Leave


def get_overlap_details(user, start_date, end_date, exclude_id=None) -> List[Dict]:
    """
    Returns detailed overlap information for a given date range.

    Args:
        user: User instance
        start_date: New leave start date
        end_date: New leave end date
        exclude_id: Leave ID to exclude (used for edit case)

    Returns:
        List of dictionaries containing overlap details
    """

    queryset = Leave.objects.filter(user=user, from_date__lte=end_date, to_date__gte=start_date, status__in=["Pending", "Approved"]).order_by("from_date")

    if exclude_id:
        queryset = queryset.exclude(id=exclude_id)

    overlaps = []

    for existing in queryset:

        overlap_start = max(existing.from_date, start_date)
        overlap_end = min(existing.to_date, end_date)
        overlap_days = (overlap_end - overlap_start).days + 1

        overlaps.append({
            "leave_type": existing.leave_type,
            "status": existing.status,
            "existing_from": existing.from_date,
            "existing_to": existing.to_date,
            "overlap_from": overlap_start,
            "overlap_to": overlap_end,
            "overlap_days": overlap_days,
        })

    return overlaps