# This file defines the core data models for the leave management system, including user profiles, 
# leave requests, leave balances, company holidays, work-from-home days, and communication entities.
# Each model includes fields relevant to its purpose, along with methods for validation, string 
# representation, and any necessary business logic. The models are designed to support the functionality of the leave management 
# system, allowing for efficient data storage and retrieval while enforcing the rules and policies defined by the organization.    



from django.db import models, transaction
import logging
import re
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from django.core.exceptions import ValidationError
from datetime import time
from django.db.models import Count
from django.utils import timezone
from django.utils.timezone import now
from App.services.profile_photo_storage import ProfilePhotoStorage


logger = logging.getLogger("lms_security")




# The CustomUser model extends Django's AbstractUser to include a role field (Admin, HR, Employee) 
# and automatically sets staff permissions for Admins. The save method ensures that the is_staff flag is correctly set based on 
# the user's role, and the string representation provides a clear display of the username and role for easy identification in the 
# admin interface and other parts of the application. This model serves as the foundation for user management within the leave 
# management system, allowing for role-based access control and user-specific functionality throughout the application.  

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





# The Leave model captures all details of a leave request, including type, date range, reason, status, and deduction source.
# It includes validation logic for short and half-day leaves and a save method that checks for monthly limits on these leave types, 
# printing warnings if limits are exceeded.

class Leave(models.Model):

    LEAVE_TYPES = [
        ("Short", "Short"),
        ("Half", "Half"),
        ("Unpaid", "Unpaid"),
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

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='leaves')

    leave_type = models.CharField(max_length=20, choices=LEAVE_TYPES)

    # Date range
    created_at = models.DateTimeField(auto_now_add=True)
    from_date = models.DateField()
    to_date = models.DateField()
    requested_from_date = models.DateField(blank=True, null=True)
    requested_to_date = models.DateField(blank=True, null=True)

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
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_leaves",
        blank=True,
        null=True,
    )

    deducted_from = models.CharField( max_length=20, choices=DEDUCTION_SOURCE, default="None")


    def clean(self):
        super().clean()

        if getattr(self, "_skip_model_validation", False):
            return

        if self.leave_type in ["Short", "Half"]:

            if not self.from_datetime or not self.to_datetime:
                raise ValidationError("Time required for Short/Half leave")

            # same day check
            from_datetime = timezone.localtime(self.from_datetime) if timezone.is_aware(self.from_datetime) else self.from_datetime
            to_datetime = timezone.localtime(self.to_datetime) if timezone.is_aware(self.to_datetime) else self.to_datetime

            if from_datetime.date() != to_datetime.date():
                raise ValidationError("Short/Half leave must be single day")

            # working hours (10 AM – 7 PM)
            if from_datetime.time() < time(10, 0) or to_datetime.time() > time(19, 0):
                raise ValidationError("Allowed time: 10 AM to 7 PM")

            duration = (to_datetime - from_datetime).total_seconds() / 3600

            if duration <= 0:
                raise ValidationError("Leave end time must be after start time")

            if self.leave_type == "Short" and duration > 2:
                raise ValidationError("Short leave max 2 hours")

            if self.leave_type == "Half" and duration > 4:
                raise ValidationError("Half leave max 4 hours")

            if self.user_id and self.from_date and self.status in ["Pending", "Approved"]:
                monthly_leaves = Leave.objects.filter(
                    user=self.user,
                    leave_type=self.leave_type,
                    from_date__month=self.from_date.month,
                    from_date__year=self.from_date.year,
                    status__in=["Pending", "Approved"],
                )

                if self.pk:
                    monthly_leaves = monthly_leaves.exclude(pk=self.pk)

                if self.leave_type == "Short" and monthly_leaves.count() >= 2:
                    logger.warning(
                        "LEAVE_MONTHLY_LIMIT_BLOCKED | user_id=%s | leave_type=%s | year=%s | month=%s | existing_count=%s | limit=%s",
                        self.user_id,
                        self.leave_type,
                        self.from_date.year,
                        self.from_date.month,
                        monthly_leaves.count(),
                        2,
                    )
                    raise ValidationError("Maximum 2 Short leaves allowed per month.")

                if self.leave_type == "Half" and monthly_leaves.count() >= 1:
                    logger.warning(
                        "LEAVE_MONTHLY_LIMIT_BLOCKED | user_id=%s | leave_type=%s | year=%s | month=%s | existing_count=%s | limit=%s",
                        self.user_id,
                        self.leave_type,
                        self.from_date.year,
                        self.from_date.month,
                        monthly_leaves.count(),
                        1,
                    )
                    raise ValidationError("Only 1 Half-day leave allowed per month.")


    def save(self, *args, **kwargs):
        skip_validation = kwargs.pop("skip_validation", False) or getattr(self, "_skip_model_validation", False)
        update_fields = kwargs.get("update_fields")
        validation_fields = {
            "user",
            "leave_type",
            "from_date",
            "to_date",
            "requested_from_date",
            "requested_to_date",
            "from_datetime",
            "to_datetime",
            "reason",
            "deducted_from",
        }

        if not skip_validation and (self._state.adding or update_fields is None or validation_fields.intersection(update_fields)):
            self.full_clean()

        super().save(*args, **kwargs)
    
    
    def __str__(self):
        return f"{self.user.username} - {self.leave_type}"





# The LeaveBalance model tracks the total and remaining leave balances for each user, including breakdowns for sick and earned leaves,
#  as well as any unpaid leave. It also includes a method to ensure that the total remaining leave cannot be negative and a string 
# representation for easy identification.    

class LeaveBalance(models.Model):
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    total_leave_balance = models.FloatField(default=27)
    total_leave_remaining = models.FloatField(default=27)

    sick_total = models.FloatField(default=12)
    sick_used = models.FloatField(default=0)

    earned_total = models.FloatField(default=15)
    earned_used = models.FloatField(default=0)

    unpaid = models.FloatField(default=0)
    last_year_end_processed = models.PositiveIntegerField(blank=True, null=True)

    def save(self, *args, **kwargs):
        self.total_leave_remaining = max(float(self.total_leave_remaining or 0), 0)
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.user.username} Leave Balance"






# The CompanyHoliday model defines company-wide holidays with a name and date. Employees cannot apply for leave on these dates, 
# but they still count if they fall within a leave range. The WorkFromHomeDay model specifies which weekdays are designated as 
# work-from-home days, allowing for flexible leave calculations that can automatically include adjacent work-from-home days. 
# When determining the effective leave period. This enables scenarios where a single day of leave can be surrounded by 
# work-from-home days, effectively extending the leave duration without additional leave days being deducted from the employee's 
# balance. This design allows for a more accurate and employee-friendly calculation of leave periods, taking into account the 
# realities of modern work arrangements and company policies.   

class YearEndCarryForwardRun(models.Model):
    year = models.PositiveIntegerField(unique=True)
    completed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-year"]
        verbose_name = "Year-end carry forward run"
        verbose_name_plural = "Year-end carry forward runs"

    def __str__(self):
        status = "completed" if self.completed_at else "pending"
        return f"{self.year} carry forward ({status})"





# The CompanyHoliday model defines company-wide holidays with a name and date. Employees cannot apply for leave on these dates, 
# but they still count if they fall within a leave range. The WorkFromHomeDay model specifies which weekdays are designated as 
# work-from-home days, allowing for flexible leave calculations that can automatically include adjacent work-from-home days 
# when determining the effective leave period.   

class CompanyHoliday(models.Model):
    """
    Company-wide holiday for a specific date.
    Employees cannot apply leave only for a blocked company holiday date,
    but the day still counts when it falls inside a wider leave range.
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





# The WorkFromHomeDay model specifies which weekdays are designated as work-from-home days, allowing for flexible leave calculations 
# that can automatically include adjacent work-from-home days. When determining the effective leave period. This enables scenarios 
# where a single day of leave can be

class WorkFromHomeDay(models.Model):
    WEEKDAY_CHOICES = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES, unique=True)
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["weekday"]
        verbose_name = "Work From Home Day"
        verbose_name_plural = "Work From Home Days"

    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"{self.get_weekday_display()} - {status}"






# The Profile model extends the user model with additional fields such as employee ID, department, role, date of joining, and 
# contact information. It includes a method to generate unique employee IDs based on the user's role, ensuring that IDs are never 
# reused even if a user is deleted. The save method automatically generates an employee ID if it's missing and a role is assigned, 
# maintaining data integrity and consistency across the system. The Communication and related models facilitate internal messaging 
# between users, allowing for announcements and direct messages with tracking for read and seen statuses. The LeaveNotificationRead
#  and LeaveNotificationSeen models track when users have read or seen notifications related to their leave requests, ensuring that 
# important updates are acknowledged.

class Profile(models.Model):
    # --- Production Level ID Configuration ---
    EMPLOYEE_ID_PREFIX = "MST"
    ID_PADDING = 4

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
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)

    # -------- Editable by user --------
    address = models.TextField(blank=True)
    profile_photo = models.ImageField(
        upload_to="profile_photos/",
        storage=ProfilePhotoStorage(),
        blank=True,
        null=True,
        default=None,
    )
    profile_photo_update_count = models.PositiveIntegerField(default=0)
    bio = models.TextField(blank=True)

    def __str__(self):
        return f"{self.user.username} Profile"

    @property
    def has_profile_photo_file(self):
        if not self.profile_photo or not self.profile_photo.name:
            return False

        try:
            return self.profile_photo.storage.exists(self.profile_photo.name)
        except Exception:
            return False

    @classmethod
    def generate_next_id(cls, role):
        """
        STRICT INCREMENT LOGIC.
        Finds the highest existing number for the role and adds 1.
        Numbers are NEVER reused even if a user is deleted.
        """
        role_map = {
            "Admin": "MST_Admin-",
            "HR": "MST_HR-",
            "EMPLOYEE": cls.EMPLOYEE_ID_PREFIX,
        }
        prefix = role_map.get(role, cls.EMPLOYEE_ID_PREFIX)
        
        with transaction.atomic():
            # Get existing IDs ONLY for this specific role's prefix
            existing_ids = cls.objects.select_for_update().filter(
                employee_id__startswith=prefix
            ).values_list('employee_id', flat=True)
            
            highest_num = 0
            pattern = rf"^{re.escape(prefix)}(\d+)$"
            
            for eid in existing_ids:
                match = re.match(pattern, eid)
                if match:
                    num = int(match.group(1))
                    if num > highest_num:
                        highest_num = num
            
            # Find the next available number (Strict Increment)
            next_num = highest_num + 1
            return f"{prefix}{next_num:0{cls.ID_PADDING}d}"

    def save(self, *args, **kwargs):
        # Auto-generate ID only if it's missing AND a role is assigned
        if not self.employee_id and self.role:
            self.employee_id = self.generate_next_id(self.role)
        super().save(*args, **kwargs)






# The Communication and related models facilitate internal messaging between users, allowing for announcements and direct messages 
# with tracking for read and seen statuses. The LeaveNotificationRead and LeaveNotificationSeen models track when users have read or 
# seen notifications related to their leave requests, ensuring that important updates are acknowledged. The calculate_leave_breakdown
#  function computes the effective leave period by automatically including adjacent work-from-home days and excluding company holidays,
#  providing a comprehensive breakdown of the leave duration and any additional days added to the original request.

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

    def clean(self):
        super().clean()

        for field_name in ("title", "body"):
            value = getattr(self, field_name, "") or ""
            if "<" in value or ">" in value:
                raise ValidationError({
                    field_name: "HTML markup is not allowed in communication messages."
                })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        label = self.title or self.get_message_type_display()
        return f"{self.sender.username} - {label}"




# The calculate_leave_breakdown function computes the effective leave period by automatically including adjacent work-from-home days 
# and excluding company holidays, providing a comprehensive breakdown of the leave duration and any additional days added to the 
# original request. It iteratively checks for gaps between the requested leave and existing approved leaves, adjusting the start and 
# end dates accordingly while ensuring that only valid work-from-home days are included. The function returns the adjusted leave 
# period along with any auto-added dates, giving a clear picture of the total leave duration after accounting for company policies 
# and calendar factors.
# The Communication and related models facilitate internal messaging between users, allowing for announcements and direct messages 
# with tracking for read and seen statuses. The LeaveNotificationRead and LeaveNotificationSeen models track when users have read 
# or seen notifications related to their leave requests, ensuring that important updates are acknowledged. 

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




# The calculate_leave_breakdown function computes the effective leave period by automatically including adjacent work-from-home days 
# and excluding company holidays, providing a comprehensive breakdown of the leave duration and any additional days added to the 
# original request. It iteratively checks for gaps between the requested leave and existing approved leaves, adjusting the start and 
# end dates accordingly while ensuring that only valid work-from-home days are included. The function returns the adjusted leave 
# period along with any auto-added dates, giving a clear picture of the total leave duration after accounting for company policies 
# and calendar factors.   

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





# The calculate_leave_breakdown function computes the effective leave period by automatically including adjacent work-from-home days 
# and excluding company holidays, providing a comprehensive breakdown of the leave duration and any additional days added to the 
# original request. It iteratively checks for gaps between the requested leave and existing approved leaves, adjusting the start and 
# end dates accordingly while ensuring that only valid work-from-home days are included. The function returns the adjusted leave
#  period along with any auto-added dates, giving a clear picture of the total leave duration after accounting for company policies 
# and calendar factors.   

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



# The calculate_leave_breakdown function computes the effective leave period by automatically including adjacent work-from-home days 
# and excluding company holidays, providing a comprehensive breakdown of the leave duration and any additional days added to the 
# original request. It iteratively checks for gaps between the requested leave and existing approved leaves, adjusting the start and 
# end dates accordingly while ensuring that only valid work-from-home days are included. The function returns the adjusted leave 
# period along with any auto-added dates, giving a clear picture of the total leave duration after accounting for company policies 
# and calendar factors.   

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
