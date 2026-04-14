from datetime import date
from django.db import transaction

def process_year_end_carry_forward(user):

    balance = user.leavebalance

    today = date.today()

    years_of_service = (today - user.profile.date_of_joining).days // 365

    if years_of_service <= 3:
        carry_limit = 7.5
    else:
        carry_limit = 10.5

    earned_remaining = balance.earned_total - balance.earned_used

    carry_forward = min(earned_remaining, carry_limit)

    with transaction.atomic():

        balance.earned_total = carry_forward
        balance.earned_used = 0

        balance.total_leaves = (
            carry_forward +
            (balance.sick_total - balance.sick_used)
        )

        balance.save()