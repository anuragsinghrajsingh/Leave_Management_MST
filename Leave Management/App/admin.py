from django.contrib import admin, messages
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from .models import Leave, LeaveBalance, Profile, CustomUser, WorkFromHomeDay
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from .models import CompanyHoliday
from django import forms
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.http import HttpResponse
from django.utils.html import format_html
from datetime import datetime
import csv
from django.utils.timezone import now, localtime






class ProfileInlineForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = "__all__"

    def clean_employee_id(self):
        eid = self.cleaned_data.get("employee_id")
        if eid:
            # Strictly Block duplicates in Admin with an in-line warning
            # We check if another profile already has this ID
            qs = Profile.objects.filter(employee_id__iexact=eid)
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            
            if qs.exists():
                raise forms.ValidationError(f"The ID '{eid}' is already assigned to another user. Please provide a unique ID.")
        return eid






# class ProfileInline(admin.TabularInline):
class ProfileInline(admin.StackedInline):
    model = Profile
    form = ProfileInlineForm
    can_delete = False
    extra = 0
    max_num = 1

    fields = (
        "employee_id",
        "department",
        "role",
        "date_of_joining",
        "phone",
        "address",
        "profile_photo",
        "bio",
    )

    def photo_preview(self, obj):
        if obj.profile_photo:
            return format_html(
                '<img src="{}" style="width:100px;height:100px;border-radius:8px;" />',
                obj.profile_photo.url
            )
        return "No Image"

    photo_preview.short_description = "Preview"
    
    readonly_fields = ("photo_preview",)    
    
    


    
CustomUser = get_user_model()

# 🔹 Register CustomUser
@login_required
@never_cache
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):

    inlines = [ProfileInline]

    class Media:
        js = ("admin/js/role_sync.js",)
        css = { "all": ("admin/css/custom_admin.css",)}

    # ✅ STEP 1 → CREATE USER (ONLY BASIC FIELDS)
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "password1", "password2"),
        }),
    )

    # ✅ STEP 2 → AFTER SAVE (SHOW FULL DETAILS)
    fieldsets = UserAdmin.fieldsets + (
        ("Role Information", {
            "fields": ("role",),
        }),
    )

    list_display = ("username", "email", "role", "is_active", "is_staff", "is_superuser", "archive_pdf_link")
    search_fields = ("username", "email", "first_name", "last_name", "profile__employee_id")
    
    
    # 🔥 Override the page to force follow the nextstep
    def get_inline_instances(self, request, obj=None):
        if obj is None:
            return []
        return super().get_inline_instances(request, obj)
    
    
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):

        if extra_context is None:
            extra_context = {}

        # 👉 ADD PAGE (object_id is None)
        if object_id is None:
            extra_context["show_save"] = False
            extra_context["show_save_and_add_another"] = False
            extra_context["show_save_and_continue"] = True

        return super().changeform_view(request, object_id, form_url, extra_context=extra_context)
    
    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)

        # ✅ safe access
        if "first_name" in form.base_fields:
            form.base_fields["first_name"].required = True

        if "last_name" in form.base_fields:
            form.base_fields["last_name"].required = True

        if "email" in form.base_fields:
            form.base_fields["email"].required = True

        return form

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<path:object_id>/archive-pdf/",
                self.admin_site.admin_view(self.download_archive_pdf),
                name="app_customuser_archive_pdf",
            ),
        ]
        return custom_urls + urls

    def archive_pdf_link(self, obj):
        url = reverse("admin:app_customuser_archive_pdf", args=[obj.pk])
        return format_html('<a class="button" href="{}">Download PDF</a>', url)

    archive_pdf_link.short_description = "Archive PDF"

    def download_archive_pdf(self, request, object_id):
        user = self.get_object(request, object_id)
        if user is None:
            return redirect("..")

        try:
            profile = user.profile
        except Profile.DoesNotExist:
            profile = None

        try:
            balance = user.leavebalance
        except LeaveBalance.DoesNotExist:
            balance = None

        from .views import build_employee_pdf_payload

        filename = f"user-archive-{user.username}.pdf"
        response = HttpResponse(
            build_employee_pdf_payload(user, profile, balance),
            content_type="application/pdf",
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "no-store"
        return response


    



class LeaveAdminForm(forms.ModelForm):
    created_at_override = forms.DateTimeField(
        required=False,
        help_text="Admin override only. Format: YYYY-MM-DD HH:MM:SS. Leave blank to keep the current created time.",
    )

    class Meta:
        model = Leave
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.created_at:
            self.fields["created_at_override"].initial = localtime(self.instance.created_at).strftime("%Y-%m-%d %H:%M:%S")

    def clean(self):
        cleaned_data = super().clean()
        self.instance._skip_model_validation = True
        return cleaned_data


@login_required
@never_cache
@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):
    form = LeaveAdminForm

    class Media:
        js = ("/static/admin/js/leave_toggle.js",)
    
    
    # ✅ LIST VIEW (clean + useful)
    list_display = ( 'id', 'user', 'leave_type',  'from_datetime', 'to_datetime', 'status', 'created_at', )

    list_filter = ( 'id', 'status', 'leave_type', 'from_date', 'created_at', )

    search_fields = ( 'id', 'user__username', 'reason', 'leave_type', 'from_date', 'status', )

    ordering = ( '-created_at', )

    # ✅ ALL FIELDS EDITABLE
    # (No readonly fields)

    # ✅ CLEAN FORM LAYOUT
    fieldsets = (

        ("👤 Employee Info", {
            'fields': ('user',)
        }),

        ("📅 Leave Details", {
            'fields': (
                'leave_type',
                ('from_date', 'from_datetime', 'to_date', 'to_datetime',),
                ('requested_from_date', 'requested_to_date',),
                'reason',
                'deducted_from',
            )
        }),

        ("⚙️ Status & Decision", {
            'fields': (
                'status',
                'rejection_reason',
                ('approved_at', 'rejected_at',),
                'updated_at',
                'no_of_times_updated',
            )
        }),

        ("🕒 Metadata", {
            'fields': ('created_at_display', 'created_at_override'),
            'classes': ('collapse',),   # 👈 collapsible (clean UI)
        }),
    )

    # ✅ OPTIONAL: make created_at auto (not editable)
    readonly_fields = ('created_at_display',)
    
    
    def created_at_display(self, obj):

        if obj and obj.created_at:
            ist_time = localtime(obj.created_at)  # ✅ converts to IST (if configured)
        else:
            ist_time = localtime(now())

        return ist_time.strftime("%d %b %Y, %I:%M %p")

    created_at_display.short_description = "Created At"
    

    def save_model(self, request, obj, form, change):
        if obj.leave_type in ["Short", "Half"] and obj.user_id and obj.from_date:
            count = Leave.objects.filter(
                user=obj.user,
                leave_type=obj.leave_type,
                from_date__month=obj.from_date.month,
                from_date__year=obj.from_date.year,
                status__in=["Pending", "Approved"],
            ).exclude(pk=obj.pk).count()
            limit = 2 if obj.leave_type == "Short" else 1

            if obj.status in ["Pending", "Approved"] and count >= limit:
                messages.warning(
                    request,
                    f"Admin override saved: {obj.leave_type} monthly limit is exceeded for this employee."
                )

        obj._skip_model_validation = True
        obj.save(skip_validation=True)
        created_at_override = form.cleaned_data.get("created_at_override")
        if created_at_override:
            Leave.objects.filter(pk=obj.pk).update(created_at=created_at_override)
            obj.created_at = created_at_override
        return








# 🔹 Register LeaveBalance
@login_required
@never_cache
@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    
    list_display = ("user", "total_leave_balance", "total_leave_remaining", "sick_total", "sick_used", "earned_total", "earned_used", "unpaid")
    
    




@login_required
@never_cache
class HolidayUploadForm(forms.Form):
    
    csv_file = forms.FileField(label="Upload CSV File",  help_text="CSV format: name,date,is_optional (YYYY-MM-DD)")






# upload csv file with preview 
@login_required
@never_cache
@admin.register(CompanyHoliday)
class CompanyHolidayAdmin(admin.ModelAdmin):

    list_display = ("name", "date", "is_optional")
    search_fields = ("name", "date")
    ordering = ("date", "name")
    date_hierarchy = "date"
    list_filter = ("is_optional", "name", "date")

    change_list_template = "admin/companyholiday_changelist.html"

    def get_urls(self):
        
        urls = super().get_urls()
        custom_urls = [path("upload-csv/", self.upload_csv, name="companyholiday_upload_csv"),]
        return custom_urls + urls

    def upload_csv(self, request):

        if request.method == "POST":
            form = HolidayUploadForm(request.POST, request.FILES)

            if form.is_valid():
                file = request.FILES["csv_file"]
                decoded_file = file.read().decode("utf-8").splitlines()
                reader = csv.DictReader(decoded_file)

                preview_data = []
                errors = []

                for i, row in enumerate(reader, start=1):

                    name = row.get("name")
                    date_str = row.get("date")
                    optional_str = row.get("is_optional", "False")

                    # Basic validation
                    if not name or not date_str:
                        errors.append(f"Row {i}: Missing name or date")
                        continue

                    try:
                        date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                        is_optional = optional_str.lower() == "true"

                        exists = CompanyHoliday.objects.filter(date=date_obj).exists()

                        preview_data.append({"name": name, "date": date_obj, "is_optional": is_optional, "exists": exists})

                    except ValueError:
                        errors.append(f"Row {i}: Invalid date format (use YYYY-MM-DD)")

                # If confirm button pressed
                if "confirm_upload" in request.POST:

                    created = 0
                    skipped = 0

                    for item in preview_data:
                        
                        obj, created_flag = CompanyHoliday.objects.get_or_create(
                            date=item["date"],
                            defaults={ "name": item["name"], "is_optional": item["is_optional"] }
                        )

                        if created_flag:
                            created += 1
                            
                        else:
                            skipped += 1

                    self.message_user(request, f"Upload completed. Created: {created}, Skipped: {skipped}", level=messages.SUCCESS)

                    return redirect("..")

                return render(request, "admin/holiday_preview.html", { "preview_data": preview_data, "errors": errors } )

        else:
            
            form = HolidayUploadForm()

        return render(request, "admin/holiday_upload.html", {"form": form})


@login_required
@never_cache
@admin.register(WorkFromHomeDay)
class WorkFromHomeDayAdmin(admin.ModelAdmin):
    list_display = ("weekday", "is_active", "updated_at")
    list_filter = ("is_active",)
    ordering = ("weekday",)
