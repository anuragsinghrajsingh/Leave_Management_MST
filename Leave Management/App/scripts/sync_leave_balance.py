from App.models import Leave, LeaveBalance
from django.contrib.auth.models import User

def run():
    print("Script loaded")
    def days(leave):
        return (leave.to_date - leave.from_date).days + 1

    for user in User.objects.all():
        balance, _ = LeaveBalance.objects.get_or_create(
            user=user,
            defaults={
                "total_leaves": 30,
                "sick_total": 15,
                "privilege_total": 15
            }
        )

        balance.sick_used = 0
        balance.privilege_used = 0
        balance.casual_used = 0

        for leave in Leave.objects.filter(user=user):
            d = days(leave)

            if leave.leave_type == "Sick":
                balance.sick_used += d
            elif leave.leave_type == "Privilege":
                balance.privilege_used += d
            elif leave.leave_type == "Casual":
                balance.casual_used += d

            balance.total_leaves -= d

        balance.save()

    print("Leave balances synced successfully.")