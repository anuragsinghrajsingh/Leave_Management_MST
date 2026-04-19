from App.models import Leave, LeaveBalance
from django.contrib.auth import get_user_model

def run():
    print("Script loaded")
    def days(leave):
        return (leave.to_date - leave.from_date).days + 1

    user_model = get_user_model()

    for user in user_model.objects.all():
        balance, _ = LeaveBalance.objects.get_or_create(
            user=user,
            defaults={
                "total_leave_balance": 27,
                "total_leave_remaining": 27,
                "sick_total": 12,
                "earned_total": 15,
            }
        )

        balance.sick_used = 0
        balance.earned_used = 0
        balance.unpaid = 0

        for leave in Leave.objects.filter(user=user):
            d = days(leave)

            if leave.leave_type == "Sick":
                balance.sick_used += d
            elif leave.leave_type == "Earned":
                balance.earned_used += d
            elif leave.leave_type == "Unpaid":
                balance.unpaid += d

        balance.total_leave_balance = balance.sick_total + balance.earned_total
        balance.total_leave_remaining = max(
            (balance.sick_total - balance.sick_used) + (balance.earned_total - balance.earned_used),
            0
        )

        balance.save()

    print("Leave balances synced successfully.")
