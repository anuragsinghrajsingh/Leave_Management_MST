from django.db import models
# from django.contrib.auth.models import User
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import time
from django.db.models import Count
from django.utils.timezone import now



class CustomUser(AbstractUser):

    ROLE_CHOICES = (
        ('Admin', 'Admin'),
        ('HR', 'HR'),
        ('EMPLOYEE', 'Employee'),
    )

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    
    def save(self, *args, **kwargs):
        # 🔥 Auto-set staff permission for ADMIN
        if self.role == "Admin":
            self.is_staff = True
        else:
            self.is_staff = False  # optional but cleaner

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.username} - {self.role}"
    
    
    
    

# class Leave(models.Model):
#     LEAVE_TYPE = [
#         ('Casual', 'Casual'),
#         ('Sick', 'Sick'),
#         ('Earned', 'Earned'),
#     ]

#     STATUS = [
#         ('Pending', 'Pending'),
#         ('Approved', 'Approved'),
#         ('Rejected', 'Rejected'),
#     ]

#     # user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves')
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaves')


#     leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE)
#     from_date = models.DateField()
#     to_date = models.DateField()
#     reason = models.TextField()

#     status = models.CharField(max_length=20, choices=STATUS, default='Pending')

#     created_at = models.DateTimeField(auto_now_add=True)
    
#     rejection_reason = models.TextField(blank=True, null=True)


#     def __str__(self):
#         return f"{self.user.username} - {self.leave_type}"




# class Leave(models.Model):
#     LEAVE_TYPE = [
#         ("Short", "Short"),
#         ("Half", "Half Day"),
#         ('Casual', 'Casual'),
#         ('Sick', 'Sick'),
#         ('Earned', 'Earned'),
#     ]

#     STATUS = [
#         ('Pending', 'Pending'),
#         ('Approved', 'Approved'),
#         ('Rejected', 'Rejected'),
#     ]

#     # user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves')
#     user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaves')


#     leave_type = models.CharField(max_length=20, choices=LEAVE_TYPE)
    
#     from_date = models.DateField()
#     # from_time = models.TimeField(blank=True, null=True)
    
#     to_date = models.DateField()
#     # to_time = models.TimeField(blank=True, null=True)
    
#     reason = models.TextField()

#     status = models.CharField(max_length=20, choices=STATUS, default='Pending')

#     created_at = models.DateTimeField(auto_now_add=True)
    
#     rejection_reason = models.TextField(blank=True, null=True)


#     def __str__(self):
#         return f"{self.user.username} - {self.leave_type}"



class Leave(models.Model):

    LEAVE_TYPES = [
        ("Short", "Short"),
        ("Half", "Half"),
        ("Casual", "Casual"),
        ("Sick", "Sick"),
        ("Earned", "Earned"),
    ]
    
    STATUS = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    DEDUCTION_SOURCE = [
        ("Earned", "Earned"),
        ("Sick", "Sick"),
        ("Unpaid", "Unpaid"),
        ("None", "None"),
    ]

    # user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='leaves')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaves')

    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)

    # Date range
    created_at = models.DateTimeField(auto_now_add=True)
    from_date = models.DateField()
    to_date = models.DateField()

    # Time support
    from_datetime = models.DateTimeField()
    to_datetime = models.DateTimeField()

    reason = models.TextField()
    rejection_reason = models.TextField(blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS, default="Pending")
    updated_at = models.DateTimeField(blank=True, null=True)
    no_of_times_updated = models.PositiveIntegerField(default=0)
    rejected_at = models.DateTimeField(blank=True, null=True)
    approved_at = models.DateTimeField(blank=True, null=True)

    deducted_from = models.CharField( max_length=20, choices=DEDUCTION_SOURCE, default="None")



    def clean(self):

        if self.leave_type in ["Short", "Half"]:

            if not self.from_datetime or not self.to_datetime:
                raise ValidationError("Time required for Short/Half leave")

            # same day check
            if self.from_datetime.date() != self.to_datetime.date():
                raise ValidationError("Short/Half leave must be single day")

            # working hours (10 AM – 7 PM)
            if self.from_datetime.time() < time(10, 0) or self.to_datetime.time() > time(19, 0):
                raise ValidationError("Allowed time: 10 AM to 7 PM")

            duration = (self.to_datetime - self.from_datetime).total_seconds() / 3600

            if self.leave_type == "Short" and duration > 2:
                raise ValidationError("Short leave max 2 hours")

            if self.leave_type == "Half" and duration > 4:
                raise ValidationError("Half leave max 4 hours")


    
    

    def save(self, *args, **kwargs):

        month = self.from_date.month
        year = self.from_date.year

        short_count = Leave.objects.filter(
            user=self.user,
            leave_type="Short",
            from_date__month=month,
            from_date__year=year
        ).count()

        half_count = Leave.objects.filter(
            user=self.user,
            leave_type="Half",
            from_date__month=month,
            from_date__year=year
        ).count()

        if self.leave_type == "Short" and short_count >= 2:
            print("⚠ Warning: More than 2 short leaves this month")

        if self.leave_type == "Half" and half_count >= 1:
            print("⚠ Warning: More than 1 half leave this month")

        super().save(*args, **kwargs)
    
    
    def __str__(self):
        return f"{self.user.username} - {self.leave_type}"



# class LeaveBalance(models.Model):
    
#     # user = models.OneToOneField(User, on_delete=models.CASCADE)
    
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)


#     total_leaves = models.IntegerField(default=30)

#     sick_total = models.IntegerField(default=15)
#     sick_used = models.IntegerField(default=0)

#     earned_total = models.IntegerField(default=15)
#     earned_used = models.IntegerField(default=0)

#     unpaid = models.IntegerField(default=0)

#     def __str__(self):
#         return f"{self.user.username} Leave Balance"



class LeaveBalance(models.Model):
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    total_leaves = models.FloatField(default=27)

    sick_total = models.FloatField(default=12)
    sick_used = models.FloatField(default=0)

    earned_total = models.FloatField(default=15)
    earned_used = models.FloatField(default=0)

    unpaid = models.FloatField(default=0)
    
    def __str__(self):
        return f"{self.user.username} Leave Balance"





class CompanyHoliday(models.Model):
    """
    Company-wide holiday for a specific date.
    These dates are excluded from leave calculations.
    """

    name = models.CharField(max_length=200)
    date = models.DateField(unique=True, db_index=True)

    created_at = models.DateTimeField(auto_now_add=True)
    
    is_optional = models.BooleanField(default=False, help_text="If True, employees may choose whether to apply leave.")

    class Meta:
        ordering = ["date"]
        verbose_name = "Company Holiday"
        verbose_name_plural = "Company Holidays"

    def __str__(self):
        return f"{self.name} - {self.date.strftime('%d %b %Y')}"







class Profile(models.Model):

    ROLE_CHOICES = (
        ("Admin", "Admin"),
        ("HR", "HR"),
        ("EMPLOYEE", "Employee"),
    )

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # -------- Non-editable by user --------
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.CharField(max_length=100)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    date_of_joining = models.DateField()
    phone = models.CharField(max_length=15, unique=True)

    # -------- Editable by user --------
    address = models.TextField(blank=True)
    profile_photo = models.ImageField(upload_to="profile_photos/", blank=True, null=True, default=None)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"


class Communication(models.Model):

    MESSAGE_TYPES = [
        ("ANNOUNCEMENT", "Announcement"),
        ("DIRECT", "Direct Message"),
    ]

    AUDIENCE_ROLES = [
        ("HR", "HR"),
        ("EMPLOYEE", "Employee"),
    ]

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sent_communications",
    )
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="received_communications",
        null=True,
        blank=True,
    )
    message_type = models.CharField(max_length=20, choices=MESSAGE_TYPES)
    audience_role = models.CharField(max_length=20, choices=AUDIENCE_ROLES, blank=True, null=True)
    title = models.CharField(max_length=140, blank=True)
    body = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        label = self.title or self.get_message_type_display()
        return f"{self.sender.username} - {label}"


class CommunicationRead(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="communication_reads",
    )
    communication = models.ForeignKey(
        Communication,
        on_delete=models.CASCADE,
        related_name="read_receipts",
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "communication")]
        ordering = ["-read_at"]


class CommunicationSeen(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="communication_seen_entries",
    )
    communication = models.ForeignKey(
        Communication,
        on_delete=models.CASCADE,
        related_name="seen_receipts",
    )
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "communication")]
        ordering = ["-seen_at"]


class LeaveNotificationRead(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_notification_reads",
    )
    leave = models.ForeignKey(
        Leave,
        on_delete=models.CASCADE,
        related_name="notification_reads",
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "leave")]
        ordering = ["-read_at"]


class LeaveNotificationSeen(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="leave_notification_seen_entries",
    )
    leave = models.ForeignKey(
        Leave,
        on_delete=models.CASCADE,
        related_name="notification_seen_receipts",
    )
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("user", "leave")]
        ordering = ["-seen_at"]








# class LeaveHourBalance(models.Model):
    
#     # user = models.OneToOneField(User, on_delete=models.CASCADE)
    
#     user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

#     hour_total = models.IntegerField(default=4)
#     hour_used = models.IntegerField(default=0)

#     def __str__(self):
#         return f"{self.user.username} Leave Balance"


# class LeaveAuditLog(models.Model):
    
#     leave = models.ForeignKey( "Leave", on_delete=models.CASCADE, related_name="audit_logs")
    
#     edited_by = models.ForeignKey( User, on_delete=models.SET_NULL, null=True)
#     edited_at = models.DateTimeField(auto_now_add=True)

#     changes = models.JSONField()  # before → after
#     action = models.CharField(max_length=50, default="EDIT")

#     def __str__(self):
#         return f"Leave {self.leave.id} edited by {self.edited_by}"
