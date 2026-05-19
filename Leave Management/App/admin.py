from django.contrib import admin, messages
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from .models import (
    AdminAuditLog,
    AllCommunicationNotificationAudit,
    AnalyticsLogViewer,
    ApiLogViewer,
    AuthLogViewer,
    BackupLogViewer,
    BackupRestoreControl,
    CompanyHoliday,
    Communication,
    CommunicationRead,
    CommunicationSeen,
    DeleteAdminAudit,
    DjangoErrorLogViewer,
    EmployeeCommunication,
    EmployeeCommunicationAudit,
    EmployeeCommunicationRead,
    EmployeeCommunicationReadSeenAudit,
    EmployeeCommunicationSeen,
    EmployeeLeaveNotificationReadSeenAudit,
    EmployeeLeaveNotificationRead,
    EmployeeLeaveNotificationSeen,
    EmailLogViewer,
    HolidayAdminAudit,
    HRCommunication,
    HRCommunicationAudit,
    HRCommunicationRead,
    HRCommunicationReadSeenAudit,
    HRCommunicationSeen,
    HRLeaveNotificationReadSeenAudit,
    HRLeaveNotificationRead,
    HRLeaveNotificationSeen,
    LeaveLogViewer,
    MaintenanceLogViewer,
    Leave,
    LeaveAdminAudit,
    LeaveBalance,
    LeaveBalanceAdminAudit,
    LeaveBalanceAudit,
    LeaveNotificationRead,
    LeaveNotificationSeen,
    LogViewer,
    MaintenanceModeControl,
    MasterLogViewer,
    Profile,
    ProfileAdminAudit,
    ProfileLogViewer,
    SchedulerLogViewer,
    SecurityLogViewer,
    ServiceActionControl,
    ServiceLogViewer,
    CustomUser,
    UserAdminAudit,
    WorkFromHomeAdminAudit,
    WorkFromHomeDay,
    YearEndCarryForwardRun,
)
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.forms import UserChangeForm
from django.contrib.auth import get_user_model
from django import forms
from django.conf import settings
from django.db.models import Q
from django.shortcuts import render, redirect
from django.urls import path, reverse
from django.http import HttpResponse
from django.utils.html import format_html
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from datetime import date, datetime
from io import BytesIO
import csv
import logging
import os
import re
import zipfile
from django.utils.timezone import now, localtime
from App.services.maintenance_mode import (
    disable_maintenance_mode,
    enable_maintenance_mode,
    is_maintenance_mode_enabled,
)


maintenance_logger = logging.getLogger("lms_maintenance")
service_admin_logger = logging.getLogger("lms_service_startup_checks")






ADMIN_PROFILE_PHOTO_MAX_UPLOAD_BYTES = 3 * 1024 * 1024
ADMIN_PROFILE_PHOTO_MAX_PIXELS = 16_000_000
ADMIN_PROFILE_PHOTO_MAX_SIDE = 2048
ADMIN_LOG_VIEW_MAX_LINES = 500
ADMIN_LOG_VIEW_DEFAULT_LINES = 200
ADMIN_LOG_SEARCH_MAX_RESULTS = 500
ADMIN_LOG_SEARCH_DEFAULT_RESULTS = 200
ADMIN_LOG_LEVELS = {"INFO", "WARNING", "ERROR", "CRITICAL", "DEBUG"}

LOG_VIEWER_FILES = {
    "all": [
        ("Master", "master/system_master.log"),
        ("Security", "security/unauthorized.log"),
        ("Django errors", "django_errors.log"),
        ("Backup", "backups/activity.log"),
        ("Maintenance", "maintenance/activity.log"),
        ("Scheduler", "scheduler/tasks.log"),
        ("Service backups", "services/backups.log"),
        ("Service restore DB", "services/restore_db.log"),
        ("Service maintenance mode", "services/maintenance_mode.log"),
        ("Service startup checks", "services/startup_checks.log"),
        ("Service year-end", "services/year_end.log"),
        ("Service weekly report", "services/weekly_report.log"),
        ("Service PDF generator", "services/pdf_generator.log"),
        ("Service uptime tracker", "services/uptime_tracker.log"),
        ("Service scheduler", "services/scheduler.log"),
        ("API", "api/requests.log"),
        ("Email employee", "email/employee.log"),
        ("Email HR", "email/hr.log"),
        ("Email admin", "email/admin.log"),
        ("Email system", "email/system.log"),
        ("Auth employee", "auth/employee.log"),
        ("Auth HR", "auth/hr.log"),
        ("Auth admin", "auth/admin.log"),
        ("Leave employee", "leave/employee.log"),
        ("Leave HR", "leave/hr.log"),
        ("Leave admin", "leave/admin.log"),
        ("Profile", "profile/updates.log"),
        ("Analytics", "analytics/navigation.log"),
    ],
    "security": [("Security", "security/unauthorized.log")],
    "auth": [
        ("Employee auth", "auth/employee.log"),
        ("HR auth", "auth/hr.log"),
        ("Admin auth", "auth/admin.log"),
    ],
    "leave": [
        ("Employee leave", "leave/employee.log"),
        ("HR leave", "leave/hr.log"),
        ("Admin leave", "leave/admin.log"),
    ],
    "email": [
        ("Employee email", "email/employee.log"),
        ("HR email", "email/hr.log"),
        ("Admin email", "email/admin.log"),
        ("System email", "email/system.log"),
    ],
    "backup": [("Backup", "backups/activity.log")],
    "maintenance": [("Maintenance", "maintenance/activity.log")],
    "scheduler": [("Scheduler", "scheduler/tasks.log")],
    "services": [
        ("Backups", "services/backups.log"),
        ("Restore DB", "services/restore_db.log"),
        ("Maintenance mode", "services/maintenance_mode.log"),
        ("Startup checks", "services/startup_checks.log"),
        ("Year-end", "services/year_end.log"),
        ("Weekly report", "services/weekly_report.log"),
        ("PDF generator", "services/pdf_generator.log"),
        ("Uptime tracker", "services/uptime_tracker.log"),
        ("Scheduler", "services/scheduler.log"),
    ],
    "api": [("API", "api/requests.log")],
    "profile": [("Profile", "profile/updates.log")],
    "analytics": [("Analytics", "analytics/navigation.log")],
    "master": [("Master", "master/system_master.log")],
    "django_errors": [("Django errors", "django_errors.log")],
}


def _tail_log_file(path, lines):
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8", errors="replace") as log_file:
        return log_file.readlines()[-lines:]


def _iter_log_files(base_path):
    candidates = [base_path]
    candidates.extend(
        sorted(
            base_path.parent.glob(f"{base_path.name}.*"),
            key=lambda candidate: candidate.stat().st_mtime if candidate.exists() else 0,
            reverse=True,
        )
    )
    return candidates


def _line_matches_log_filters(line, query, level):
    if query and query.lower() not in line.lower():
        return False
    if level and f"[{level}]" not in line:
        return False
    return True


def _search_log_files(path, query, level, max_results):
    results = []
    if not path.exists():
        return results

    for log_path in _iter_log_files(path):
        if len(results) >= max_results:
            break
        if not log_path.exists() or not log_path.is_file():
            continue

        with log_path.open("r", encoding="utf-8", errors="replace") as log_file:
            for line_number, line in enumerate(log_file, start=1):
                if _line_matches_log_filters(line, query, level):
                    results.append(f"{log_path.name}:{line_number}: {line}")
                    if len(results) >= max_results:
                        break

    return results


def _safe_log_file_entry(label, relative_path, lines, query="", level="", max_results=ADMIN_LOG_SEARCH_DEFAULT_RESULTS):
    log_base_dir = settings.LOG_BASE_DIR.resolve()
    log_path = (log_base_dir / relative_path).resolve()
    if log_base_dir not in log_path.parents and log_path != log_base_dir:
        return {
            "label": label,
            "path": relative_path,
            "exists": False,
            "lines": ["Blocked unsafe log path."],
            "searching": bool(query or level),
        }

    searching = bool(query or level)
    return {
        "label": label,
        "path": str(log_path),
        "exists": log_path.exists(),
        "lines": _search_log_files(log_path, query, level, max_results) if searching else _tail_log_file(log_path, lines),
        "searching": searching,
    }


def _get_backup_restore_files(query=""):
    backup_dir = settings.BASE_DIR / "backups"
    if not backup_dir.exists():
        return []

    backups = []
    for backup in sorted(backup_dir.glob("backup_*.zip"), key=lambda path: path.stat().st_mtime, reverse=True):
        if query and query.lower() not in backup.name.lower():
            continue
        backups.append({
            "name": backup.name,
            "size_kb": round(backup.stat().st_size / 1024, 2),
            "modified_at": datetime.fromtimestamp(backup.stat().st_mtime),
        })
    return backups


def _get_safe_backup_path(filename):
    backup_dir = (settings.BASE_DIR / "backups").resolve()
    backup_path = (backup_dir / filename).resolve()
    if backup_dir not in backup_path.parents or backup_path.suffix.lower() != ".zip" or not backup_path.name.startswith("backup_"):
        return None
    if not backup_path.exists() or not backup_path.is_file():
        return None
    return backup_path


def _get_latest_file_info(directory, pattern):
    if not directory.exists():
        return None
    files = sorted(directory.glob(pattern), key=lambda path: path.stat().st_mtime, reverse=True)
    if not files:
        return None
    latest = files[0]
    return {
        "name": latest.name,
        "path": latest,
        "size_kb": round(latest.stat().st_size / 1024, 2),
        "modified_at": datetime.fromtimestamp(latest.stat().st_mtime),
    }


def _save_admin_weekly_report_pdf():
    from App.services.weekly_report_service import generate_weekly_hr_report_pdf_bytes

    output_dir = settings.BASE_DIR / "generated_pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"weekly_hr_report_admin_{now().strftime('%Y%m%d_%H%M%S')}.pdf"
    pdf_bytes = generate_weekly_hr_report_pdf_bytes()
    output_path.write_bytes(pdf_bytes)
    return output_path


def _sanitize_admin_profile_photo_upload(photo):
    from PIL import Image, ImageOps

    if photo.size > ADMIN_PROFILE_PHOTO_MAX_UPLOAD_BYTES:
        raise forms.ValidationError("Image must be under 3MB.")

    try:
        photo.seek(0)
        with Image.open(photo) as image:
            source_format = image.format
            if source_format not in {"JPEG", "PNG", "WEBP"}:
                raise forms.ValidationError("Only JPG, PNG or WEBP images allowed.")

            width, height = image.size
            if width <= 0 or height <= 0 or width * height > ADMIN_PROFILE_PHOTO_MAX_PIXELS:
                raise forms.ValidationError("Image dimensions are too large.")

            image.verify()

        photo.seek(0)
        with Image.open(photo) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail(
                (ADMIN_PROFILE_PHOTO_MAX_SIDE, ADMIN_PROFILE_PHOTO_MAX_SIDE),
                Image.Resampling.LANCZOS,
            )

            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )

            output = BytesIO()
            if has_alpha:
                sanitized = image.convert("RGBA")
                sanitized.save(output, format="PNG", optimize=True)
                extension = "png"
            else:
                sanitized = image.convert("RGB")
                sanitized.save(output, format="JPEG", quality=90, optimize=True)
                extension = "jpg"

    except forms.ValidationError:
        raise
    except Exception:
        raise forms.ValidationError("Invalid image file.")

    output.seek(0)
    filename_root = os.path.splitext(os.path.basename(photo.name or "profile-photo"))[0]
    filename_root = re.sub(r"[^A-Za-z0-9._()-]+", "_", filename_root).strip("._")
    return ContentFile(output.read(), name=f"{filename_root or 'profile-photo'}.{extension}")


def _audit_value(value):
    if hasattr(value, "pk"):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _collect_model_changes(previous, obj, field_names):
    changes = {}
    for field_name in field_names:
        old_value = getattr(previous, field_name)
        new_value = getattr(obj, field_name)
        if old_value != new_value:
            changes[field_name] = {
                "old": _audit_value(old_value),
                "new": _audit_value(new_value),
            }
    return changes


def _create_admin_audit_log(request, obj, changes, reason, action="CHANGE"):
    if not changes and action == "CHANGE":
        return
    AdminAuditLog.objects.create(
        model_label=obj._meta.label,
        object_id=str(obj.pk),
        object_repr=str(obj),
        action=action,
        updated_by=request.user,
        reason=(reason or "").strip(),
        changes=changes,
    )


def _snapshot_model_fields(obj, excluded_fields=None):
    excluded_fields = excluded_fields or {"id"}
    return {
        field.name: _audit_value(getattr(obj, field.name))
        for field in obj._meta.fields
        if field.name not in excluded_fields
    }


def admin_reason_field():
    return forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required when you change this record.",
    )


class AdminReasonFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        changed_fields = [field for field in self.changed_data if field != "change_reason"]
        if self.instance.pk and changed_fields and not (cleaned_data.get("change_reason") or "").strip():
            self.add_error("change_reason", "Please provide a reason for this admin change.")
        return cleaned_data


class ProfileInlineForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

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

    def clean_profile_photo(self):
        photo = self.cleaned_data.get("profile_photo")
        if not photo or "profile_photo" not in self.changed_data:
            return photo
        return _sanitize_admin_profile_photo_upload(photo)






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
        "change_reason",
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


class DeleteAuditedAdminMixin:
    audit_excluded_fields = {"id"}
    delete_confirmation_template = "admin/audited_delete_confirmation.html"
    delete_selected_confirmation_template = "admin/audited_delete_selected_confirmation.html"

    def _get_delete_reason(self, request, bulk=False):
        reason = (request.POST.get("delete_reason") or "").strip()
        if not reason:
            action_label = "bulk delete" if bulk else "delete"
            self.message_user(request, f"Delete reason is required before {action_label}.", level=messages.ERROR)
            return ""
        return reason

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST" and request.POST.get("post") == "yes" and not (request.POST.get("delete_reason") or "").strip():
            self.message_user(request, "Delete reason is required before delete.", level=messages.ERROR)
            return redirect(request.path)
        return super().delete_view(request, object_id, extra_context=extra_context)

    def delete_model(self, request, obj):
        reason = self._get_delete_reason(request)
        if not reason:
            return
        _create_admin_audit_log(
            request,
            obj,
            {"deleted_record": {"old": _snapshot_model_fields(obj, self.audit_excluded_fields), "new": None}},
            reason,
            action="DELETE",
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        reason = self._get_delete_reason(request, bulk=True)
        if not reason:
            return
        objects_to_log = list(queryset)
        for obj in objects_to_log:
            _create_admin_audit_log(
                request,
                obj,
                {"deleted_record": {"old": _snapshot_model_fields(obj, self.audit_excluded_fields), "new": None}},
                reason,
                action="DELETE",
            )
        super().delete_queryset(request, queryset)

    def _log_create(self, request, obj, reason):
        _create_admin_audit_log(
            request,
            obj,
            {"created_record": {"old": None, "new": _snapshot_model_fields(obj, self.audit_excluded_fields)}},
            reason,
            action="CREATE",
        )
    
    


    
CustomUser = get_user_model()


class CustomUserAdminForm(AdminReasonFormMixin, UserChangeForm):
    change_reason = admin_reason_field()

    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = "__all__"

# 🔹 Register CustomUser
@login_required
@never_cache
@admin.register(CustomUser)
class CustomUserAdmin(DeleteAuditedAdminMixin, UserAdmin):
    form = CustomUserAdminForm

    inlines = [ProfileInline]
    actions = ["export_selected_archive_pdfs"]

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
        ("Audit reason", {
            "fields": ("change_reason",),
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

        if request.method != "POST" or "confirm_download" not in request.POST:
            context = {
                **self.admin_site.each_context(request),
                "title": "Confirm employee archive download",
                "opts": self.model._meta,
                "target_user": user,
            }
            return TemplateResponse(request, "admin/archive_download_confirm.html", context)

        download_reason = (request.POST.get("download_reason") or "").strip()
        if not download_reason:
            self.message_user(request, "Audit reason is required before downloading employee archive PDF.", level=messages.ERROR)
            return redirect(request.path)

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
        _create_admin_audit_log(
            request,
            user,
            {"archive_pdf": {"old": None, "new": "downloaded"}},
            download_reason,
            action="DOWNLOAD",
        )
        return response

    @admin.action(description="Export selected employee archive PDFs")
    def export_selected_archive_pdfs(self, request, queryset):
        from .views import build_employee_pdf_payload

        selected_ids = list(queryset.values_list("pk", flat=True))
        if not selected_ids:
            self.message_user(request, "No users selected for archive export.", level=messages.WARNING)
            return None

        if "confirm_export" not in request.POST:
            context = {
                **self.admin_site.each_context(request),
                "title": "Confirm employee archive export",
                "opts": self.model._meta,
                "users": queryset.order_by("username", "id"),
                "selected_ids": selected_ids,
                "action_name": "export_selected_archive_pdfs",
            }
            return TemplateResponse(request, "admin/archive_export_confirm.html", context)

        export_reason = (request.POST.get("export_reason") or "").strip()
        if not export_reason:
            self.message_user(request, "Audit reason is required before exporting employee archives.", level=messages.ERROR)
            return None

        output = BytesIO()
        exported_count = 0

        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
            for user in queryset.order_by("username", "id"):
                try:
                    profile = user.profile
                except Profile.DoesNotExist:
                    profile = None

                try:
                    balance = user.leavebalance
                except LeaveBalance.DoesNotExist:
                    balance = None

                safe_username = re.sub(r"[^A-Za-z0-9._-]+", "_", user.username).strip("._")
                filename = f"user-archive-{safe_username or user.pk}.pdf"
                archive.writestr(filename, build_employee_pdf_payload(user, profile, balance))
                exported_count += 1

                _create_admin_audit_log(
                    request,
                    user,
                    {"archive_pdf": {"old": None, "new": "batch_exported"}},
                    export_reason,
                    action="DOWNLOAD",
                )

        output.seek(0)
        timestamp = localtime(now()).strftime("%Y%m%d-%H%M%S")
        response = HttpResponse(output.read(), content_type="application/zip")
        response["Content-Disposition"] = f'attachment; filename="employee-archives-{timestamp}.zip"'
        response["X-Content-Type-Options"] = "nosniff"
        response["Cache-Control"] = "no-store"
        self.message_user(request, f"Exported {exported_count} employee archive PDF(s).", level=messages.SUCCESS)
        return response

    def save_model(self, request, obj, form, change):
        previous = CustomUser.objects.get(pk=obj.pk) if change and obj.pk else None
        super().save_model(request, obj, form, change)
        if previous:
            field_names = [field.name for field in obj._meta.fields if field.name not in {"password", "last_login", "date_joined"}]
            _create_admin_audit_log(
                request,
                obj,
                _collect_model_changes(previous, obj, field_names),
                form.cleaned_data.get("change_reason"),
            )
        elif obj.pk:
            self._log_create(request, obj, "Created from Django admin.")

    def save_formset(self, request, form, formset, change):
        tracked_profiles = {
            inline_form.instance.pk: Profile.objects.get(pk=inline_form.instance.pk)
            for inline_form in formset.forms
            if isinstance(inline_form.instance, Profile) and inline_form.instance.pk
        }
        super().save_formset(request, form, formset, change)
        for inline_form in formset.forms:
            profile = inline_form.instance
            previous = tracked_profiles.get(profile.pk)
            if not previous:
                continue
            field_names = [field.name for field in profile._meta.fields if field.name not in {"id", "user"}]
            _create_admin_audit_log(
                request,
                profile,
                _collect_model_changes(previous, profile, field_names),
                inline_form.cleaned_data.get("change_reason"),
            )


    



class LeaveAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

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
LEAVE_BALANCE_AUDIT_FIELDS = (
    "total_leave_balance",
    "total_leave_remaining",
    "sick_total",
    "sick_used",
    "earned_total",
    "earned_used",
    "unpaid",
    "last_year_end_processed",
)


class LeaveBalanceAdminForm(forms.ModelForm):
    change_reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required when you change any balance value.",
    )

    class Meta:
        model = LeaveBalance
        fields = "__all__"

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk:
            changed_balance_fields = [
                field_name
                for field_name in LEAVE_BALANCE_AUDIT_FIELDS
                if field_name in self.changed_data
            ]
            if changed_balance_fields and not (cleaned_data.get("change_reason") or "").strip():
                self.add_error("change_reason", "Please provide a reason for changing leave balance values.")
        return cleaned_data


class LeaveBalanceAuditInline(admin.TabularInline):
    model = LeaveBalanceAudit
    extra = 0
    can_delete = False
    fields = ("changed_at", "updated_by", "reason", "changes")
    readonly_fields = fields
    ordering = ("-changed_at",)

    def has_add_permission(self, request, obj=None):
        return False


@login_required
@never_cache
@admin.register(Leave)
class LeaveAdmin(DeleteAuditedAdminMixin, admin.ModelAdmin):
    form = LeaveAdminForm

    class Media:
        js = ("/static/admin/js/leave_toggle.js",)
    
    
    # ✅ LIST VIEW (clean + useful)
    list_display = ( 'id', 'user', 'leave_type',  'from_datetime', 'to_datetime', 'status', 'reviewed_by', 'created_at', )

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
                'reviewed_by',
                ('approved_at', 'rejected_at',),
                'updated_at',
                'no_of_times_updated',
            )
        }),

        ("🕒 Metadata", {
            'fields': ('created_at_display', 'created_at_override'),
            'classes': ('collapse',),   # 👈 collapsible (clean UI)
        }),
        ("Audit reason", {
            'fields': ('change_reason',),
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
        previous = Leave.objects.get(pk=obj.pk) if change and obj.pk else None
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
        if previous:
            field_names = [field.name for field in obj._meta.fields if field.name != "id"]
            _create_admin_audit_log(
                request,
                obj,
                _collect_model_changes(previous, obj, field_names),
                form.cleaned_data.get("change_reason"),
            )
        elif obj.pk:
            self._log_create(request, obj, form.cleaned_data.get("change_reason") or "Created from Django admin.")
        return








# 🔹 Register LeaveBalance
@login_required
@never_cache
@admin.register(LeaveBalance)
class LeaveBalanceAdmin(DeleteAuditedAdminMixin, admin.ModelAdmin):
    form = LeaveBalanceAdminForm
    inlines = [LeaveBalanceAuditInline]
    list_display = ("user", "total_leave_balance", "total_leave_remaining", "sick_total", "sick_used", "earned_total", "earned_used", "unpaid")
    fieldsets = (
        ("Employee", {"fields": ("user",)}),
        ("Balance", {
            "fields": (
                "total_leave_balance",
                "total_leave_remaining",
                ("sick_total", "sick_used"),
                ("earned_total", "earned_used"),
                "unpaid",
                "last_year_end_processed",
            )
        }),
        ("Audit reason", {"fields": ("change_reason",)}),
    )

    def save_model(self, request, obj, form, change):
        old_values = {}
        if change and obj.pk:
            previous = LeaveBalance.objects.get(pk=obj.pk)
            old_values = {
                field_name: getattr(previous, field_name)
                for field_name in LEAVE_BALANCE_AUDIT_FIELDS
            }

        super().save_model(request, obj, form, change)

        if not change:
            return

        changes = {}
        for field_name in LEAVE_BALANCE_AUDIT_FIELDS:
            old_value = old_values.get(field_name)
            new_value = getattr(obj, field_name)
            if old_value != new_value:
                changes[field_name] = {"old": old_value, "new": new_value}

        if changes:
            LeaveBalanceAudit.objects.create(
                balance=obj,
                employee=obj.user,
                updated_by=request.user,
                reason=(form.cleaned_data.get("change_reason") or "").strip(),
                changes=changes,
            )
        elif not change and obj.pk:
            self._log_create(request, obj, form.cleaned_data.get("change_reason") or "Created from Django admin.")


class ReadOnlyAuditAdminMixin:
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@login_required
@never_cache
@admin.register(LeaveBalanceAdminAudit)
class LeaveBalanceAuditAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    list_display = ("employee", "updated_by", "changed_at", "change_summary", "reason")
    list_filter = ("changed_at", "updated_by")
    search_fields = ("employee__username", "updated_by__username", "reason")
    readonly_fields = ("balance", "employee", "updated_by", "changed_at", "reason", "changes")

    @admin.display(description="Summary")
    def change_summary(self, obj):
        return ", ".join(obj.changes.keys()) if obj.changes else "-"
    




@login_required
@never_cache
class HolidayUploadForm(forms.Form):
    
    csv_file = forms.FileField(label="Upload CSV File",  help_text="CSV format: name,date,is_optional (YYYY-MM-DD)")
    change_reason = forms.CharField(
        label="Audit reason",
        widget=forms.Textarea(attrs={"rows": 3}),
        help_text="Required. This reason is stored for every holiday created from the CSV upload.",
    )


class CompanyHolidayAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = CompanyHoliday
        fields = "__all__"


class WorkFromHomeDayAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = WorkFromHomeDay
        fields = "__all__"


class YearEndCarryForwardRunAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = YearEndCarryForwardRun
        fields = "__all__"


class CommunicationAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = Communication
        fields = "__all__"


class CommunicationReadAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = CommunicationRead
        fields = "__all__"


class CommunicationSeenAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = CommunicationSeen
        fields = "__all__"


class LeaveNotificationReadAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = LeaveNotificationRead
        fields = "__all__"


class LeaveNotificationSeenAdminForm(AdminReasonFormMixin, forms.ModelForm):
    change_reason = admin_reason_field()

    class Meta:
        model = LeaveNotificationSeen
        fields = "__all__"


class AuditedAdminModelMixin:
    audit_excluded_fields = {"id"}
    delete_confirmation_template = "admin/audited_delete_confirmation.html"
    delete_selected_confirmation_template = "admin/audited_delete_selected_confirmation.html"

    def save_model(self, request, obj, form, change):
        previous = obj.__class__.objects.get(pk=obj.pk) if change and obj.pk else None
        super().save_model(request, obj, form, change)
        if previous:
            field_names = [
                field.name
                for field in obj._meta.fields
                if field.name not in self.audit_excluded_fields
            ]
            _create_admin_audit_log(
                request,
                obj,
                _collect_model_changes(previous, obj, field_names),
                form.cleaned_data.get("change_reason"),
            )
        elif obj.pk:
            _create_admin_audit_log(
                request,
                obj,
                {"created_record": {"old": None, "new": _snapshot_model_fields(obj, self.audit_excluded_fields)}},
                form.cleaned_data.get("change_reason") or "Created from Django admin.",
                action="CREATE",
            )

    def _get_delete_reason(self, request, bulk=False):
        reason = (request.POST.get("delete_reason") or "").strip()
        if not reason:
            action_label = "bulk delete" if bulk else "delete"
            self.message_user(request, f"Delete reason is required before {action_label}.", level=messages.ERROR)
            return ""
        return reason

    def delete_view(self, request, object_id, extra_context=None):
        if request.method == "POST" and request.POST.get("post") == "yes" and not (request.POST.get("delete_reason") or "").strip():
            self.message_user(request, "Delete reason is required before delete.", level=messages.ERROR)
            return redirect(request.path)
        return super().delete_view(request, object_id, extra_context=extra_context)

    def delete_model(self, request, obj):
        reason = self._get_delete_reason(request)
        if not reason:
            return
        _create_admin_audit_log(
            request,
            obj,
            {"deleted_record": {"old": _snapshot_model_fields(obj, self.audit_excluded_fields), "new": None}},
            reason,
            action="DELETE",
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        reason = self._get_delete_reason(request, bulk=True)
        if not reason:
            return
        objects_to_log = list(queryset)
        for obj in objects_to_log:
            _create_admin_audit_log(
                request,
                obj,
                {"deleted_record": {"old": _snapshot_model_fields(obj, self.audit_excluded_fields), "new": None}},
                reason,
                action="DELETE",
            )
        super().delete_queryset(request, queryset)


@login_required
@never_cache
@admin.register(YearEndCarryForwardRun)
class YearEndCarryForwardRunAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = YearEndCarryForwardRunAdminForm
    audit_excluded_fields = {"id"}
    list_display = ("year", "completed_at")
    list_filter = ("completed_at",)
    search_fields = ("year",)
    ordering = ("-year",)
    fields = ("year", "completed_at", "change_reason")
    actions = ["run_selected_year_end_carry_forward"]

    @admin.action(description="Run selected year-end carry forward")
    def run_selected_year_end_carry_forward(self, request, queryset):
        from App.services.year_end_service import run_year_end_carry_forward_if_due

        selected_ids = list(queryset.values_list("pk", flat=True))
        if not selected_ids:
            self.message_user(request, "No year-end records selected.", level=messages.WARNING)
            return None

        if "confirm_run" not in request.POST:
            context = {
                **self.admin_site.each_context(request),
                "title": "Confirm year-end carry forward",
                "opts": self.model._meta,
                "records": queryset.order_by("year"),
                "selected_ids": selected_ids,
                "action_name": "run_selected_year_end_carry_forward",
            }
            return TemplateResponse(request, "admin/year_end_carry_forward_confirm.html", context)

        action_reason = (request.POST.get("action_reason") or "").strip()
        if not action_reason:
            self.message_user(request, "Audit reason is required before running year-end carry forward.", level=messages.ERROR)
            return None

        processed_years = []
        skipped_years = []

        for run_record in queryset.order_by("year"):
            if run_record.completed_at:
                skipped_years.append(str(run_record.year))
                continue

            did_run = run_year_end_carry_forward_if_due(today=date(run_record.year, 1, 1))
            refreshed_record = YearEndCarryForwardRun.objects.get(pk=run_record.pk)

            if did_run:
                processed_years.append(str(run_record.year))
                _create_admin_audit_log(
                    request,
                    refreshed_record,
                    {"year_end_carry_forward": {"old": "pending", "new": "completed"}},
                    action_reason,
                    action="RUN",
                )
            else:
                skipped_years.append(str(run_record.year))

        if processed_years:
            self.message_user(
                request,
                f"Year-end carry forward completed for: {', '.join(processed_years)}.",
                level=messages.SUCCESS,
            )

        if skipped_years:
            self.message_user(
                request,
                f"Skipped already completed or unavailable year(s): {', '.join(skipped_years)}.",
                level=messages.WARNING,
            )

        return None


@login_required
@never_cache
@admin.register(Communication)
class CommunicationAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = CommunicationAdminForm
    audit_excluded_fields = {"id", "created_at"}
    list_display = ("id", "message_type", "title", "sender", "recipient", "audience_role", "created_at")
    list_filter = ("message_type", "audience_role", "created_at")
    search_fields = ("title", "body", "sender__username", "recipient__username")
    readonly_fields = ("created_at",)
    fields = (
        "sender",
        "recipient",
        "message_type",
        "audience_role",
        "title",
        "body",
        "created_at",
        "change_reason",
    )


class RoleCommunicationAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = CommunicationAdminForm
    audit_excluded_fields = {"id", "created_at"}
    list_display = ("id", "message_type", "title", "sender", "recipient", "audience_role", "created_at")
    list_filter = ("message_type", "audience_role", "created_at")
    search_fields = ("title", "body", "sender__username", "recipient__username")
    readonly_fields = ("created_at",)
    fields = (
        "sender",
        "recipient",
        "message_type",
        "audience_role",
        "title",
        "body",
        "created_at",
        "change_reason",
    )


class EmployeeCommunicationAdmin(RoleCommunicationAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(sender__role="EMPLOYEE")
            | Q(recipient__role="EMPLOYEE")
            | Q(message_type="ANNOUNCEMENT", audience_role="EMPLOYEE")
        ).distinct()


class HRCommunicationAdmin(RoleCommunicationAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(sender__role="HR")
            | Q(recipient__role="HR")
            | Q(audience_role="HR")
        ).distinct()


@login_required
@never_cache
@admin.register(EmployeeCommunication)
class EmployeeCommunicationProxyAdmin(EmployeeCommunicationAdmin):
    pass


@login_required
@never_cache
@admin.register(HRCommunication)
class HRCommunicationProxyAdmin(HRCommunicationAdmin):
    pass


@login_required
@never_cache
@admin.register(CommunicationRead)
class CommunicationReadAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = CommunicationReadAdminForm
    audit_excluded_fields = {"id", "read_at"}
    list_display = ("user", "communication", "read_at")
    list_filter = ("read_at",)
    search_fields = ("user__username", "communication__title", "communication__body")
    readonly_fields = ("read_at",)
    fields = ("user", "communication", "read_at", "change_reason")


class RoleCommunicationReadAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = CommunicationReadAdminForm
    audit_excluded_fields = {"id", "read_at"}
    list_display = ("user", "communication", "read_at")
    list_filter = ("read_at",)
    search_fields = ("user__username", "communication__title", "communication__body")
    readonly_fields = ("read_at",)
    fields = ("user", "communication", "read_at", "change_reason")


class EmployeeCommunicationReadAdmin(RoleCommunicationReadAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="EMPLOYEE")


class HRCommunicationReadAdmin(RoleCommunicationReadAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="HR")


@login_required
@never_cache
@admin.register(EmployeeCommunicationRead)
class EmployeeCommunicationReadProxyAdmin(EmployeeCommunicationReadAdmin):
    pass


@login_required
@never_cache
@admin.register(HRCommunicationRead)
class HRCommunicationReadProxyAdmin(HRCommunicationReadAdmin):
    pass


@login_required
@never_cache
@admin.register(CommunicationSeen)
class CommunicationSeenAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = CommunicationSeenAdminForm
    audit_excluded_fields = {"id", "seen_at"}
    list_display = ("user", "communication", "seen_at")
    list_filter = ("seen_at",)
    search_fields = ("user__username", "communication__title", "communication__body")
    readonly_fields = ("seen_at",)
    fields = ("user", "communication", "seen_at", "change_reason")


class RoleCommunicationSeenAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = CommunicationSeenAdminForm
    audit_excluded_fields = {"id", "seen_at"}
    list_display = ("user", "communication", "seen_at")
    list_filter = ("seen_at",)
    search_fields = ("user__username", "communication__title", "communication__body")
    readonly_fields = ("seen_at",)
    fields = ("user", "communication", "seen_at", "change_reason")


class EmployeeCommunicationSeenAdmin(RoleCommunicationSeenAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="EMPLOYEE")


class HRCommunicationSeenAdmin(RoleCommunicationSeenAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="HR")


@login_required
@never_cache
@admin.register(EmployeeCommunicationSeen)
class EmployeeCommunicationSeenProxyAdmin(EmployeeCommunicationSeenAdmin):
    pass


@login_required
@never_cache
@admin.register(HRCommunicationSeen)
class HRCommunicationSeenProxyAdmin(HRCommunicationSeenAdmin):
    pass


@login_required
@never_cache
@admin.register(LeaveNotificationRead)
class LeaveNotificationReadAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = LeaveNotificationReadAdminForm
    audit_excluded_fields = {"id", "read_at"}
    list_display = ("user", "leave", "read_at")
    list_filter = ("read_at",)
    search_fields = ("user__username", "leave__user__username", "leave__leave_type", "leave__status")
    readonly_fields = ("read_at",)
    fields = ("user", "leave", "read_at", "change_reason")


class RoleLeaveNotificationReadAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = LeaveNotificationReadAdminForm
    audit_excluded_fields = {"id", "read_at"}
    list_display = ("user", "leave", "read_at")
    list_filter = ("read_at",)
    search_fields = ("user__username", "leave__user__username", "leave__leave_type", "leave__status")
    readonly_fields = ("read_at",)
    fields = ("user", "leave", "read_at", "change_reason")


class EmployeeLeaveNotificationReadAdmin(RoleLeaveNotificationReadAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="EMPLOYEE")


class HRLeaveNotificationReadAdmin(RoleLeaveNotificationReadAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="HR")


@login_required
@never_cache
@admin.register(EmployeeLeaveNotificationRead)
class EmployeeLeaveNotificationReadProxyAdmin(EmployeeLeaveNotificationReadAdmin):
    pass


@login_required
@never_cache
@admin.register(HRLeaveNotificationRead)
class HRLeaveNotificationReadProxyAdmin(HRLeaveNotificationReadAdmin):
    pass


@login_required
@never_cache
@admin.register(LeaveNotificationSeen)
class LeaveNotificationSeenAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = LeaveNotificationSeenAdminForm
    audit_excluded_fields = {"id", "seen_at"}
    list_display = ("user", "leave", "seen_at")
    list_filter = ("seen_at",)
    search_fields = ("user__username", "leave__user__username", "leave__leave_type", "leave__status")
    readonly_fields = ("seen_at",)
    fields = ("user", "leave", "seen_at", "change_reason")


class RoleLeaveNotificationSeenAdmin(AuditedAdminModelMixin, admin.ModelAdmin):
    form = LeaveNotificationSeenAdminForm
    audit_excluded_fields = {"id", "seen_at"}
    list_display = ("user", "leave", "seen_at")
    list_filter = ("seen_at",)
    search_fields = ("user__username", "leave__user__username", "leave__leave_type", "leave__status")
    readonly_fields = ("seen_at",)
    fields = ("user", "leave", "seen_at", "change_reason")


class EmployeeLeaveNotificationSeenAdmin(RoleLeaveNotificationSeenAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="EMPLOYEE")


class HRLeaveNotificationSeenAdmin(RoleLeaveNotificationSeenAdmin):
    def get_queryset(self, request):
        return super().get_queryset(request).filter(user__role="HR")


@login_required
@never_cache
@admin.register(EmployeeLeaveNotificationSeen)
class EmployeeLeaveNotificationSeenProxyAdmin(EmployeeLeaveNotificationSeenAdmin):
    pass


@login_required
@never_cache
@admin.register(HRLeaveNotificationSeen)
class HRLeaveNotificationSeenProxyAdmin(HRLeaveNotificationSeenAdmin):
    pass





# upload csv file with preview 
@login_required
@never_cache
@admin.register(CompanyHoliday)
class CompanyHolidayAdmin(DeleteAuditedAdminMixin, admin.ModelAdmin):
    form = CompanyHolidayAdminForm

    list_display = ("name", "date", "is_optional")
    search_fields = ("name", "date")
    ordering = ("date", "name")
    date_hierarchy = "date"
    list_filter = ("is_optional", "name", "date")

    change_list_template = "admin/companyholiday_changelist.html"
    fields = ("name", "date", "is_optional", "change_reason")

    def save_model(self, request, obj, form, change):
        previous = CompanyHoliday.objects.get(pk=obj.pk) if change and obj.pk else None
        super().save_model(request, obj, form, change)
        if previous:
            field_names = [field.name for field in obj._meta.fields if field.name not in {"id", "created_at"}]
            _create_admin_audit_log(
                request,
                obj,
                _collect_model_changes(previous, obj, field_names),
                form.cleaned_data.get("change_reason"),
            )
        elif obj.pk:
            self._log_create(request, obj, form.cleaned_data.get("change_reason") or "Created from Django admin.")

    def get_urls(self):
        
        urls = super().get_urls()
        custom_urls = [path("upload-csv/", self.upload_csv, name="companyholiday_upload_csv"),]
        return custom_urls + urls

    def upload_csv(self, request):

        if request.method == "POST":
            if "confirm_upload" in request.POST:
                preview_data = request.session.pop("holiday_upload_preview_data", [])
                change_reason = (request.POST.get("change_reason") or "").strip()

                if not change_reason:
                    self.message_user(request, "Audit reason is required before confirming holiday CSV upload.", level=messages.ERROR)
                    return redirect(request.path)

                created = 0
                skipped = 0
                created_rows = []
                skipped_rows = []

                for item in preview_data:
                    obj, created_flag = CompanyHoliday.objects.get_or_create(
                        date=datetime.strptime(item["date_str"], "%Y-%m-%d").date(),
                        defaults={"name": item["name"], "is_optional": item["is_optional"]},
                    )

                    if created_flag:
                        created += 1
                        created_rows.append({"name": item["name"], "date": item["date_str"]})
                        _create_admin_audit_log(
                            request,
                            obj,
                            {"csv_upload": {"old": None, "new": _snapshot_model_fields(obj, {"id"})}},
                            change_reason,
                            action="CREATE",
                        )
                    else:
                        skipped += 1
                        skipped_rows.append({"name": item["name"], "date": item["date_str"]})

                _create_admin_audit_log(
                    request,
                    request.user,
                    {
                        "holiday_csv_upload_summary": {
                            "old": None,
                            "new": {
                                "created_count": created,
                                "skipped_count": skipped,
                                "created_rows": created_rows,
                                "skipped_rows": skipped_rows,
                            },
                        }
                    },
                    change_reason,
                    action="IMPORT",
                )

                self.message_user(request, f"Upload completed. Created: {created}, Skipped: {skipped}", level=messages.SUCCESS)
                return redirect("..")

            form = HolidayUploadForm(request.POST, request.FILES)

            if form.is_valid():
                change_reason = form.cleaned_data["change_reason"].strip()
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

                        preview_data.append({
                            "name": name,
                            "date": date_obj.isoformat(),
                            "date_str": date_obj.isoformat(),
                            "is_optional": is_optional,
                            "exists": exists,
                        })

                    except ValueError:
                        errors.append(f"Row {i}: Invalid date format (use YYYY-MM-DD)")

                request.session["holiday_upload_preview_data"] = preview_data
                return render(request, "admin/holiday_preview.html", {
                    "preview_data": preview_data,
                    "errors": errors,
                    "change_reason": change_reason,
                })

        else:
            
            form = HolidayUploadForm()

        return render(request, "admin/holiday_upload.html", {"form": form})


@login_required
@never_cache
@admin.register(WorkFromHomeDay)
class WorkFromHomeDayAdmin(DeleteAuditedAdminMixin, admin.ModelAdmin):
    form = WorkFromHomeDayAdminForm
    list_display = ("weekday", "is_active", "updated_at")
    list_filter = ("is_active",)
    ordering = ("weekday",)
    fields = ("weekday", "is_active", "change_reason")

    def save_model(self, request, obj, form, change):
        previous = WorkFromHomeDay.objects.get(pk=obj.pk) if change and obj.pk else None
        super().save_model(request, obj, form, change)
        if previous:
            field_names = [field.name for field in obj._meta.fields if field.name not in {"id", "updated_at"}]
            _create_admin_audit_log(
                request,
                obj,
                _collect_model_changes(previous, obj, field_names),
                form.cleaned_data.get("change_reason"),
            )
        elif obj.pk:
            self._log_create(request, obj, form.cleaned_data.get("change_reason") or "Created from Django admin.")


class BaseAdminAuditLogAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    model_label_filter = None
    model_label_filters = None
    action_filter = None
    list_display = ("model_label", "object_repr", "action", "change_summary", "updated_by", "changed_at", "reason")
    list_filter = ("model_label", "action", "updated_by", "changed_at")
    search_fields = ("model_label", "object_repr", "updated_by__username", "reason")
    readonly_fields = ("model_label", "object_id", "object_repr", "action", "updated_by", "changed_at", "reason", "changes")

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if self.model_label_filter:
            return queryset.filter(model_label=self.model_label_filter)
        if self.model_label_filters:
            queryset = queryset.filter(model_label__in=self.model_label_filters)
        if self.action_filter:
            queryset = queryset.filter(action=self.action_filter)
        return queryset

    @admin.display(description="Summary")
    def change_summary(self, obj):
        if not obj.changes:
            return "-"
        if "deleted_record" in obj.changes:
            return "Deleted record"
        if "archive_pdf" in obj.changes:
            return "Archive PDF"
        if "year_end_carry_forward" in obj.changes:
            return "Year-end carry forward"
        return ", ".join(obj.changes.keys())


@login_required
@never_cache
@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(BaseAdminAuditLogAdmin):
    pass


@login_required
@never_cache
@admin.register(UserAdminAudit)
class UserAdminAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filter = "App.CustomUser"


@login_required
@never_cache
@admin.register(ProfileAdminAudit)
class ProfileAdminAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filter = "App.Profile"


@login_required
@never_cache
@admin.register(LeaveAdminAudit)
class LeaveAdminAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filter = "App.Leave"


@login_required
@never_cache
@admin.register(HolidayAdminAudit)
class HolidayAdminAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filter = "App.CompanyHoliday"


@login_required
@never_cache
@admin.register(WorkFromHomeAdminAudit)
class WorkFromHomeAdminAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filter = "App.WorkFromHomeDay"


@login_required
@never_cache
@admin.register(DeleteAdminAudit)
class DeleteAdminAuditAdmin(BaseAdminAuditLogAdmin):
    action_filter = "DELETE"


COMMUNICATION_AUDIT_LABELS = (
    "App.Communication",
    "App.EmployeeCommunication",
    "App.HRCommunication",
)

EMPLOYEE_COMMUNICATION_AUDIT_LABELS = (
    "App.EmployeeCommunication",
)

HR_COMMUNICATION_AUDIT_LABELS = (
    "App.HRCommunication",
)

EMPLOYEE_COMMUNICATION_READ_SEEN_AUDIT_LABELS = (
    "App.EmployeeCommunicationRead",
    "App.EmployeeCommunicationSeen",
)

HR_COMMUNICATION_READ_SEEN_AUDIT_LABELS = (
    "App.HRCommunicationRead",
    "App.HRCommunicationSeen",
)

EMPLOYEE_LEAVE_NOTIFICATION_READ_SEEN_AUDIT_LABELS = (
    "App.EmployeeLeaveNotificationRead",
    "App.EmployeeLeaveNotificationSeen",
)

HR_LEAVE_NOTIFICATION_READ_SEEN_AUDIT_LABELS = (
    "App.HRLeaveNotificationRead",
    "App.HRLeaveNotificationSeen",
)

ALL_COMMUNICATION_NOTIFICATION_AUDIT_LABELS = (
    *COMMUNICATION_AUDIT_LABELS,
    *EMPLOYEE_COMMUNICATION_READ_SEEN_AUDIT_LABELS,
    *HR_COMMUNICATION_READ_SEEN_AUDIT_LABELS,
    *EMPLOYEE_LEAVE_NOTIFICATION_READ_SEEN_AUDIT_LABELS,
    *HR_LEAVE_NOTIFICATION_READ_SEEN_AUDIT_LABELS,
)


@login_required
@never_cache
@admin.register(AllCommunicationNotificationAudit)
class AllCommunicationNotificationAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = ALL_COMMUNICATION_NOTIFICATION_AUDIT_LABELS


@login_required
@never_cache
@admin.register(EmployeeCommunicationAudit)
class EmployeeCommunicationAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = EMPLOYEE_COMMUNICATION_AUDIT_LABELS


@login_required
@never_cache
@admin.register(HRCommunicationAudit)
class HRCommunicationAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = HR_COMMUNICATION_AUDIT_LABELS


@login_required
@never_cache
@admin.register(EmployeeCommunicationReadSeenAudit)
class EmployeeCommunicationReadSeenAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = EMPLOYEE_COMMUNICATION_READ_SEEN_AUDIT_LABELS


@login_required
@never_cache
@admin.register(HRCommunicationReadSeenAudit)
class HRCommunicationReadSeenAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = HR_COMMUNICATION_READ_SEEN_AUDIT_LABELS


@login_required
@never_cache
@admin.register(EmployeeLeaveNotificationReadSeenAudit)
class EmployeeLeaveNotificationReadSeenAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = EMPLOYEE_LEAVE_NOTIFICATION_READ_SEEN_AUDIT_LABELS


@login_required
@never_cache
@admin.register(HRLeaveNotificationReadSeenAudit)
class HRLeaveNotificationReadSeenAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = HR_LEAVE_NOTIFICATION_READ_SEEN_AUDIT_LABELS


class BaseLogViewerAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    log_key = "all"
    log_title = "Logs"

    def changelist_view(self, request, extra_context=None):
        try:
            lines = int(request.GET.get("lines", ADMIN_LOG_VIEW_DEFAULT_LINES))
        except (TypeError, ValueError):
            lines = ADMIN_LOG_VIEW_DEFAULT_LINES
        lines = max(1, min(lines, ADMIN_LOG_VIEW_MAX_LINES))
        query = (request.GET.get("q") or "").strip()[:120]
        level = (request.GET.get("level") or "").strip().upper()
        if level not in ADMIN_LOG_LEVELS:
            level = ""
        try:
            max_results = int(request.GET.get("max_results", ADMIN_LOG_SEARCH_DEFAULT_RESULTS))
        except (TypeError, ValueError):
            max_results = ADMIN_LOG_SEARCH_DEFAULT_RESULTS
        max_results = max(1, min(max_results, ADMIN_LOG_SEARCH_MAX_RESULTS))

        log_files = [
            _safe_log_file_entry(label, relative_path, lines, query=query, level=level, max_results=max_results)
            for label, relative_path in LOG_VIEWER_FILES[self.log_key]
        ]

        context = {
            **self.admin_site.each_context(request),
            "title": self.log_title,
            "subtitle": f"Showing latest {lines} line(s) per file",
            "opts": self.model._meta,
            "log_files": log_files,
            "line_count": lines,
            "max_lines": ADMIN_LOG_VIEW_MAX_LINES,
            "query": query,
            "level": level,
            "levels": sorted(ADMIN_LOG_LEVELS),
            "max_results": max_results,
            "max_search_results": ADMIN_LOG_SEARCH_MAX_RESULTS,
            "is_searching": bool(query or level),
        }
        return TemplateResponse(request, "admin/log_viewer.html", context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@login_required
@never_cache
@admin.register(LogViewer)
class LogViewerAdmin(BaseLogViewerAdmin):
    log_key = "all"
    log_title = "All logs"


@login_required
@never_cache
@admin.register(SecurityLogViewer)
class SecurityLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "security"
    log_title = "Security logs"


@login_required
@never_cache
@admin.register(AuthLogViewer)
class AuthLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "auth"
    log_title = "Authentication logs"


@login_required
@never_cache
@admin.register(LeaveLogViewer)
class LeaveLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "leave"
    log_title = "Leave logs"


@login_required
@never_cache
@admin.register(EmailLogViewer)
class EmailLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "email"
    log_title = "Email logs"


@login_required
@never_cache
@admin.register(BackupLogViewer)
class BackupLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "backup"
    log_title = "Backup logs"


@login_required
@never_cache
@admin.register(MaintenanceLogViewer)
class MaintenanceLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "maintenance"
    log_title = "Maintenance logs"


@login_required
@never_cache
@admin.register(SchedulerLogViewer)
class SchedulerLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "scheduler"
    log_title = "Scheduler logs"


@login_required
@never_cache
@admin.register(ServiceLogViewer)
class ServiceLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "services"
    log_title = "Service logs"


@login_required
@never_cache
@admin.register(ApiLogViewer)
class ApiLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "api"
    log_title = "API logs"


@login_required
@never_cache
@admin.register(ProfileLogViewer)
class ProfileLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "profile"
    log_title = "Profile logs"


@login_required
@never_cache
@admin.register(AnalyticsLogViewer)
class AnalyticsLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "analytics"
    log_title = "Analytics logs"


@login_required
@never_cache
@admin.register(MasterLogViewer)
class MasterLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "master"
    log_title = "Master logs"


@login_required
@never_cache
@admin.register(DjangoErrorLogViewer)
class DjangoErrorLogViewerAdmin(BaseLogViewerAdmin):
    log_key = "django_errors"
    log_title = "Django error logs"


@login_required
@never_cache
@admin.register(ServiceActionControl)
class ServiceActionControlAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can run service actions.", level=messages.ERROR)
            return redirect("admin:index")

        if request.method == "POST":
            service_action = (request.POST.get("service_action") or "").strip()
            confirmation = (request.POST.get("confirmation") or "").strip()
            reason = (request.POST.get("reason") or "").strip()

            if not reason:
                self.message_user(request, "Reason is required.", level=messages.ERROR)
                return redirect(request.path)

            try:
                if service_action == "backup":
                    if confirmation != "RUN_BACKUP":
                        self.message_user(request, "Type RUN_BACKUP to run backup.", level=messages.ERROR)
                        return redirect(request.path)
                    from manage_backups import run_backup

                    did_backup = run_backup()
                    if did_backup:
                        _create_admin_audit_log(
                            request,
                            request.user,
                            {"service_action": {"old": None, "new": {"action": "backup"}}},
                            reason,
                            action="SERVICE_BACKUP",
                        )
                        service_admin_logger.info("SERVICE_ADMIN | BACKUP | Run by=%s | Reason=%s", request.user.username, reason)
                        self.message_user(request, "Backup completed.", level=messages.SUCCESS)
                    else:
                        self.message_user(request, "Backup failed. Check service logs.", level=messages.ERROR)

                elif service_action == "weekly_report":
                    if confirmation != "SEND_WEEKLY_REPORT":
                        self.message_user(request, "Type SEND_WEEKLY_REPORT to send weekly report.", level=messages.ERROR)
                        return redirect(request.path)
                    from App.services.weekly_report_service import send_weekly_hr_report

                    sent = send_weekly_hr_report()
                    if sent:
                        _create_admin_audit_log(
                            request,
                            request.user,
                            {"service_action": {"old": None, "new": {"action": "weekly_report"}}},
                            reason,
                            action="SERVICE_WEEKLY_REPORT",
                        )
                        service_admin_logger.info("SERVICE_ADMIN | WEEKLY_REPORT | Sent by=%s | Reason=%s", request.user.username, reason)
                        self.message_user(request, "Weekly report sent.", level=messages.SUCCESS)
                    else:
                        self.message_user(request, "Weekly report was not sent. Check service/email logs.", level=messages.ERROR)

                elif service_action == "weekly_pdf":
                    if confirmation != "GENERATE_WEEKLY_PDF":
                        self.message_user(request, "Type GENERATE_WEEKLY_PDF to generate weekly PDF.", level=messages.ERROR)
                        return redirect(request.path)

                    output_path = _save_admin_weekly_report_pdf()
                    _create_admin_audit_log(
                        request,
                        request.user,
                        {"service_action": {"old": None, "new": {"action": "weekly_pdf", "file": output_path.name}}},
                        reason,
                        action="SERVICE_WEEKLY_PDF",
                    )
                    service_admin_logger.info("SERVICE_ADMIN | WEEKLY_PDF | Generated by=%s | File=%s | Reason=%s", request.user.username, output_path, reason)
                    self.message_user(request, f"Weekly PDF generated: {output_path.name}", level=messages.SUCCESS)

                elif service_action == "startup_checks":
                    if confirmation != "RUN_STARTUP_CHECKS":
                        self.message_user(request, "Type RUN_STARTUP_CHECKS to run startup checks.", level=messages.ERROR)
                        return redirect(request.path)
                    from App.services.startup_checks import run_selected_startup_checks

                    selected = {
                        "backup": request.POST.get("check_backup") == "on",
                        "weekly_report": request.POST.get("check_weekly_report") == "on",
                        "year_end": request.POST.get("check_year_end") == "on",
                    }
                    if not any(selected.values()):
                        self.message_user(request, "Select at least one startup check.", level=messages.ERROR)
                        return redirect(request.path)

                    run_selected_startup_checks(selected)
                    _create_admin_audit_log(
                        request,
                        request.user,
                        {"service_action": {"old": None, "new": {"action": "startup_checks", "selected": selected}}},
                        reason,
                        action="SERVICE_STARTUP_CHECKS",
                    )
                    service_admin_logger.info("SERVICE_ADMIN | STARTUP_CHECKS | Run by=%s | Selected=%s | Reason=%s", request.user.username, selected, reason)
                    self.message_user(request, "Startup checks finished. Review service logs for details.", level=messages.SUCCESS)

                elif service_action == "year_end":
                    if confirmation != "RUN_YEAR_END_CARRY_FORWARD":
                        self.message_user(request, "Type RUN_YEAR_END_CARRY_FORWARD to run year-end carry forward.", level=messages.ERROR)
                        return redirect(request.path)
                    from App.services.year_end_service import run_year_end_carry_forward_if_due

                    did_run = run_year_end_carry_forward_if_due()
                    _create_admin_audit_log(
                        request,
                        request.user,
                        {"service_action": {"old": None, "new": {"action": "year_end", "did_run": did_run}}},
                        reason,
                        action="SERVICE_YEAR_END",
                    )
                    service_admin_logger.info("SERVICE_ADMIN | YEAR_END | Run by=%s | DidRun=%s | Reason=%s", request.user.username, did_run, reason)
                    self.message_user(
                        request,
                        "Year-end carry forward completed." if did_run else "Year-end carry forward skipped. Check status/logs.",
                        level=messages.SUCCESS if did_run else messages.WARNING,
                    )

                else:
                    self.message_user(request, "Unknown service action.", level=messages.ERROR)

            except Exception as exc:
                service_admin_logger.error("SERVICE_ADMIN | FAILED | Action=%s | By=%s | Error=%s", service_action, request.user.username, exc)
                _create_admin_audit_log(
                    request,
                    request.user,
                    {"service_action": {"old": None, "new": {"action": service_action, "error": str(exc)}}},
                    reason,
                    action="SERVICE_ACTION_FAILED",
                )
                self.message_user(request, f"Service action failed: {exc}", level=messages.ERROR)

            return redirect(request.path)

        from App.services.startup_checks import (
            get_backup_catchup_status,
            get_weekly_report_catchup_status,
            get_year_end_catchup_status,
        )
        from App.services.uptime_tracker import format_current_uptime, get_app_started_at
        from App.services.weekly_report_service import build_weekly_hr_report_context
        from App.services.year_end_service import get_year_end_carry_forward_status

        weekly_context = build_weekly_hr_report_context()
        startup_status = {
            "backup": get_backup_catchup_status(),
            "weekly_report": get_weekly_report_catchup_status(),
            "year_end": get_year_end_catchup_status(),
        }
        started_at = get_app_started_at()
        context = {
            **self.admin_site.each_context(request),
            "title": "Service actions",
            "opts": self.model._meta,
            "maintenance_mode_enabled": is_maintenance_mode_enabled(),
            "latest_backup": _get_latest_file_info(settings.BASE_DIR / "backups", "backup_*.zip"),
            "latest_pdf": _get_latest_file_info(settings.BASE_DIR / "generated_pdfs", "*.pdf"),
            "startup_status": startup_status,
            "weekly_report_preview": weekly_context,
            "year_end_status": get_year_end_carry_forward_status(),
            "uptime_text": format_current_uptime(),
            "started_at": localtime(started_at) if started_at else None,
        }
        return TemplateResponse(request, "admin/service_actions.html", context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@login_required
@never_cache
@admin.register(BackupRestoreControl)
class BackupRestoreControlAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can restore database backups.", level=messages.ERROR)
            return redirect("admin:index")

        if request.method == "POST":
            backup_name = (request.POST.get("backup_name") or "").strip()
            confirmation = (request.POST.get("confirmation") or "").strip()
            restore_reason = (request.POST.get("restore_reason") or "").strip()

            if not is_maintenance_mode_enabled():
                self.message_user(request, "Enable maintenance mode before restoring a database backup.", level=messages.ERROR)
                return redirect(request.path)

            if confirmation != "RESTORE":
                self.message_user(request, "Type RESTORE to confirm database restore.", level=messages.ERROR)
                return redirect(request.path)

            if not restore_reason:
                self.message_user(request, "Restore reason is required.", level=messages.ERROR)
                return redirect(request.path)

            backup_path = _get_safe_backup_path(backup_name)
            if not backup_path:
                self.message_user(request, "Selected backup file is invalid or missing.", level=messages.ERROR)
                return redirect(request.path)

            try:
                from manage_backups import restore_backup_file

                message = restore_backup_file(backup_path)
                _create_admin_audit_log(
                    request,
                    request.user,
                    {"database_restore": {"old": None, "new": {"backup": backup_path.name}}},
                    restore_reason,
                    action="RESTORE",
                )
                self.message_user(request, message, level=messages.SUCCESS)
            except Exception as exc:
                _create_admin_audit_log(
                    request,
                    request.user,
                    {"database_restore": {"old": None, "new": {"backup": backup_name, "error": str(exc)}}},
                    restore_reason,
                    action="RESTORE_FAILED",
                )
                self.message_user(request, f"Restore failed: {exc}", level=messages.ERROR)

            return redirect(request.path)

        query = (request.GET.get("q") or "").strip()[:120]
        context = {
            **self.admin_site.each_context(request),
            "title": "Backup restore",
            "opts": self.model._meta,
            "backups": None,
            "database_engine": settings.DATABASES["default"]["ENGINE"],
            "query": query,
            "maintenance_mode_enabled": is_maintenance_mode_enabled(),
        }
        paginator = Paginator(_get_backup_restore_files(query), 5)
        page_obj = paginator.get_page(request.GET.get("page"))
        context["backups"] = page_obj
        context["page_obj"] = page_obj
        return TemplateResponse(request, "admin/backup_restore.html", context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@login_required
@never_cache
@admin.register(MaintenanceModeControl)
class MaintenanceModeControlAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        if not request.user.is_superuser:
            self.message_user(request, "Only superusers can change maintenance mode.", level=messages.ERROR)
            return redirect("admin:index")

        if request.method == "POST":
            requested_action = (request.POST.get("maintenance_action") or "").strip()
            reason = (request.POST.get("reason") or "").strip()
            confirmation = (request.POST.get("confirmation") or "").strip()

            if not reason:
                self.message_user(request, "Reason is required.", level=messages.ERROR)
                return redirect(request.path)

            if requested_action == "enable":
                if confirmation != "MAINTENANCE":
                    self.message_user(request, "Type MAINTENANCE to enable maintenance mode.", level=messages.ERROR)
                    return redirect(request.path)
                enable_maintenance_mode()
                _create_admin_audit_log(
                    request,
                    request.user,
                    {"maintenance_mode": {"old": "disabled", "new": "enabled"}},
                    reason,
                    action="MAINTENANCE_ON",
                )
                maintenance_logger.info(
                    "MAINTENANCE | ENABLED | By: %s | Reason: %s",
                    request.user.username,
                    reason,
                )
                self.message_user(request, "Maintenance mode enabled.", level=messages.SUCCESS)
            elif requested_action == "disable":
                disable_maintenance_mode()
                _create_admin_audit_log(
                    request,
                    request.user,
                    {"maintenance_mode": {"old": "enabled", "new": "disabled"}},
                    reason,
                    action="MAINTENANCE_OFF",
                )
                maintenance_logger.info(
                    "MAINTENANCE | DISABLED | By: %s | Reason: %s",
                    request.user.username,
                    reason,
                )
                self.message_user(request, "Maintenance mode disabled.", level=messages.SUCCESS)
            else:
                self.message_user(request, "Unknown maintenance action.", level=messages.ERROR)

            return redirect(request.path)

        context = {
            **self.admin_site.each_context(request),
            "title": "Maintenance mode",
            "opts": self.model._meta,
            "maintenance_mode_enabled": is_maintenance_mode_enabled(),
        }
        return TemplateResponse(request, "admin/maintenance_mode.html", context)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


ADMIN_AUDIT_OBJECT_NAMES = {
    "AdminAuditLog",
    "UserAdminAudit",
    "ProfileAdminAudit",
    "LeaveAdminAudit",
    "HolidayAdminAudit",
    "WorkFromHomeAdminAudit",
    "LeaveBalanceAdminAudit",
    "DeleteAdminAudit",
}

COMMUNICATION_NOTIFICATION_OBJECT_NAMES = {
    "EmployeeCommunication",
    "HRCommunication",
    "EmployeeCommunicationRead",
    "HRCommunicationRead",
    "EmployeeCommunicationSeen",
    "HRCommunicationSeen",
    "EmployeeLeaveNotificationRead",
    "HRLeaveNotificationRead",
    "EmployeeLeaveNotificationSeen",
    "HRLeaveNotificationSeen",
}

COMMUNICATION_NOTIFICATION_AUDIT_OBJECT_NAMES = {
    "AllCommunicationNotificationAudit",
    "EmployeeCommunicationAudit",
    "HRCommunicationAudit",
    "EmployeeCommunicationReadSeenAudit",
    "HRCommunicationReadSeenAudit",
    "EmployeeLeaveNotificationReadSeenAudit",
    "HRLeaveNotificationReadSeenAudit",
}

LOG_VIEWER_OBJECT_NAMES = {
    "LogViewer",
    "SecurityLogViewer",
    "AuthLogViewer",
    "LeaveLogViewer",
    "EmailLogViewer",
    "BackupLogViewer",
    "MaintenanceLogViewer",
    "SchedulerLogViewer",
    "ServiceLogViewer",
    "ApiLogViewer",
    "ProfileLogViewer",
    "AnalyticsLogViewer",
    "MasterLogViewer",
    "DjangoErrorLogViewer",
}

BACKUP_MANAGEMENT_OBJECT_NAMES = {
    "ServiceActionControl",
    "BackupRestoreControl",
    "MaintenanceModeControl",
}

HIDDEN_ADMIN_OBJECT_NAMES = {
    "Communication",
    "CommunicationRead",
    "CommunicationSeen",
    "LeaveNotificationRead",
    "LeaveNotificationSeen",
}

_default_get_app_list = admin.site.get_app_list


def get_grouped_admin_app_list(request, app_label=None):
    app_list = _default_get_app_list(request, app_label)
    audit_models = []
    communication_notification_models = []
    communication_notification_audit_models = []
    log_viewer_models = []
    backup_management_models = []
    grouped_app_list = []

    for app in app_list:
        remaining_models = []
        for model in app["models"]:
            if model.get("object_name") in ADMIN_AUDIT_OBJECT_NAMES:
                audit_models.append(model)
            elif model.get("object_name") in COMMUNICATION_NOTIFICATION_OBJECT_NAMES:
                communication_notification_models.append(model)
            elif model.get("object_name") in COMMUNICATION_NOTIFICATION_AUDIT_OBJECT_NAMES:
                communication_notification_audit_models.append(model)
            elif model.get("object_name") in LOG_VIEWER_OBJECT_NAMES:
                log_viewer_models.append(model)
            elif model.get("object_name") in BACKUP_MANAGEMENT_OBJECT_NAMES:
                backup_management_models.append(model)
            elif model.get("object_name") in HIDDEN_ADMIN_OBJECT_NAMES:
                continue
            else:
                remaining_models.append(model)

        if remaining_models:
            app["models"] = remaining_models
            grouped_app_list.append(app)

    if audit_models:
        grouped_app_list.insert(0, {
            "name": "Admin Audit",
            "app_label": "admin_audit",
            "app_url": "",
            "has_module_perms": True,
            "models": audit_models,
        })

    if communication_notification_models:
        grouped_app_list.insert(1 if audit_models else 0, {
            "name": "Communication and Notifications",
            "app_label": "communication_notifications",
            "app_url": "",
            "has_module_perms": True,
            "models": communication_notification_models,
        })

    if communication_notification_audit_models:
        insert_at = 0
        if audit_models:
            insert_at += 1
        if communication_notification_models:
            insert_at += 1
        grouped_app_list.insert(insert_at, {
            "name": "Communication and Notification Audit",
            "app_label": "communication_notification_audit",
            "app_url": "",
            "has_module_perms": True,
            "models": communication_notification_audit_models,
        })

    if log_viewer_models:
        insert_at = 0
        if audit_models:
            insert_at += 1
        if communication_notification_models:
            insert_at += 1
        if communication_notification_audit_models:
            insert_at += 1
        grouped_app_list.insert(insert_at, {
            "name": "Logs",
            "app_label": "logs",
            "app_url": "",
            "has_module_perms": True,
            "models": log_viewer_models,
        })

    if backup_management_models:
        insert_at = 0
        if audit_models:
            insert_at += 1
        if communication_notification_models:
            insert_at += 1
        if communication_notification_audit_models:
            insert_at += 1
        if log_viewer_models:
            insert_at += 1
        grouped_app_list.insert(insert_at, {
            "name": "Services",
            "app_label": "services",
            "app_url": "",
            "has_module_perms": True,
            "models": backup_management_models,
        })

    return grouped_app_list


admin.site.get_app_list = get_grouped_admin_app_list
