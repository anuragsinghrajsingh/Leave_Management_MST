from django.contrib import admin, messages
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from .models import Leave, LeaveBalance, Profile, CustomUser
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from .models import CompanyHoliday
from django import forms
from django.shortcuts import render, redirect
from django.urls import path
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

    # readonly_fields = ("employee_id",)  # optional
    
    
    


# No use of it as of now it has been bypassed using other method

# class CustomUserAdminForm(forms.ModelForm):
#     profile_role = forms.CharField(label="Profile Role", required=False, disabled=True)

#     class Meta:
#         model = CustomUser
#         fields = "__all__"

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)

#         if self.instance.pk and hasattr(self.instance, "profile"):
#             self.fields["profile_role"].initial = self.instance.profile.role
#         else:
#             self.fields["profile_role"].initial = "-"




    
CustomUser = get_user_model()


# 🔹 Register CustomUser
# @admin.register(CustomUser)
# class CustomUserAdmin(UserAdmin):
    
#     fieldsets = UserAdmin.fieldsets + (("Role Information", {"fields": ("role",),}),)
#     list_display = ("username", "email", "role", "is_staff", "is_superuser")




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

    list_display = ("username", "email", "role", "is_staff", "is_superuser")
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






# 🔹 Register Leave
# @login_required
# @never_cache
# @admin.register(Leave)
# class LeaveAdmin(admin.ModelAdmin):

#     list_display = ('created_at', 'id', 'user', 'leave_type', 'from_date', 'to_date', 'reason', 'status', )

#     list_filter = ('id', 'user', 'status','leave_type', 'from_date', )

#     search_fields = ('id', 'user__username', 'leave_type',  'from_date', 'status', )

#     # Default ordering
#     ordering = ('-created_at',)


#     # readonly_fields = ('created_at', 'id', 'user', 'leave_type', 'from_date', 'to_date', 'reason', 'status',)
    
#     # Fields admin CANNOT edit
    
#     def get_readonly_fields(self, request, obj=None):
#         if obj:  # When editing existing leave
#             return ('user', 'leave_type', 'from_date', 'to_date', 'reason', 'created_at', )
#         return ()
    
    
#     # Page layout
#     fieldsets = (
#         ("Employee Info", {
#             'fields': ('user',)
#         }),

#         ("Leave Details (Read Only)", {
#             'fields': ('leave_type', 'from_date', 'to_date', 'reason')
#         }),

#         ("Admin Decision", {
#             'fields': ('status', 'rejection_reason')
#         }),

#         ("Metadata", {
#             'fields': ('created_at',)
#         }),
#     )
    
#     # This will block the the "add" button so that new leave cannot be added directly through admin panel
    
#     def has_add_permission(self, request):
#         return False





@login_required
@never_cache
@admin.register(Leave)
class LeaveAdmin(admin.ModelAdmin):

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
                'reason',
            )
        }),

        ("⚙️ Status & Decision", {
            'fields': (
                'status',
                'rejection_reason',
            )
        }),

        ("🕒 Metadata", {
            'fields': ('created_at_display',),
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

        current_month = now().month

        if obj.leave_type == "Short":
            count = Leave.objects.filter(
                user=obj.user,
                leave_type="Short",
                from_date__month=current_month
            ).count()

            if count >= 2:
                messages.warning(request, "⚠ More than 2 short leaves this month")

        if obj.leave_type == "Half":
            count = Leave.objects.filter(
                user=obj.user,
                leave_type="Half",
                from_date__month=current_month
            ).count()

            if count >= 1:
                messages.warning(request, "⚠ More than 1 half leave this month")

        super().save_model(request, obj, form, change)






# 🔹 Register LeaveBalance
@login_required
@never_cache
@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    
    list_display = ("user", "total_leave_balance", "total_leave_remaining", "sick_total", "sick_used", "earned_total", "earned_used", "unpaid")
    
    


# @admin.register(CompanyHoliday)
# class CompanyHolidayAdmin(admin.ModelAdmin):

#     list_display = ("name", "date", "is_optional")
#     search_fields = ("name", "date")
#     ordering = ("date", "name")
#     date_hierarchy = "date"
#     list_filter = ("is_optional", "name", "date",)

    

@login_required
@never_cache
class HolidayUploadForm(forms.Form):
    
    csv_file = forms.FileField(label="Upload CSV File",  help_text="CSV format: name,date,is_optional (YYYY-MM-DD)")



# upload csv file Without preview 
# @admin.register(CompanyHoliday)
# class CompanyHolidayAdmin(admin.ModelAdmin):

#     list_display = ("name", "date")
#     change_list_template = "admin/holiday_upload.html"

#     def get_urls(self):
#         urls = super().get_urls()
#         custom_urls = [
#             path("upload-csv/", self.upload_csv),
#         ]
#         return custom_urls + urls

#     def upload_csv(self, request):
#         if request.method == "POST":
#             form = HolidayUploadForm(request.POST, request.FILES)
#             if form.is_valid():
#                 file = request.FILES["csv_file"]
#                 decoded_file = file.read().decode("utf-8").splitlines()
#                 reader = csv.DictReader(decoded_file)

#                 for row in reader:
#                     CompanyHoliday.objects.get_or_create(
#                         date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
#                         defaults={"name": row["name"]}
#                     )

#                 self.message_user(request, "Holidays uploaded successfully")
#                 return redirect("..")
#         else:
#             form = HolidayUploadForm()

#         return render(request, "admin/upload_form.html", {"form": form})



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
    
    
# Bulk Operation Do it Later
# actions = ['approve_leaves', 'reject_leaves']

# def approve_leaves(self, request, queryset):
#     queryset.update(status='Approved')
# approve_leaves.short_description = "Approve selected leaves"

# def reject_leaves(self, request, queryset):
#     queryset.update(status='Rejected')
# reject_leaves.short_description = "Reject selected leaves"
