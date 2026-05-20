from django.contrib import admin, messages
from django.views.decorators.cache import never_cache
from django.contrib.auth.decorators import login_required
from .models import (
    AdminAuditLog,
    AdminCommunicationAudit,
    AdminCommunicationCenter,
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
    EmailDeliveryLog,
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
from django.core import signing
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import path, reverse
from django.http import HttpResponse, JsonResponse
from django.utils.html import format_html
from django.core.files.base import ContentFile
from django.core.paginator import Paginator
from django.template.response import TemplateResponse
from datetime import date, datetime, time
from io import BytesIO
import csv
import json
import logging
import os
import re
import zipfile
from urllib.parse import urlencode
from django.utils.timezone import now, localtime
from django.utils import timezone
from App.services.maintenance_mode import (
    disable_maintenance_mode,
    enable_maintenance_mode,
    is_maintenance_mode_enabled,
)
from App.services import admin_leave_workflow


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
    admin_conflict_preview_token = forms.CharField(required=False, widget=forms.HiddenInput)
    admin_conflict_preview_decision = forms.CharField(required=False, widget=forms.HiddenInput)
    admin_skip_wfh_bridge = forms.BooleanField(
        required=False,
        label="Do not auto-expand WFH bridge for this save",
        help_text="Admin-only override. Keeps the entered full-day range instead of joining nearby leaves through WFH bridge days.",
    )

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
        token = cleaned_data.get("admin_conflict_preview_token") or ""
        decision = cleaned_data.get("admin_conflict_preview_decision") or ""

        if not token:
            raise ValidationError("Run admin conflict/impact preview before saving this leave.")

        if decision not in {"reviewed", "override"}:
            raise ValidationError("Confirm the admin conflict/impact preview decision before saving this leave.")

        try:
            preview = signing.loads(token, salt="admin-leave-conflict-preview", max_age=1800)
        except signing.BadSignature as exc:
            raise ValidationError("Admin conflict/impact preview expired or is invalid. Run preview again.") from exc

        current_signature = _admin_leave_preview_signature_from_cleaned_data(cleaned_data, self.instance.pk)
        if preview.get("signature") != current_signature:
            raise ValidationError("Leave fields changed after preview. Run admin conflict/impact preview again.")

        if preview.get("status") in {"warning", "conflict"} and decision != "override":
            raise ValidationError("This preview has warnings/conflicts. Confirm override before saving.")

        cleaned_data["admin_conflict_preview_payload"] = preview
        return cleaned_data


def _admin_leave_preview_signature_from_cleaned_data(cleaned_data, leave_id=None):
    user = cleaned_data.get("user")
    from_date_value = cleaned_data.get("from_date")
    to_date_value = cleaned_data.get("to_date")
    from_datetime_value = cleaned_data.get("from_datetime")
    to_datetime_value = cleaned_data.get("to_datetime")
    payload = {
        "leave_id": str(leave_id or ""),
        "user_id": str(user.pk if user else ""),
        "leave_type": cleaned_data.get("leave_type") or "",
        "status": cleaned_data.get("status") or "",
        "deducted_from": cleaned_data.get("deducted_from") or "",
        "admin_skip_wfh_bridge": bool(cleaned_data.get("admin_skip_wfh_bridge")),
        "from_date": from_date_value.isoformat() if from_date_value else "",
        "to_date": to_date_value.isoformat() if to_date_value else "",
        "from_datetime": from_datetime_value.isoformat() if from_datetime_value else "",
        "to_datetime": to_datetime_value.isoformat() if to_datetime_value else "",
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))
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
    change_form_template = "admin/leave_change_form.html"
    actions = [
        "admin_approve_selected_leaves",
        "admin_reject_selected_leaves",
        "admin_sync_selected_leaves",
        "admin_delete_selected_leaves_with_workflow",
        "admin_recalculate_selected_leave_balances",
    ]

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
                'admin_skip_wfh_bridge',
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
            'fields': ('change_reason', 'admin_conflict_preview_token', 'admin_conflict_preview_decision'),
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

    def _normalize_admin_leave_status_fields(self, obj, request):
        if obj.status == "Pending":
            obj.approved_at = None
            obj.rejected_at = None
            obj.rejection_reason = ""
            obj.reviewed_by = None
            return

        if obj.status == "Approved":
            obj.rejected_at = None
            obj.rejection_reason = ""
            if not obj.approved_at:
                obj.approved_at = now()
            if not obj.reviewed_by_id:
                obj.reviewed_by = request.user
            return

        if obj.status == "Rejected":
            obj.approved_at = None
            if not obj.rejected_at:
                obj.rejected_at = now()
            if not obj.reviewed_by_id:
                obj.reviewed_by = request.user

    admin_workflow_configs = {
        "approve": {
            "title": "Confirm admin leave approval workflow",
            "action_name": "admin_approve_selected_leaves",
            "label": "Approve workflow",
            "needs_rejection_reason": False,
            "show_delivery_options": True,
        },
        "reject": {
            "title": "Confirm admin leave rejection workflow",
            "action_name": "admin_reject_selected_leaves",
            "label": "Reject workflow",
            "needs_rejection_reason": True,
            "show_delivery_options": True,
        },
        "sync": {
            "title": "Confirm admin leave sync workflow",
            "action_name": "admin_sync_selected_leaves",
            "label": "Sync/recalculate workflow",
            "needs_rejection_reason": False,
            "show_delivery_options": True,
        },
        "delete": {
            "title": "Confirm admin leave delete workflow",
            "action_name": "admin_delete_selected_leaves_with_workflow",
            "label": "Delete workflow",
            "needs_rejection_reason": False,
            "show_delivery_options": True,
        },
        "recalculate": {
            "title": "Confirm admin balance recalculation",
            "action_name": "admin_recalculate_selected_leave_balances",
            "label": "Recalculate balance only",
            "needs_rejection_reason": False,
            "show_delivery_options": False,
        },
    }

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "conflict-preview/",
                self.admin_site.admin_view(self.conflict_preview_view),
                name="app_leave_conflict_preview",
            ),
            path(
                "<path:object_id>/admin-workflow/<str:workflow_action>/",
                self.admin_site.admin_view(self.single_leave_workflow_view),
                name="app_leave_admin_workflow",
            ),
            path(
                "<path:object_id>/admin-workflow-skip/",
                self.admin_site.admin_view(self.skip_leave_workflow_prompt_view),
                name="app_leave_admin_workflow_skip",
            ),
        ]
        return custom_urls + urls

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_view(self, request, object_id, extra_context=None):
        self.message_user(
            request,
            "Leave records must be deleted through the admin delete workflow.",
            level=messages.INFO,
        )
        return redirect(reverse("admin:app_leave_admin_workflow", args=[object_id, "delete"]))

    def delete_model(self, request, obj):
        raise PermissionDenied("Leave records must be deleted through the admin delete workflow.")

    def delete_queryset(self, request, queryset):
        raise PermissionDenied("Leave records must be deleted through the admin delete workflow.")

    def _parse_preview_datetime(self, request, prefix):
        date_value = (request.POST.get(f"{prefix}_0") or "").strip()
        time_value = (request.POST.get(f"{prefix}_1") or "").strip()
        if not date_value or not time_value:
            return None
        parsed = datetime.combine(date.fromisoformat(date_value), time.fromisoformat(time_value))
        return timezone.make_aware(parsed) if timezone.is_naive(parsed) else parsed

    def _parse_preview_date(self, request, name):
        value = (request.POST.get(name) or "").strip()
        return date.fromisoformat(value) if value else None

    def _preview_signature_from_values(self, values):
        payload = {
            "leave_id": str(values.get("leave_id") or ""),
            "user_id": str(values["user"].pk if values.get("user") else ""),
            "leave_type": values.get("leave_type") or "",
            "status": values.get("status") or "",
            "deducted_from": values.get("deducted_from") or "",
            "admin_skip_wfh_bridge": bool(values.get("admin_skip_wfh_bridge")),
            "from_date": values.get("from_date").isoformat() if values.get("from_date") else "",
            "to_date": values.get("to_date").isoformat() if values.get("to_date") else "",
            "from_datetime": values.get("from_datetime").isoformat() if values.get("from_datetime") else "",
            "to_datetime": values.get("to_datetime").isoformat() if values.get("to_datetime") else "",
        }
        return json.dumps(payload, sort_keys=True, separators=(",", ":"))

    def _format_date_list(self, dates):
        return [item.strftime("%d %b %Y") for item in dates]

    def _format_range(self, start_date, end_date):
        if start_date == end_date:
            return start_date.strftime("%d %b %Y")
        return f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"

    def _admin_leave_conflict_preview(self, values):
        from App.services.leave_breakdown import calculate_leave_breakdown, expand_full_day_leave_range
        from App.services.overlap_service import get_overlap_details

        user = values["user"]
        leave_id = values.get("leave_id")
        leave_type = values["leave_type"]
        status = values["status"]
        deducted_from = values["deducted_from"]
        from_date = values["from_date"]
        to_date = values["to_date"]
        from_datetime = values["from_datetime"]
        to_datetime = values["to_datetime"]
        skip_wfh_bridge = bool(values.get("admin_skip_wfh_bridge"))
        active_status = status in {"Pending", "Approved"}
        full_day = leave_type in {"Sick", "Earned", "Unpaid"}
        warnings = []
        conflicts = []
        auto_added_dates = []
        requested_from = from_date
        requested_to = to_date
        effective_from = from_date
        effective_to = to_date

        if full_day:
            if skip_wfh_bridge:
                warnings.append("Admin override selected: WFH bridge auto-expansion will be skipped for this save.")
            else:
                expanded = expand_full_day_leave_range(user=user, start_date=from_date, end_date=to_date, exclude_id=leave_id)
                effective_from = expanded["start_date"]
                effective_to = expanded["end_date"]
                auto_added_dates = expanded["auto_added_dates"]
            breakdown = calculate_leave_breakdown(
                effective_from,
                effective_to,
                requested_start_date=requested_from,
                requested_end_date=requested_to,
            )
            leave_value = float(breakdown["working_days"] or 0)
        else:
            breakdown = calculate_leave_breakdown(from_date, to_date)
            leave_value = 0.25 if leave_type == "Short" else 0.5 if leave_type == "Half" else float(breakdown["working_days"] or 0)

        if auto_added_dates:
            warnings.append(
                "WFH bridge expanded the effective leave range with: "
                + ", ".join(self._format_date_list(auto_added_dates))
            )

        overlaps = get_overlap_details(user=user, start_date=effective_from, end_date=effective_to, exclude_id=leave_id)
        if overlaps and active_status:
            conflicts.append(f"{len(overlaps)} overlapping pending/approved leave record(s) found.")

        if leave_type in {"Short", "Half"} and active_status:
            same_day_opposite_type = "Half" if leave_type == "Short" else "Short"
            if Leave.objects.filter(user=user, leave_type=leave_type, from_date=from_date, status__in=["Pending", "Approved"]).exclude(pk=leave_id).exists():
                conflicts.append(f"Employee already has a {leave_type} leave on this date.")
            if Leave.objects.filter(user=user, leave_type=same_day_opposite_type, from_date=from_date, status__in=["Pending", "Approved"]).exclude(pk=leave_id).exists():
                conflicts.append(f"Employee already has a {same_day_opposite_type} leave on this date.")

            monthly_count = Leave.objects.filter(
                user=user,
                leave_type=leave_type,
                from_date__month=from_date.month,
                from_date__year=from_date.year,
                status__in=["Pending", "Approved"],
            ).exclude(pk=leave_id).count()
            monthly_limit = 2 if leave_type == "Short" else 1
            if monthly_count >= monthly_limit:
                conflicts.append(f"Monthly {leave_type} limit is already reached ({monthly_count}/{monthly_limit}).")

        try:
            balance = user.leavebalance
        except LeaveBalance.DoesNotExist:
            balance = None
        current_balance = {}
        expected_balance = {}
        if balance:
            current_balance = {
                "total_leave_remaining": round(float(balance.total_leave_remaining or 0), 2),
                "sick_remaining": round(float(balance.sick_total or 0) - float(balance.sick_used or 0), 2),
                "sick_used": round(float(balance.sick_used or 0), 2),
                "earned_remaining": round(float(balance.earned_total or 0) - float(balance.earned_used or 0), 2),
                "earned_used": round(float(balance.earned_used or 0), 2),
                "unpaid": round(float(balance.unpaid or 0), 2),
            }
            expected_balance = dict(current_balance)
            old_value = 0.0
            old_deducted_from = ""
            old_status_active = False
            if leave_id:
                old_leave = Leave.objects.filter(pk=leave_id).first()
                if old_leave:
                    old_status_active = old_leave.status in {"Pending", "Approved"}
                    old_deducted_from = old_leave.deducted_from
                    if old_leave.leave_type == "Short":
                        old_value = 0.25
                    elif old_leave.leave_type == "Half":
                        old_value = 0.5
                    else:
                        from App.services.leave_breakdown import calculate_leave_breakdown_for_leave
                        old_value = float(calculate_leave_breakdown_for_leave(old_leave)["working_days"] or 0)

            def apply_delta(target, source, value):
                if source == "Sick":
                    expected_balance["sick_used"] = round(expected_balance["sick_used"] + target * value, 2)
                    expected_balance["total_leave_remaining"] = round(expected_balance["total_leave_remaining"] - target * value, 2)
                elif source == "Earned":
                    expected_balance["earned_used"] = round(expected_balance["earned_used"] + target * value, 2)
                    expected_balance["total_leave_remaining"] = round(expected_balance["total_leave_remaining"] - target * value, 2)
                elif source == "Unpaid":
                    expected_balance["unpaid"] = round(expected_balance["unpaid"] + target * value, 2)

            if old_status_active:
                apply_delta(-1, old_deducted_from, old_value)
            if active_status:
                apply_delta(1, deducted_from if leave_type in {"Short", "Half"} else leave_type, leave_value)

            if expected_balance["total_leave_remaining"] < 0:
                conflicts.append("Expected paid leave balance goes below zero.")

            expected_balance["sick_remaining"] = round(float(balance.sick_total or 0) - expected_balance["sick_used"], 2)
            expected_balance["earned_remaining"] = round(float(balance.earned_total or 0) - expected_balance["earned_used"], 2)

            if expected_balance["sick_remaining"] < 0:
                conflicts.append("Expected Sick remaining balance goes below zero.")
            if expected_balance["earned_remaining"] < 0:
                conflicts.append("Expected Earned remaining balance goes below zero.")

        status_label = "conflict" if conflicts else "warning" if warnings else "safe"
        signature = self._preview_signature_from_values(values)
        token = signing.dumps({
            "signature": signature,
            "status": status_label,
            "warnings": warnings,
            "conflicts": conflicts,
            "requested_range": {
                "from": requested_from.isoformat(),
                "to": requested_to.isoformat(),
            },
            "effective_range": {
                "from": effective_from.isoformat(),
                "to": effective_to.isoformat(),
            },
            "auto_added_dates": [item.isoformat() for item in auto_added_dates],
            "working_days": leave_value,
            "admin_skip_wfh_bridge": skip_wfh_bridge,
        }, salt="admin-leave-conflict-preview")

        return {
            "token": token,
            "status": status_label,
            "warnings": warnings,
            "conflicts": conflicts,
            "requested_range": {"from": requested_from.isoformat(), "to": requested_to.isoformat()},
            "effective_range": {"from": effective_from.isoformat(), "to": effective_to.isoformat()},
            "admin_skip_wfh_bridge": skip_wfh_bridge,
            "effective_datetime": {
                "from_date": effective_from.isoformat(),
                "to_date": effective_to.isoformat(),
                "from_time": "10:00:00" if full_day else (localtime(from_datetime).strftime("%H:%M:%S") if from_datetime else ""),
                "to_time": "19:00:00" if full_day else (localtime(to_datetime).strftime("%H:%M:%S") if to_datetime else ""),
            },
            "auto_added_dates": self._format_date_list(auto_added_dates),
            "breakdown": {
                "working_days": leave_value,
                "weekend_days": breakdown.get("weekend_days", 0),
                "company_holiday_days": breakdown.get("company_holiday_days", 0),
                "included_wfh_days": breakdown.get("included_wfh_days", 0),
                "included_wfh_dates": self._format_date_list(breakdown.get("included_wfh_dates", [])),
                "included_weekend_dates": self._format_date_list(breakdown.get("included_weekend_dates", [])),
            },
            "overlaps": [
                {
                    "leave_type": item["leave_type"],
                    "status": item["status"],
                    "existing_from": item["existing_from"].isoformat(),
                    "existing_to": item["existing_to"].isoformat(),
                    "overlap_from": item["overlap_from"].isoformat(),
                    "overlap_to": item["overlap_to"].isoformat(),
                    "overlap_days": item["overlap_days"],
                }
                for item in overlaps
            ],
            "current_balance": current_balance,
            "expected_balance": expected_balance,
        }

    def conflict_preview_view(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)

        try:
            user_id = request.POST.get("user")
            user = get_user_model().objects.select_related("leavebalance").get(pk=user_id)
            leave_type = (request.POST.get("leave_type") or "").strip()
            status = (request.POST.get("status") or "Pending").strip()
            deducted_from = (request.POST.get("deducted_from") or "None").strip()
            skip_wfh_bridge = request.POST.get("admin_skip_wfh_bridge") in {"on", "true", "1", "yes"}
            object_id = (request.POST.get("object_id") or "").strip()
            leave_id = int(object_id) if object_id.isdigit() else None
            full_day = leave_type in {"Sick", "Earned", "Unpaid"}

            if leave_type in {"Short", "Half"}:
                from_datetime = self._parse_preview_datetime(request, "from_datetime")
                to_datetime = self._parse_preview_datetime(request, "to_datetime")
                if not from_datetime or not to_datetime:
                    return JsonResponse({"error": "From/to date-time is required."}, status=400)
                from_date = localtime(from_datetime).date()
                to_date = localtime(to_datetime).date()
            else:
                if not full_day:
                    return JsonResponse({"error": "Select a valid leave type."}, status=400)
                from_date = self._parse_preview_date(request, "from_date")
                to_date = self._parse_preview_date(request, "to_date")
                if not from_date or not to_date:
                    return JsonResponse({"error": "From/to date is required."}, status=400)
                from_datetime = timezone.make_aware(datetime.combine(from_date, time(10, 0)))
                to_datetime = timezone.make_aware(datetime.combine(to_date, time(19, 0)))

            if to_date < from_date:
                return JsonResponse({"error": "To date cannot be before from date."}, status=400)
            if to_datetime <= from_datetime:
                return JsonResponse({"error": "Leave end must be after leave start."}, status=400)

            values = {
                "leave_id": leave_id,
                "user": user,
                "leave_type": leave_type,
                "status": status,
                "deducted_from": deducted_from,
                "admin_skip_wfh_bridge": skip_wfh_bridge,
                "from_date": from_date,
                "to_date": to_date,
                "from_datetime": from_datetime,
                "to_datetime": to_datetime,
            }
            return JsonResponse({"success": True, "preview": self._admin_leave_conflict_preview(values)})
        except Exception as exc:
            return JsonResponse({"error": str(exc)}, status=400)

    def _get_single_workflow_urls(self, obj):
        if not obj or not obj.pk:
            return []
        return [
            {
                "key": key,
                "label": config["label"],
                "url": reverse("admin:app_leave_admin_workflow", args=[obj.pk, key]),
            }
            for key, config in self.admin_workflow_configs.items()
        ]

    def change_view(self, request, object_id, form_url="", extra_context=None):
        extra_context = extra_context or {}
        obj = self.get_object(request, object_id)
        workflow_urls = self._get_single_workflow_urls(obj)
        recommended_key = request.GET.get("recommended") or self._default_workflow_recommendation(obj)
        recent_workflow_audits = []
        if obj and obj.pk:
            recent_workflow_audits = AdminAuditLog.objects.filter(
                model_label=obj._meta.label,
                object_id=str(obj.pk),
                action__in=[
                    "ADMIN_APPROVE",
                    "ADMIN_REJECT",
                    "ADMIN_SYNC",
                    "ADMIN_DELETE_WF",
                    "ADMIN_EMAIL_FAIL",
                    "ADMIN_WORKFLOW_SKIPPED",
                ],
            ).order_by("-changed_at")[:5]
        extra_context.update({
            "admin_leave_workflow_urls": workflow_urls,
            "recommended_workflow_key": recommended_key,
            "recommended_workflow_url": next((item for item in workflow_urls if item["key"] == recommended_key), None),
            "admin_leave_workflow_skip_url": reverse("admin:app_leave_admin_workflow_skip", args=[obj.pk]) if obj else "",
            "recommendation_reason": request.GET.get("recommendation_reason") or self._default_workflow_recommendation_reason(obj),
            "show_admin_leave_workflow_prompt": request.GET.get("workflow_prompt") == "1",
            "recent_admin_leave_workflow_audits": recent_workflow_audits,
        })
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def skip_leave_workflow_prompt_view(self, request, object_id):
        if request.method != "POST":
            self.message_user(request, "POST required to skip workflow.", level=messages.ERROR)
            return redirect("admin:App_leave_change", object_id)

        if not Leave.objects.filter(pk=object_id).exists():
            self.message_user(request, "Leave record not found.", level=messages.ERROR)
            return redirect("admin:App_leave_changelist")

        workflow_action = (request.POST.get("workflow_action") or "post_save_prompt").strip()
        result = admin_leave_workflow.log_workflow_skipped(
            [object_id],
            request.user,
            workflow_action,
            reason="Admin skipped post-save workflow prompt.",
        )
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": True, "message": result})

        self.message_user(request, result, level=messages.INFO)
        return redirect("admin:App_leave_change", object_id)

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        if "_save" in request.POST or "_continue" in request.POST:
            change_url = reverse("admin:App_leave_change", args=[obj.pk])
            query = urlencode({
                "workflow_prompt": "1",
                "recommended": getattr(request, "_admin_leave_recommended_workflow", self._default_workflow_recommendation(obj)),
                "recommendation_reason": getattr(request, "_admin_leave_recommendation_reason", self._default_workflow_recommendation_reason(obj)),
            })
            return redirect(f"{change_url}?{query}")
        return response

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue=post_url_continue)
        if "_save" in request.POST or "_continue" in request.POST:
            change_url = reverse("admin:App_leave_change", args=[obj.pk])
            query = urlencode({
                "workflow_prompt": "1",
                "recommended": getattr(request, "_admin_leave_recommended_workflow", "sync"),
                "recommendation_reason": getattr(
                    request,
                    "_admin_leave_recommendation_reason",
                    "New admin-created leave should be synced with balance, email, and notifications if needed.",
                ),
            })
            return redirect(f"{change_url}?{query}")
        return response

    def _default_workflow_recommendation(self, obj):
        if obj and obj.status == "Pending":
            return "approve"
        return "sync"

    def _default_workflow_recommendation_reason(self, obj):
        if obj and obj.status == "Pending":
            return "Pending leave is waiting for an approve or reject decision."
        return "Saved leave may affect balance, email, or notification state."
    

    def save_model(self, request, obj, form, change):
        previous = Leave.objects.get(pk=obj.pk) if change and obj.pk else None
        preview_payload = form.cleaned_data.get("admin_conflict_preview_payload") or {}
        skip_wfh_bridge = bool(form.cleaned_data.get("admin_skip_wfh_bridge"))
        if obj.leave_type in {"Sick", "Earned", "Unpaid"}:
            obj.deducted_from = obj.leave_type
            obj.admin_skip_wfh_bridge = skip_wfh_bridge
            requested_range = preview_payload.get("requested_range") or {}
            effective_range = preview_payload.get("effective_range") or {}
            requested_from = date.fromisoformat(requested_range["from"]) if requested_range.get("from") else form.cleaned_data.get("from_date")
            requested_to = date.fromisoformat(requested_range["to"]) if requested_range.get("to") else form.cleaned_data.get("to_date")
            effective_from = date.fromisoformat(effective_range["from"]) if effective_range.get("from") else form.cleaned_data.get("from_date")
            effective_to = date.fromisoformat(effective_range["to"]) if effective_range.get("to") else form.cleaned_data.get("to_date")
            obj.requested_from_date = requested_from
            obj.requested_to_date = requested_to
            if not skip_wfh_bridge and effective_from and effective_to:
                obj.from_date = effective_from
                obj.to_date = effective_to
                obj.from_datetime = timezone.make_aware(datetime.combine(effective_from, time(10, 0)))
                obj.to_datetime = timezone.make_aware(datetime.combine(effective_to, time(19, 0)))
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
        self._normalize_admin_leave_status_fields(obj, request)
        obj.save(skip_validation=True)
        created_at_override = form.cleaned_data.get("created_at_override")
        if created_at_override:
            Leave.objects.filter(pk=obj.pk).update(created_at=created_at_override)
            obj.created_at = created_at_override
        if previous:
            field_names = [field.name for field in obj._meta.fields if field.name != "id"]
            changes = _collect_model_changes(previous, obj, field_names)
            if preview_payload:
                changes["admin_conflict_preview"] = {
                    "old": None,
                    "new": {
                        "status": preview_payload.get("status"),
                        "decision": form.cleaned_data.get("admin_conflict_preview_decision"),
                        "warnings": preview_payload.get("warnings", []),
                        "conflicts": preview_payload.get("conflicts", []),
                        "requested_range": preview_payload.get("requested_range"),
                        "effective_range": preview_payload.get("effective_range"),
                        "auto_added_dates": preview_payload.get("auto_added_dates", []),
                        "working_days": preview_payload.get("working_days"),
                        "admin_skip_wfh_bridge": preview_payload.get("admin_skip_wfh_bridge", False),
                    },
                }
            _create_admin_audit_log(
                request,
                obj,
                changes,
                form.cleaned_data.get("change_reason"),
            )
            workflow_sensitive_fields = {
                "status",
                "leave_type",
                "from_date",
                "to_date",
                "from_datetime",
                "to_datetime",
                "deducted_from",
                "approved_at",
                "rejected_at",
                "rejection_reason",
                "reviewed_by",
            }
            changed_sensitive_fields = sorted(workflow_sensitive_fields.intersection(form.changed_data))
            if "status" in changed_sensitive_fields:
                request._admin_leave_recommended_workflow = "sync"
                request._admin_leave_recommendation_reason = "Status changed manually, so sync/recalculate is recommended."
            elif changed_sensitive_fields:
                request._admin_leave_recommended_workflow = "sync"
                request._admin_leave_recommendation_reason = (
                    f"Workflow-sensitive field(s) changed: {', '.join(changed_sensitive_fields)}."
                )
            elif obj.status == "Pending":
                request._admin_leave_recommended_workflow = "approve"
                request._admin_leave_recommendation_reason = "Pending leave is waiting for an approve or reject decision."
        elif obj.pk:
            self._log_create(request, obj, form.cleaned_data.get("change_reason") or "Created from Django admin.")
            if preview_payload:
                _create_admin_audit_log(
                    request,
                    obj,
                    {
                        "admin_conflict_preview": {
                            "old": None,
                            "new": {
                                "status": preview_payload.get("status"),
                                "decision": form.cleaned_data.get("admin_conflict_preview_decision"),
                                "warnings": preview_payload.get("warnings", []),
                                "conflicts": preview_payload.get("conflicts", []),
                                "requested_range": preview_payload.get("requested_range"),
                                "effective_range": preview_payload.get("effective_range"),
                                "auto_added_dates": preview_payload.get("auto_added_dates", []),
                                "working_days": preview_payload.get("working_days"),
                                "admin_skip_wfh_bridge": preview_payload.get("admin_skip_wfh_bridge", False),
                            },
                        }
                    },
                    form.cleaned_data.get("change_reason") or "Created from Django admin.",
                    action="ADMIN_PREVIEW",
                )
            request._admin_leave_recommended_workflow = "sync"
            request._admin_leave_recommendation_reason = "New admin-created leave should be synced with balance and notifications if needed."
        if obj.user_id and obj.leave_type in {"Sick", "Earned", "Unpaid"}:
            admin_leave_workflow.recalculate_employee_balance(
                obj.user,
                request.user,
                form.cleaned_data.get("change_reason") or "Admin leave save",
                "Admin leave save bridge bypass" if skip_wfh_bridge else "Admin leave save preview range",
            )
            if skip_wfh_bridge:
                self.message_user(
                    request,
                    "WFH bridge auto-expansion was skipped for this admin save.",
                    level=messages.WARNING,
                )
            elif preview_payload.get("auto_added_dates"):
                self.message_user(
                    request,
                    "WFH bridge preview range was applied to this leave only.",
                    level=messages.INFO,
                )
        return

    def _render_leave_workflow_confirmation(
        self,
        request,
        queryset,
        title,
        action_name,
        needs_rejection_reason=False,
        show_delivery_options=True,
    ):
        selected_ids = list(queryset.values_list("pk", flat=True))
        workflow_action_key = self._workflow_action_key_from_action_name(action_name)
        ordered_queryset = queryset.select_related("user").order_by("id")
        context = {
            **self.admin_site.each_context(request),
            "title": title,
            "opts": self.model._meta,
            "preview": admin_leave_workflow.get_leave_admin_preview(
                ordered_queryset,
                workflow_action=workflow_action_key,
            ),
            "conflict_previews": self._bulk_leave_conflict_previews(ordered_queryset, workflow_action_key),
            "selected_ids": selected_ids,
            "selected_count": len(selected_ids),
            "action_name": action_name,
            "needs_rejection_reason": needs_rejection_reason,
            "show_delivery_options": show_delivery_options,
        }
        return TemplateResponse(request, "admin/admin_leave_workflow_confirm.html", context)

    def _bulk_leave_conflict_previews(self, queryset, workflow_action_key):
        previews = []
        for leave in queryset:
            preview_status = leave.status
            if workflow_action_key == "approve":
                preview_status = "Approved"
            elif workflow_action_key in {"reject", "delete"}:
                preview_status = "Rejected"

            values = {
                "leave_id": leave.id,
                "user": leave.user,
                "leave_type": leave.leave_type,
                "status": preview_status,
                "deducted_from": leave.deducted_from,
                "admin_skip_wfh_bridge": bool(getattr(leave, "admin_skip_wfh_bridge", False)),
                "from_date": leave.requested_from_date or leave.from_date,
                "to_date": leave.requested_to_date or leave.to_date,
                "from_datetime": leave.from_datetime,
                "to_datetime": leave.to_datetime,
            }
            try:
                result = self._admin_leave_conflict_preview(values)
                previews.append({
                    "leave_id": leave.id,
                    "employee": leave.user.get_full_name().strip() or leave.user.username,
                    "leave_type": leave.leave_type,
                    "current_status": leave.status,
                    "preview_status": preview_status,
                    "date_range": self._format_range(leave.from_date, leave.to_date),
                    "status": result["status"],
                    "warnings": result["warnings"],
                    "conflicts": result["conflicts"],
                    "effective_range": result["effective_range"],
                    "auto_added_dates": result["auto_added_dates"],
                    "breakdown": result["breakdown"],
                    "overlaps": result["overlaps"],
                    "current_balance": result["current_balance"],
                    "expected_balance": result["expected_balance"],
                })
            except Exception as exc:
                previews.append({
                    "leave_id": leave.id,
                    "employee": leave.user.get_full_name().strip() or leave.user.username,
                    "leave_type": leave.leave_type,
                    "current_status": leave.status,
                    "preview_status": preview_status,
                    "date_range": self._format_range(leave.from_date, leave.to_date),
                    "status": "conflict",
                    "warnings": [],
                    "conflicts": [f"Could not build conflict preview: {exc}"],
                    "effective_range": {},
                    "auto_added_dates": [],
                    "breakdown": {},
                    "overlaps": [],
                    "current_balance": {},
                    "expected_balance": {},
                })
        return previews

    def _workflow_action_key_from_action_name(self, action_name):
        if "approve" in action_name:
            return "approve"
        if "reject" in action_name:
            return "reject"
        if "delete" in action_name:
            return "delete"
        if "recalculate" in action_name:
            return "recalculate"
        return "sync"

    def single_leave_workflow_view(self, request, object_id, workflow_action):
        config = self.admin_workflow_configs.get(workflow_action)
        if not config:
            self.message_user(request, "Unknown admin workflow action.", level=messages.ERROR)
            return redirect("admin:App_leave_change", object_id)

        queryset = Leave.objects.filter(pk=object_id)
        if not queryset.exists():
            self.message_user(request, "Leave record not found.", level=messages.ERROR)
            return redirect("admin:App_leave_changelist")

        if request.method != "POST" or not request.POST.get("admin_workflow_confirm"):
            return self._render_leave_workflow_confirmation(
                request,
                queryset,
                config["title"],
                config["action_name"],
                needs_rejection_reason=config["needs_rejection_reason"],
                show_delivery_options=config["show_delivery_options"],
            )

        if request.POST.get("admin_workflow_skip"):
            result = admin_leave_workflow.log_workflow_skipped(
                [object_id],
                request.user,
                workflow_action,
            )
            self.message_user(request, result, level=messages.INFO)
            return redirect("admin:App_leave_change", object_id)

        reason = (request.POST.get("workflow_reason") or "").strip()
        if not reason:
            self.message_user(request, "Admin reason is required.", level=messages.ERROR)
            return redirect(request.path)

        leave_ids = [object_id]
        if workflow_action == "approve":
            results = admin_leave_workflow.approve_selected_leaves(
                leave_ids,
                request.user,
                reason,
                self._workflow_options_from_request(request),
            )
        elif workflow_action == "reject":
            rejection_reason = (request.POST.get("rejection_reason") or "").strip()
            if not rejection_reason:
                self.message_user(request, "Rejection reason is required.", level=messages.ERROR)
                return redirect(request.path)
            results = admin_leave_workflow.reject_selected_leaves(
                leave_ids,
                request.user,
                reason,
                rejection_reason,
                self._workflow_options_from_request(request),
            )
        elif workflow_action == "sync":
            results = admin_leave_workflow.sync_selected_leaves(
                leave_ids,
                request.user,
                reason,
                self._workflow_options_from_request(request),
            )
        elif workflow_action == "delete":
            results = admin_leave_workflow.delete_selected_leaves_with_workflow(
                leave_ids,
                request.user,
                reason,
                self._workflow_options_from_request(request),
            )
            self._message_workflow_results(request, results)
            return redirect("admin:App_leave_changelist")
        else:
            results = admin_leave_workflow.recalculate_balances_for_selected_leaves(
                leave_ids,
                request.user,
                reason,
            )

        self._message_workflow_results(request, results)
        return redirect("admin:App_leave_change", object_id)

    def _workflow_options_from_request(self, request):
        return {
            "notify_employee": bool(request.POST.get("notify_employee")),
            "notify_hr": bool(request.POST.get("notify_hr")),
            "record_email": bool(request.POST.get("record_email")),
            "employee_message": bool(request.POST.get("employee_message")),
            "employee_notification": bool(request.POST.get("employee_notification")),
            "hr_notification": bool(request.POST.get("hr_notification")),
        }

    def _selected_leave_ids_from_request(self, request, queryset):
        selected_ids = request.POST.getlist("_selected_action")
        if selected_ids:
            return selected_ids
        return list(queryset.values_list("pk", flat=True))

    def _message_workflow_results(self, request, results):
        for result in results:
            level = messages.WARNING if "failed" in result.lower() else messages.INFO
            self.message_user(request, result, level=level)

    @admin.action(description="Admin approve selected leaves with workflow")
    def admin_approve_selected_leaves(self, request, queryset):
        if not request.POST.get("admin_workflow_confirm"):
            return self._render_leave_workflow_confirmation(
                request,
                queryset,
                "Confirm admin leave approval workflow",
                "admin_approve_selected_leaves",
            )

        if request.POST.get("admin_workflow_skip"):
            result = admin_leave_workflow.log_workflow_skipped(
                self._selected_leave_ids_from_request(request, queryset),
                request.user,
                "approve",
            )
            self.message_user(request, result, level=messages.INFO)
            return None

        reason = (request.POST.get("workflow_reason") or "").strip()
        if not reason:
            self.message_user(request, "Admin reason is required.", level=messages.ERROR)
            return None

        results = admin_leave_workflow.approve_selected_leaves(
            self._selected_leave_ids_from_request(request, queryset),
            request.user,
            reason,
            self._workflow_options_from_request(request),
        )
        self._message_workflow_results(request, results)
        return None

    @admin.action(description="Admin reject selected leaves with workflow")
    def admin_reject_selected_leaves(self, request, queryset):
        if not request.POST.get("admin_workflow_confirm"):
            return self._render_leave_workflow_confirmation(
                request,
                queryset,
                "Confirm admin leave rejection workflow",
                "admin_reject_selected_leaves",
                needs_rejection_reason=True,
            )

        if request.POST.get("admin_workflow_skip"):
            result = admin_leave_workflow.log_workflow_skipped(
                self._selected_leave_ids_from_request(request, queryset),
                request.user,
                "reject",
            )
            self.message_user(request, result, level=messages.INFO)
            return None

        reason = (request.POST.get("workflow_reason") or "").strip()
        rejection_reason = (request.POST.get("rejection_reason") or "").strip()
        if not reason:
            self.message_user(request, "Admin reason is required.", level=messages.ERROR)
            return None
        if not rejection_reason:
            self.message_user(request, "Rejection reason is required.", level=messages.ERROR)
            return None

        results = admin_leave_workflow.reject_selected_leaves(
            self._selected_leave_ids_from_request(request, queryset),
            request.user,
            reason,
            rejection_reason,
            self._workflow_options_from_request(request),
        )
        self._message_workflow_results(request, results)
        return None

    @admin.action(description="Admin sync selected leaves and recalculate balance")
    def admin_sync_selected_leaves(self, request, queryset):
        if not request.POST.get("admin_workflow_confirm"):
            return self._render_leave_workflow_confirmation(
                request,
                queryset,
                "Confirm admin leave sync workflow",
                "admin_sync_selected_leaves",
            )

        if request.POST.get("admin_workflow_skip"):
            result = admin_leave_workflow.log_workflow_skipped(
                self._selected_leave_ids_from_request(request, queryset),
                request.user,
                "sync",
            )
            self.message_user(request, result, level=messages.INFO)
            return None

        reason = (request.POST.get("workflow_reason") or "").strip()
        if not reason:
            self.message_user(request, "Admin reason is required.", level=messages.ERROR)
            return None

        results = admin_leave_workflow.sync_selected_leaves(
            self._selected_leave_ids_from_request(request, queryset),
            request.user,
            reason,
            self._workflow_options_from_request(request),
        )
        self._message_workflow_results(request, results)
        return None

    @admin.action(description="Admin delete selected leaves with workflow")
    def admin_delete_selected_leaves_with_workflow(self, request, queryset):
        if not request.POST.get("admin_workflow_confirm"):
            return self._render_leave_workflow_confirmation(
                request,
                queryset,
                "Confirm admin leave delete workflow",
                "admin_delete_selected_leaves_with_workflow",
            )

        if request.POST.get("admin_workflow_skip"):
            result = admin_leave_workflow.log_workflow_skipped(
                self._selected_leave_ids_from_request(request, queryset),
                request.user,
                "delete",
            )
            self.message_user(request, result, level=messages.INFO)
            return None

        reason = (request.POST.get("workflow_reason") or "").strip()
        if not reason:
            self.message_user(request, "Admin reason is required.", level=messages.ERROR)
            return None

        results = admin_leave_workflow.delete_selected_leaves_with_workflow(
            self._selected_leave_ids_from_request(request, queryset),
            request.user,
            reason,
            self._workflow_options_from_request(request),
        )
        self._message_workflow_results(request, results)
        return None

    @admin.action(description="Admin recalculate balances for selected leave employees")
    def admin_recalculate_selected_leave_balances(self, request, queryset):
        if not request.POST.get("admin_workflow_confirm"):
            return self._render_leave_workflow_confirmation(
                request,
                queryset,
                "Confirm admin balance recalculation",
                "admin_recalculate_selected_leave_balances",
                show_delivery_options=False,
            )

        if request.POST.get("admin_workflow_skip"):
            result = admin_leave_workflow.log_workflow_skipped(
                self._selected_leave_ids_from_request(request, queryset),
                request.user,
                "recalculate",
            )
            self.message_user(request, result, level=messages.INFO)
            return None

        reason = (request.POST.get("workflow_reason") or "").strip()
        if not reason:
            self.message_user(request, "Admin reason is required.", level=messages.ERROR)
            return None

        results = admin_leave_workflow.recalculate_balances_for_selected_leaves(
            self._selected_leave_ids_from_request(request, queryset),
            request.user,
            reason,
        )
        self._message_workflow_results(request, results)
        return None








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


class AdminCommunicationRecipientField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        try:
            profile = obj.profile
        except Profile.DoesNotExist:
            profile = None

        employee_id = getattr(profile, "employee_id", "") if profile else ""
        phone = getattr(profile, "phone", "") if profile else ""
        full_name = obj.get_full_name().strip() or obj.username
        parts = [
            full_name,
            f"@{obj.username}",
            obj.role,
            employee_id,
            phone,
            obj.email,
        ]
        return " | ".join(str(part) for part in parts if part)


class AdminCommunicationComposeForm(forms.Form):
    MESSAGE_MODE_CHOICES = (
        ("", "Select"),
        ("DIRECT", "Direct message"),
        ("ANNOUNCEMENT", "Announcement"),
    )
    AUDIENCE_CHOICES = (
        ("EMPLOYEE", "All employees"),
        ("HR", "All HR"),
        ("Admin", "All admins"),
        ("EVERYONE", "Everyone"),
    )

    message_mode = forms.ChoiceField(choices=MESSAGE_MODE_CHOICES, required=False)
    audience = forms.MultipleChoiceField(
        choices=AUDIENCE_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={
            "size": "5",
            "style": "min-width: 320px; max-width: 100%;",
        }),
    )
    recipients = AdminCommunicationRecipientField(
        queryset=CustomUser.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            "size": "5",
            "style": "min-width: 320px; max-width: 100%;",
            "class": "admin-recipient-source",
        }),
        help_text="Used for direct messages only.",
    )
    title = forms.CharField(max_length=140, required=False)
    body = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), max_length=1500)
    change_reason = forms.CharField(
        label="Admin reason",
        widget=forms.Textarea(attrs={"rows": 3}),
        max_length=1000,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["recipients"].queryset = CustomUser.objects.filter(is_active=True).order_by("role", "username")

    def clean(self):
        cleaned_data = super().clean()
        mode = cleaned_data.get("message_mode")
        recipients = cleaned_data.get("recipients")
        audience = cleaned_data.get("audience")

        if not mode:
            self.add_error("message_mode", "Select a message mode.")

        if mode == "DIRECT" and not recipients:
            self.add_error("recipients", "Select at least one recipient for direct messages.")

        if mode == "ANNOUNCEMENT" and not audience:
            self.add_error("audience", "Select at least one announcement audience.")

        for field_name in ("title", "body"):
            value = cleaned_data.get(field_name) or ""
            if "<" in value or ">" in value:
                self.add_error(field_name, "HTML markup is not allowed.")

        return cleaned_data


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
@admin.register(AdminCommunicationCenter)
class AdminCommunicationCenterAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    change_list_template = "admin/admin_communication_center.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "feed/",
                self.admin_site.admin_view(self.admin_notifications_feed),
                name="App_admincommunicationcenter_feed",
            ),
            path(
                "seen/",
                self.admin_site.admin_view(self.admin_notifications_seen),
                name="App_admincommunicationcenter_seen",
            ),
            path(
                "read/",
                self.admin_site.admin_view(self.admin_notifications_read),
                name="App_admincommunicationcenter_read",
            ),
            path(
                "read-all/",
                self.admin_site.admin_view(self.admin_notifications_read_all),
                name="App_admincommunicationcenter_read_all",
            ),
            path(
                "message/<int:communication_id>/view-log/",
                self.admin_site.admin_view(self.log_message_detail_view),
                name="App_admincommunicationcenter_view_log",
            ),
        ]
        return custom_urls + urls

    def changelist_view(self, request, extra_context=None):
        if not request.user.is_superuser and getattr(request.user, "role", None) != "Admin":
            self.message_user(request, "Only admins can use the admin communication center.", level=messages.ERROR)
            return redirect("admin:index")

        if request.method == "POST":
            form = AdminCommunicationComposeForm(request.POST)
            if form.is_valid():
                created = self._send_admin_communication(request, form.cleaned_data)
                self.message_user(request, f"Created {created} communication record(s).", level=messages.SUCCESS)
                return redirect(request.path)
        else:
            form = AdminCommunicationComposeForm()

        inbox = self._admin_inbox_queryset(request.user)[:25]
        sent = Communication.objects.select_related("sender", "recipient").filter(sender=request.user).order_by("-created_at")[:25]
        announcements = Communication.objects.select_related("sender", "recipient").filter(message_type="ANNOUNCEMENT").order_by("-created_at")[:25]

        context = {
            **self.admin_site.each_context(request),
            "title": "Admin communication center",
            "opts": self.model._meta,
            "form": form,
            "inbox": inbox,
            "sent": sent,
            "announcements": announcements,
            "message_view_log_url_template": reverse("admin:App_admincommunicationcenter_view_log", args=[0]),
        }
        return TemplateResponse(request, self.change_list_template, context)

    def _admin_allowed_communications(self, user):
        return (
            Communication.objects.select_related("sender", "recipient")
            .filter(Q(recipient=user) | Q(message_type="ANNOUNCEMENT", audience_role="Admin"))
            .exclude(sender=user)
            .order_by("-created_at")
        )

    def _serialize_admin_communication(self, communication, read_ids, seen_ids):
        sender = communication.sender.get_full_name().strip() or communication.sender.username
        target = str(communication.recipient) if communication.recipient else (communication.audience_role or "-")
        return {
            "id": communication.id,
            "message_type": communication.message_type,
            "type_label": "Announcement" if communication.message_type == "ANNOUNCEMENT" else "Direct message",
            "title": communication.title or "Message",
            "sender": sender,
            "target": target,
            "created_at": localtime(communication.created_at).strftime("%b %d, %Y %I:%M %p"),
            "body_preview": (communication.body[:140] + "...") if len(communication.body) > 140 else communication.body,
            "body_full": communication.body,
            "is_read": communication.id in read_ids,
            "is_seen": communication.id in seen_ids,
        }

    def _admin_notification_payload(self, request, offset=0, limit=10):
        offset = max(0, min(int(offset or 0), 1000))
        limit = max(1, min(int(limit or 10), 10))
        queryset = self._admin_allowed_communications(request.user)
        total_available = queryset.count()
        communications = list(queryset[offset:offset + limit])
        ids = [communication.id for communication in communications]
        read_ids = set(CommunicationRead.objects.filter(user=request.user, communication_id__in=ids).values_list("communication_id", flat=True))
        seen_ids = set(CommunicationSeen.objects.filter(user=request.user, communication_id__in=ids).values_list("communication_id", flat=True))
        unread_count = queryset.exclude(read_receipts__user=request.user).count()
        unseen_count = sum(1 for communication in communications if communication.id not in seen_ids)
        return {
            "count": unread_count,
            "new_count": unseen_count,
            "items": [self._serialize_admin_communication(communication, read_ids, seen_ids) for communication in communications],
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total_available,
        }

    def admin_notifications_feed(self, request):
        if request.method != "GET":
            return JsonResponse({"error": "GET required."}, status=405)
        if not request.user.is_superuser and getattr(request.user, "role", None) != "Admin":
            return JsonResponse({"error": "Not allowed."}, status=403)
        try:
            offset = int(request.GET.get("offset", 0))
            limit = int(request.GET.get("limit", 10))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Invalid pagination."}, status=400)
        return JsonResponse(self._admin_notification_payload(request, offset=offset, limit=limit))

    def admin_notifications_seen(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)
        if not request.user.is_superuser and getattr(request.user, "role", None) != "Admin":
            return JsonResponse({"error": "Not allowed."}, status=403)

        communication_ids = list(self._admin_allowed_communications(request.user).values_list("id", flat=True)[:10])
        existing_seen_ids = set(CommunicationSeen.objects.filter(user=request.user, communication_id__in=communication_ids).values_list("communication_id", flat=True))
        newly_seen_ids = [communication_id for communication_id in communication_ids if communication_id not in existing_seen_ids]
        CommunicationSeen.objects.bulk_create(
            [CommunicationSeen(user=request.user, communication_id=communication_id) for communication_id in communication_ids],
            ignore_conflicts=True,
        )
        for communication in Communication.objects.filter(id__in=newly_seen_ids):
            _create_admin_audit_log(
                request,
                communication,
                {"admin_communication_seen": {"old": "unseen", "new": "seen"}},
                "New admin message arrived and was shown in admin bell.",
                action="SEEN",
            )
        return JsonResponse(self._admin_notification_payload(request))

    def admin_notifications_read(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)
        if not request.user.is_superuser and getattr(request.user, "role", None) != "Admin":
            return JsonResponse({"error": "Not allowed."}, status=403)

        communication_id = request.POST.get("communication_id")
        if not communication_id:
            return JsonResponse({"error": "Message id is required."}, status=400)
        if not str(communication_id).isdigit():
            return JsonResponse({"error": "Invalid message id."}, status=400)

        communication = self._admin_allowed_communications(request.user).filter(pk=communication_id).first()
        if not communication:
            return JsonResponse({"error": "Message not found."}, status=404)

        _, read_created = CommunicationRead.objects.get_or_create(user=request.user, communication=communication)
        CommunicationSeen.objects.get_or_create(user=request.user, communication=communication)
        if read_created:
            _create_admin_audit_log(
                request,
                communication,
                {
                    "admin_communication_read": {
                        "old": "unread",
                        "new": "read",
                    },
                    "admin_communication_detail": {
                        "old": None,
                        "new": {
                            "message_type": communication.message_type,
                            "title": communication.title or "",
                            "sender": str(communication.sender),
                            "recipient": str(communication.recipient) if communication.recipient else "",
                            "audience_role": communication.audience_role or "",
                            "created_at": _audit_value(communication.created_at),
                        },
                    },
                },
                "Opened admin bell message detail and marked it as read.",
                action="READ",
            )
        return JsonResponse(self._admin_notification_payload(request))

    def admin_notifications_read_all(self, request):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)
        if not request.user.is_superuser and getattr(request.user, "role", None) != "Admin":
            return JsonResponse({"error": "Not allowed."}, status=403)

        communication_ids = list(self._admin_allowed_communications(request.user).values_list("id", flat=True))
        existing_read_ids = set(CommunicationRead.objects.filter(user=request.user, communication_id__in=communication_ids).values_list("communication_id", flat=True))
        newly_read_ids = [communication_id for communication_id in communication_ids if communication_id not in existing_read_ids]
        CommunicationRead.objects.bulk_create(
            [CommunicationRead(user=request.user, communication_id=communication_id) for communication_id in communication_ids],
            ignore_conflicts=True,
        )
        CommunicationSeen.objects.bulk_create(
            [CommunicationSeen(user=request.user, communication_id=communication_id) for communication_id in communication_ids],
            ignore_conflicts=True,
        )
        first_communication = Communication.objects.filter(id__in=newly_read_ids).first()
        if first_communication:
            _create_admin_audit_log(
                request,
                first_communication,
                {
                    "admin_communication_mark_all_read": {
                        "old": f"{len(newly_read_ids)} unread",
                        "new": "read",
                    }
                },
                "Marked all admin bell messages as read.",
                action="READ",
            )
        return JsonResponse(self._admin_notification_payload(request))

    def log_message_detail_view(self, request, communication_id):
        if request.method != "POST":
            return JsonResponse({"error": "POST required."}, status=405)

        if not request.user.is_superuser and getattr(request.user, "role", None) != "Admin":
            return JsonResponse({"error": "Not allowed."}, status=403)

        communication = Communication.objects.select_related("sender", "recipient").filter(pk=communication_id).first()
        if not communication:
            return JsonResponse({"error": "Message not found."}, status=404)

        _create_admin_audit_log(
            request,
            communication,
            {
                "admin_communication_view": {
                    "old": None,
                    "new": {
                        "message_type": communication.message_type,
                        "title": communication.title or "",
                        "sender": str(communication.sender),
                        "recipient": str(communication.recipient) if communication.recipient else "",
                        "audience_role": communication.audience_role or "",
                        "created_at": _audit_value(communication.created_at),
                    },
                }
            },
            "Opened full message detail popup in admin communication center.",
            action="VIEW",
        )
        return JsonResponse({"success": True})

    def _admin_inbox_queryset(self, user):
        return (
            Communication.objects.select_related("sender", "recipient")
            .filter(Q(recipient=user) | Q(message_type="ANNOUNCEMENT", audience_role="Admin"))
            .exclude(sender=user)
            .order_by("-created_at")
        )

    def _send_admin_communication(self, request, cleaned_data):
        mode = cleaned_data["message_mode"]
        title = cleaned_data.get("title") or ""
        body = cleaned_data["body"]
        reason = cleaned_data["change_reason"]
        created_records = []

        if mode == "DIRECT":
            for recipient in cleaned_data["recipients"]:
                created_records.append(Communication.objects.create(
                    sender=request.user,
                    recipient=recipient,
                    message_type="DIRECT",
                    title=title,
                    body=body,
                ))
        else:
            selected_audiences = cleaned_data["audience"]
            audiences = []
            for audience in selected_audiences:
                if audience == "EVERYONE":
                    audiences.extend(["EMPLOYEE", "HR", "Admin"])
                else:
                    audiences.append(audience)
            audiences = list(dict.fromkeys(audiences))
            for audience_role in audiences:
                created_records.append(Communication.objects.create(
                    sender=request.user,
                    message_type="ANNOUNCEMENT",
                    audience_role=audience_role,
                    title=title,
                    body=body,
                ))

        for communication in created_records:
            _create_admin_audit_log(
                request,
                communication,
                {"admin_communication": {"old": None, "new": _snapshot_model_fields(communication, {"id"})}},
                reason,
                action="CREATE",
            )
        return len(created_records)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path("upload-csv/", self.upload_csv, name="companyholiday_upload_csv"),
            path(
                "impact/",
                self.admin_site.admin_view(self.holiday_impact_view),
                name="app_companyholiday_impact",
            ),
        ]
        return custom_urls + urls

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
            changed_dates = sorted({previous.date.isoformat(), obj.date.isoformat()})
            if previous.date != obj.date or previous.is_optional != obj.is_optional:
                request._holiday_impact_prompt = {
                    "mode": "changed",
                    "holiday": obj.name,
                    "old_date": previous.date.isoformat(),
                    "new_date": obj.date.isoformat(),
                    "changed_dates": changed_dates,
                    "change_reason": form.cleaned_data.get("change_reason") or "Holiday changed from Django admin.",
                }
        elif obj.pk:
            self._log_create(request, obj, form.cleaned_data.get("change_reason") or "Created from Django admin.")
            request._holiday_impact_prompt = {
                "mode": "created",
                "holiday": obj.name,
                "old_date": None,
                "new_date": obj.date.isoformat(),
                "changed_dates": [obj.date.isoformat()],
                "change_reason": form.cleaned_data.get("change_reason") or "Holiday created from Django admin.",
            }

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        prompt = getattr(request, "_holiday_impact_prompt", None)
        if prompt and ("_save" in request.POST or "_continue" in request.POST):
            request.session["holiday_impact_prompt"] = prompt
            return redirect(reverse("admin:app_companyholiday_impact"))
        return response

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue=post_url_continue)
        prompt = getattr(request, "_holiday_impact_prompt", None)
        if prompt and ("_save" in request.POST or "_continue" in request.POST):
            request.session["holiday_impact_prompt"] = prompt
            return redirect(reverse("admin:app_companyholiday_impact"))
        return response

    def delete_model(self, request, obj):
        prompt = {
            "mode": "deleted",
            "holiday": obj.name,
            "old_date": obj.date.isoformat(),
            "new_date": None,
            "changed_dates": [obj.date.isoformat()],
            "change_reason": (request.POST.get("delete_reason") or "").strip() or "Holiday deleted from Django admin.",
        }
        request._holiday_impact_prompt = prompt
        request.session["holiday_impact_prompt"] = prompt
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        holidays = list(queryset)
        if holidays:
            changed_dates = sorted({item.date.isoformat() for item in holidays})
            names = [item.name for item in holidays[:5]]
            extra_count = max(len(holidays) - len(names), 0)
            holiday_label = ", ".join(names)
            if extra_count:
                holiday_label = f"{holiday_label} and {extra_count} more"
            prompt = {
                "mode": "bulk_deleted",
                "holiday": holiday_label,
                "old_date": None,
                "new_date": None,
                "changed_dates": changed_dates,
                "change_reason": (request.POST.get("delete_reason") or "").strip() or "Holiday bulk deleted from Django admin.",
                "deleted_count": len(holidays),
            }
            request._holiday_impact_prompt = prompt
            request.session["holiday_impact_prompt"] = prompt
        super().delete_queryset(request, queryset)

    def response_delete(self, request, obj_display, obj_id):
        response = super().response_delete(request, obj_display, obj_id)
        prompt = getattr(request, "_holiday_impact_prompt", None) or request.session.get("holiday_impact_prompt")
        if prompt:
            request.session["holiday_impact_prompt"] = prompt
            return redirect(reverse("admin:app_companyholiday_impact"))
        return response

    def response_action(self, request, queryset):
        response = super().response_action(request, queryset)
        if request.session.get("holiday_impact_prompt"):
            return redirect(reverse("admin:app_companyholiday_impact"))
        return response

    def _format_range(self, start_date, end_date):
        if start_date == end_date:
            return start_date.strftime("%d %b %Y")
        return f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"

    def _holiday_dates_before_prompt(self, start_date, end_date, prompt):
        holidays = set(
            CompanyHoliday.objects.filter(date__range=(start_date, end_date)).values_list("date", flat=True)
        )
        changed_dates = {
            date.fromisoformat(item)
            for item in prompt.get("changed_dates", [])
            if item
        }
        mode = prompt.get("mode")

        if mode in {"created", "csv_import"}:
            holidays.difference_update(changed_dates)
        elif mode in {"deleted", "bulk_deleted"}:
            holidays.update(changed_dates)
        elif mode == "changed":
            old_date = date.fromisoformat(prompt["old_date"]) if prompt.get("old_date") else None
            new_date = date.fromisoformat(prompt["new_date"]) if prompt.get("new_date") else None
            if old_date:
                holidays.add(old_date)
            if new_date:
                holidays.discard(new_date)

        return holidays

    def _holiday_impact_preview(self, prompt=None):
        from App.services.leave_breakdown import calculate_leave_breakdown, calculate_leave_breakdown_for_leave, preview_user_full_day_leave_bridge_reconciliation

        prompt = prompt or {}
        changed_dates = {
            date.fromisoformat(item)
            for item in prompt.get("changed_dates", [])
            if item
        }
        today = timezone.localdate()
        leaves = (
            Leave.objects
            .select_related("user", "user__leavebalance")
            .filter(
                status__in=["Pending", "Approved"],
                leave_type__in=["Sick", "Earned", "Unpaid"],
                to_date__gte=today,
            )
            .order_by("user_id", "from_date", "id")
        )
        skipped = {
            "past": Leave.objects.filter(
                status__in=["Pending", "Approved"],
                leave_type__in=["Sick", "Earned", "Unpaid"],
                to_date__lt=today,
            ).count(),
            "admin_bypass": Leave.objects.filter(
                status__in=["Pending", "Approved"],
                leave_type__in=["Sick", "Earned", "Unpaid"],
                to_date__gte=today,
                admin_skip_wfh_bridge=True,
            ).count(),
        }
        rows = []
        risk_by_user = {}
        reconciled_ranges_by_user = {}

        for leave in leaves:
            requested_start = leave.requested_from_date or leave.from_date
            requested_end = leave.requested_to_date or leave.to_date
            if leave.user_id not in reconciled_ranges_by_user:
                reconciled_ranges_by_user[leave.user_id] = preview_user_full_day_leave_bridge_reconciliation(leave.user)

            if leave.admin_skip_wfh_bridge:
                proposed_from = leave.from_date
                proposed_to = leave.to_date
                auto_added_dates = []
            else:
                reconciled = reconciled_ranges_by_user[leave.user_id].get(leave.id, {})
                proposed_from = reconciled.get("from_date", leave.from_date)
                proposed_to = reconciled.get("to_date", leave.to_date)
                auto_added_dates = reconciled.get("auto_added_dates", [])
            current_days = float(calculate_leave_breakdown(
                leave.from_date,
                leave.to_date,
                requested_start_date=requested_start,
                requested_end_date=requested_end,
                company_holidays_override=self._holiday_dates_before_prompt(leave.from_date, leave.to_date, prompt),
            )["working_days"] or 0)
            proposed_days = float(calculate_leave_breakdown(
                proposed_from,
                proposed_to,
                requested_start_date=requested_start,
                requested_end_date=requested_end,
            )["working_days"] or 0)
            range_changed = leave.from_date != proposed_from or leave.to_date != proposed_to
            touches_changed_date = any(leave.from_date <= changed_date <= leave.to_date for changed_date in changed_dates)
            bridge_touches_changed_date = any(changed_date in auto_added_dates for changed_date in changed_dates)
            if not range_changed and not touches_changed_date and not bridge_touches_changed_date:
                continue

            employee_name = leave.user.get_full_name().strip() or leave.user.username
            balance = getattr(leave.user, "leavebalance", None)
            row = {
                "leave_id": leave.id,
                "employee": employee_name,
                "employee_id": leave.user_id,
                "status": leave.status,
                "leave_type": leave.leave_type,
                "deducted_from": leave.deducted_from,
                "current_range": self._format_range(leave.from_date, leave.to_date),
                "proposed_range": self._format_range(proposed_from, proposed_to),
                "proposed_from": proposed_from.isoformat(),
                "proposed_to": proposed_to.isoformat(),
                "bridge_dates": [item.strftime("%d %b %Y") for item in auto_added_dates],
                "changed_holiday_dates": [item.strftime("%d %b %Y") for item in sorted(changed_dates)],
                "current_days": current_days,
                "proposed_days": proposed_days,
                "range_changed": range_changed,
                "holiday_inside_range": touches_changed_date,
                "current_sick_remaining": round(float((balance.sick_total - balance.sick_used) if balance else 0), 2),
                "current_earned_remaining": round(float((balance.earned_total - balance.earned_used) if balance else 0), 2),
                "proposed_remaining": "-",
                "risk": "",
            }
            rows.append(row)

        affected_user_ids = {row["employee_id"] for row in rows}
        proposed_by_leave_id = {
            row["leave_id"]: (date.fromisoformat(row["proposed_from"]), date.fromisoformat(row["proposed_to"]))
            for row in rows
        }
        if affected_user_ids:
            active_leaves = (
                Leave.objects
                .select_related("user", "user__leavebalance")
                .filter(user_id__in=affected_user_ids, status__in=["Pending", "Approved"])
                .order_by("user_id", "from_date", "id")
            )
            projected = {}
            for leave in active_leaves:
                balance = getattr(leave.user, "leavebalance", None)
                user_state = projected.setdefault(
                    leave.user_id,
                    {
                        "employee": leave.user.get_full_name().strip() or leave.user.username,
                        "sick_total": float(balance.sick_total if balance else 0),
                        "earned_total": float(balance.earned_total if balance else 0),
                        "sick_used": 0.0,
                        "earned_used": 0.0,
                        "unpaid": 0.0,
                    },
                )
                if leave.id in proposed_by_leave_id:
                    proposed_from, proposed_to = proposed_by_leave_id[leave.id]
                    requested_start = leave.requested_from_date or leave.from_date
                    requested_end = leave.requested_to_date or leave.to_date
                    value = float(calculate_leave_breakdown(
                        proposed_from,
                        proposed_to,
                        requested_start_date=requested_start,
                        requested_end_date=requested_end,
                    )["working_days"] or 0)
                else:
                    value = float(calculate_leave_breakdown_for_leave(leave)["working_days"] or 0)

                if leave.leave_type == "Sick":
                    user_state["sick_used"] += value
                elif leave.leave_type == "Earned":
                    user_state["earned_used"] += value
                elif leave.leave_type == "Unpaid":
                    user_state["unpaid"] += value
                elif leave.leave_type in ["Short", "Half"]:
                    if leave.deducted_from == "Sick":
                        user_state["sick_used"] += value
                    elif leave.deducted_from == "Earned":
                        user_state["earned_used"] += value
                    elif leave.deducted_from == "Unpaid":
                        user_state["unpaid"] += value

            for row in rows:
                user_state = projected.get(row["employee_id"], {})
                sick_remaining = round(user_state.get("sick_total", 0) - user_state.get("sick_used", 0), 2)
                earned_remaining = round(user_state.get("earned_total", 0) - user_state.get("earned_used", 0), 2)
                if row["deducted_from"] == "Sick":
                    row["proposed_remaining"] = sick_remaining
                elif row["deducted_from"] == "Earned":
                    row["proposed_remaining"] = earned_remaining
                elif row["deducted_from"] == "Unpaid":
                    row["proposed_remaining"] = "Unpaid"
                risks = []
                if sick_remaining < 0:
                    risks.append("Sick below zero")
                if earned_remaining < 0:
                    risks.append("Earned below zero")
                row["risk"] = ", ".join(risks)
                if row["risk"]:
                    risk_by_user.setdefault(row["employee_id"], {"employee": row["employee"], "rows": []})["rows"].append(row)

        return {
            "rows": rows,
            "risk_groups": list(risk_by_user.values()),
            "risk_count": len(risk_by_user),
            "affected_employee_count": len({row["employee_id"] for row in rows}),
            "affected_leave_count": len(rows),
            "skipped": skipped,
        }

    def _holiday_impact_snapshot(self, prompt, preview):
        return {
            "prompt": {
                "mode": prompt.get("mode"),
                "holiday": prompt.get("holiday"),
                "old_date": prompt.get("old_date"),
                "new_date": prompt.get("new_date"),
                "changed_dates": sorted(prompt.get("changed_dates", [])),
                "created_count": prompt.get("created_count"),
                "skipped_count": prompt.get("skipped_count"),
            },
            "affected_employee_count": preview["affected_employee_count"],
            "affected_leave_count": preview["affected_leave_count"],
            "risk_count": preview["risk_count"],
            "skipped": preview["skipped"],
            "rows": [
                {
                    "leave_id": row["leave_id"],
                    "employee_id": row["employee_id"],
                    "status": row["status"],
                    "leave_type": row["leave_type"],
                    "deducted_from": row["deducted_from"],
                    "current_range": row["current_range"],
                    "proposed_from": row["proposed_from"],
                    "proposed_to": row["proposed_to"],
                    "current_days": row["current_days"],
                    "proposed_days": row["proposed_days"],
                    "range_changed": row["range_changed"],
                    "holiday_inside_range": row["holiday_inside_range"],
                    "proposed_remaining": row["proposed_remaining"],
                    "risk": row["risk"],
                }
                for row in sorted(preview["rows"], key=lambda item: item["leave_id"])
            ],
        }

    def _holiday_impact_snapshot_token(self, prompt, preview):
        return signing.dumps(
            self._holiday_impact_snapshot(prompt, preview),
            salt="admin-holiday-impact-preview",
        )

    def holiday_impact_view(self, request):
        prompt = request.session.get("holiday_impact_prompt", {})
        preview = self._holiday_impact_preview(prompt)

        if request.method == "POST":
            action = request.POST.get("holiday_action")
            reason = (request.POST.get("holiday_reason") or "").strip()
            has_risk = preview["risk_count"] > 0

            if action == "skip":
                _create_admin_audit_log(
                    request,
                    request.user,
                    {
                        "holiday_impact_recalculation": {
                            "old": "pending",
                            "new": "skipped",
                            "prompt": prompt,
                            "preview": {
                                "affected_leave_count": preview["affected_leave_count"],
                                "affected_employee_count": preview["affected_employee_count"],
                                "risk_count": preview["risk_count"],
                            },
                        }
                    },
                    reason or "Admin skipped holiday impact recalculation.",
                    action="SKIP",
                )
                request.session.pop("holiday_impact_prompt", None)
                self.message_user(request, "Holiday impact recalculation skipped and audited.", level=messages.INFO)
                return redirect("admin:App_companyholiday_changelist")

            if action == "apply":
                snapshot_token = request.POST.get("holiday_preview_snapshot") or ""
                try:
                    reviewed_snapshot = signing.loads(
                        snapshot_token,
                        salt="admin-holiday-impact-preview",
                        max_age=1800,
                    )
                except signing.BadSignature:
                    self.message_user(
                        request,
                        "Holiday impact preview expired or is invalid. Review the refreshed preview before applying.",
                        level=messages.ERROR,
                    )
                    return redirect(request.path)

                current_snapshot = self._holiday_impact_snapshot(prompt, preview)
                if reviewed_snapshot != current_snapshot:
                    self.message_user(
                        request,
                        "Holiday impact preview is stale because leave or holiday data changed. Review the refreshed preview before applying.",
                        level=messages.ERROR,
                    )
                    return redirect(request.path)

                if not reason:
                    self.message_user(request, "Admin reason is required before applying holiday impact recalculation.", level=messages.ERROR)
                    return redirect(request.path)
                if has_risk and request.POST.get("balance_risk_override") != "1":
                    self.message_user(request, "Balance risk override confirmation is required.", level=messages.ERROR)
                    return redirect(request.path)

                from App.services.admin_leave_workflow import recalculate_employee_balance
                from App.services.leave_breakdown import reconcile_user_full_day_leave_bridges

                affected_users = set()
                changed_rows = []
                preview_user_ids = {row["employee_id"] for row in preview["rows"]}
                with transaction.atomic():
                    users = list(get_user_model().objects.select_for_update().filter(id__in=preview_user_ids))
                    preview_rows_by_id = {row["leave_id"]: row for row in preview["rows"]}
                    for user in users:
                        before = {
                            leave.id: {
                                "employee": leave.user.get_full_name().strip() or leave.user.username,
                                "from_date": leave.from_date.isoformat(),
                                "to_date": leave.to_date.isoformat(),
                                "from_datetime": _audit_value(leave.from_datetime),
                                "to_datetime": _audit_value(leave.to_datetime),
                            }
                            for leave in Leave.objects.select_for_update().select_related("user").filter(
                                user=user,
                                status__in=["Pending", "Approved"],
                                leave_type__in=["Sick", "Earned", "Unpaid"],
                            )
                        }
                        changed_leave_ids = set(reconcile_user_full_day_leave_bridges(user))
                        row_leave_ids = set(
                            Leave.objects.filter(id__in=preview_rows_by_id.keys(), user=user).values_list("id", flat=True)
                        )
                        after_leaves = Leave.objects.select_related("user").filter(id__in=changed_leave_ids.union(row_leave_ids))
                        for leave in after_leaves:
                            old = before.get(leave.id, {})
                            preview_row = preview_rows_by_id.get(leave.id, {})
                            changed_rows.append({
                                "leave_id": leave.id,
                                "employee": old.get("employee") or leave.user.get_full_name().strip() or leave.user.username,
                                "old": old,
                                "new": {
                                    "from_date": leave.from_date.isoformat(),
                                    "to_date": leave.to_date.isoformat(),
                                    "from_datetime": _audit_value(leave.from_datetime),
                                    "to_datetime": _audit_value(leave.to_datetime),
                                    "working_days": preview_row.get("proposed_days"),
                                },
                            })
                        affected_users.add(user.id)
                    for user in users:
                        recalculate_employee_balance(user, request.user, reason, "Holiday schedule recalculation")

                _create_admin_audit_log(
                    request,
                    request.user,
                    {
                        "holiday_impact_recalculation": {
                            "old": "preview",
                            "new": "applied",
                            "prompt": prompt,
                            "balance_risk_override": has_risk,
                            "snapshot_verified": True,
                            "changed_rows": changed_rows,
                            "risk_count": preview["risk_count"],
                        }
                    },
                    reason,
                    action="APPLY",
                )
                request.session.pop("holiday_impact_prompt", None)
                self.message_user(request, f"Applied holiday impact recalculation to {len(changed_rows)} leave(s).", level=messages.SUCCESS)
                return redirect("admin:App_companyholiday_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": "Upcoming Holiday Impact Preview",
            "opts": self.model._meta,
            "prompt": prompt,
            "preview": preview,
            "preview_snapshot_token": self._holiday_impact_snapshot_token(prompt, preview),
            "risk_groups_json": preview["risk_groups"],
        }
        return TemplateResponse(request, "admin/holiday_impact.html", context)

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
                if created_rows:
                    request.session["holiday_impact_prompt"] = {
                        "mode": "csv_import",
                        "holiday": f"{created} holiday(s) imported",
                        "old_date": None,
                        "new_date": None,
                        "changed_dates": [item["date"] for item in created_rows],
                        "change_reason": change_reason,
                        "created_count": created,
                        "skipped_count": skipped,
                    }
                    return redirect(reverse("admin:app_companyholiday_impact"))
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

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "bridge-impact/",
                self.admin_site.admin_view(self.bridge_impact_view),
                name="app_workfromhomeday_bridge_impact_global",
            ),
            path(
                "<path:object_id>/bridge-impact/",
                self.admin_site.admin_view(self.bridge_impact_view),
                name="app_workfromhomeday_bridge_impact",
            ),
        ]
        return custom_urls + urls

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
            if previous.is_active != obj.is_active or previous.weekday != obj.weekday:
                request._wfh_bridge_impact_prompt = {
                    "object_id": obj.pk,
                    "change_reason": form.cleaned_data.get("change_reason") or "WFH setting changed from Django admin.",
                    "weekday": obj.get_weekday_display(),
                    "old_weekday": previous.get_weekday_display(),
                    "new_weekday": obj.get_weekday_display(),
                    "old_active": previous.is_active,
                    "new_active": obj.is_active,
                }
        elif obj.pk:
            self._log_create(request, obj, form.cleaned_data.get("change_reason") or "Created from Django admin.")
            request._wfh_bridge_impact_prompt = {
                "object_id": obj.pk,
                "change_reason": form.cleaned_data.get("change_reason") or "WFH setting created from Django admin.",
                "weekday": obj.get_weekday_display(),
                "old_active": None,
                "new_active": obj.is_active,
            }

    def delete_model(self, request, obj):
        prompt = {
            "mode": "deleted",
            "change_reason": (request.POST.get("delete_reason") or "").strip() or "WFH setting deleted from Django admin.",
            "weekday": obj.get_weekday_display(),
            "old_active": obj.is_active,
            "new_active": None,
        }
        request._wfh_bridge_impact_prompt = prompt
        request.session["wfh_bridge_impact_prompt"] = prompt
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        wfh_days = list(queryset)
        if wfh_days:
            weekday_labels = [item.get_weekday_display() for item in wfh_days]
            prompt = {
                "mode": "bulk_deleted",
                "change_reason": (request.POST.get("delete_reason") or "").strip() or "WFH settings bulk deleted from Django admin.",
                "weekday": ", ".join(weekday_labels[:5]) + (f" and {len(weekday_labels) - 5} more" if len(weekday_labels) > 5 else ""),
                "old_active": any(item.is_active for item in wfh_days),
                "new_active": None,
                "deleted_count": len(wfh_days),
            }
            request._wfh_bridge_impact_prompt = prompt
            request.session["wfh_bridge_impact_prompt"] = prompt
        super().delete_queryset(request, queryset)

    def response_change(self, request, obj):
        response = super().response_change(request, obj)
        prompt = getattr(request, "_wfh_bridge_impact_prompt", None)
        if prompt and ("_save" in request.POST or "_continue" in request.POST):
            request.session["wfh_bridge_impact_prompt"] = prompt
            return redirect(reverse("admin:app_workfromhomeday_bridge_impact", args=[obj.pk]))
        return response

    def response_add(self, request, obj, post_url_continue=None):
        response = super().response_add(request, obj, post_url_continue=post_url_continue)
        prompt = getattr(request, "_wfh_bridge_impact_prompt", None)
        if prompt and ("_save" in request.POST or "_continue" in request.POST):
            request.session["wfh_bridge_impact_prompt"] = prompt
            return redirect(reverse("admin:app_workfromhomeday_bridge_impact", args=[obj.pk]))
        return response

    def response_delete(self, request, obj_display, obj_id):
        response = super().response_delete(request, obj_display, obj_id)
        prompt = getattr(request, "_wfh_bridge_impact_prompt", None) or request.session.get("wfh_bridge_impact_prompt")
        if prompt:
            request.session["wfh_bridge_impact_prompt"] = prompt
            return redirect(reverse("admin:app_workfromhomeday_bridge_impact_global"))
        return response

    def response_action(self, request, queryset):
        response = super().response_action(request, queryset)
        if request.session.get("wfh_bridge_impact_prompt"):
            return redirect(reverse("admin:app_workfromhomeday_bridge_impact_global"))
        return response

    def _wfh_bridge_preview(self):
        from App.services.leave_breakdown import calculate_leave_breakdown, calculate_leave_breakdown_for_leave, preview_user_full_day_leave_bridge_reconciliation

        today = timezone.localdate()
        leaves = (
            Leave.objects
            .select_related("user", "user__leavebalance")
            .filter(
                status__in=["Pending", "Approved"],
                leave_type__in=["Sick", "Earned", "Unpaid"],
                to_date__gte=today,
                admin_skip_wfh_bridge=False,
            )
            .order_by("user_id", "from_date", "id")
        )
        skipped = {
            "past": Leave.objects.filter(
                status__in=["Pending", "Approved"],
                leave_type__in=["Sick", "Earned", "Unpaid"],
                to_date__lt=today,
            ).count(),
            "admin_bypass": Leave.objects.filter(
                status__in=["Pending", "Approved"],
                leave_type__in=["Sick", "Earned", "Unpaid"],
                to_date__gte=today,
                admin_skip_wfh_bridge=True,
            ).count(),
        }
        rows = []
        risk_by_user = {}
        balance_state = {}
        reconciled_ranges_by_user = {}

        for leave in leaves:
            requested_start = leave.requested_from_date or leave.from_date
            requested_end = leave.requested_to_date or leave.to_date
            if leave.user_id not in reconciled_ranges_by_user:
                reconciled_ranges_by_user[leave.user_id] = preview_user_full_day_leave_bridge_reconciliation(leave.user)
            reconciled = reconciled_ranges_by_user[leave.user_id].get(leave.id, {})
            proposed_from = reconciled.get("from_date", leave.from_date)
            proposed_to = reconciled.get("to_date", leave.to_date)
            if leave.from_date == proposed_from and leave.to_date == proposed_to:
                continue

            current_days = float(calculate_leave_breakdown_for_leave(leave)["working_days"] or 0)
            proposed_days = float(calculate_leave_breakdown(
                proposed_from,
                proposed_to,
                requested_start_date=requested_start,
                requested_end_date=requested_end,
            )["working_days"] or 0)
            delta = round(proposed_days - current_days, 2)
            balance = getattr(leave.user, "leavebalance", None)
            if leave.user_id not in balance_state:
                balance_state[leave.user_id] = {
                    "sick_remaining": float((balance.sick_total - balance.sick_used) if balance else 0),
                    "earned_remaining": float((balance.earned_total - balance.earned_used) if balance else 0),
                    "unpaid": float(balance.unpaid if balance else 0),
                }
            proposed_remaining = "-"
            risk_label = ""
            if leave.deducted_from == "Sick":
                balance_state[leave.user_id]["sick_remaining"] = round(balance_state[leave.user_id]["sick_remaining"] - delta, 2)
                proposed_remaining = balance_state[leave.user_id]["sick_remaining"]
                if proposed_remaining < 0:
                    risk_label = "Sick below zero"
            elif leave.deducted_from == "Earned":
                balance_state[leave.user_id]["earned_remaining"] = round(balance_state[leave.user_id]["earned_remaining"] - delta, 2)
                proposed_remaining = balance_state[leave.user_id]["earned_remaining"]
                if proposed_remaining < 0:
                    risk_label = "Earned below zero"
            elif leave.deducted_from == "Unpaid":
                balance_state[leave.user_id]["unpaid"] = round(balance_state[leave.user_id]["unpaid"] + delta, 2)
                proposed_remaining = "Unpaid"

            employee_name = leave.user.get_full_name().strip() or leave.user.username
            row = {
                "leave_id": leave.id,
                "employee": employee_name,
                "employee_id": leave.user_id,
                "status": leave.status,
                "leave_type": leave.leave_type,
                "deducted_from": leave.deducted_from,
                "current_range": self._format_range(leave.from_date, leave.to_date),
                "proposed_range": self._format_range(proposed_from, proposed_to),
                "proposed_from": proposed_from.isoformat(),
                "proposed_to": proposed_to.isoformat(),
                "bridge_dates": [item.strftime("%d %b %Y") for item in reconciled.get("auto_added_dates", [])],
                "current_days": current_days,
                "proposed_days": proposed_days,
                "delta": delta,
                "current_sick_remaining": round(float((balance.sick_total - balance.sick_used) if balance else 0), 2),
                "current_earned_remaining": round(float((balance.earned_total - balance.earned_used) if balance else 0), 2),
                "proposed_remaining": proposed_remaining,
                "risk": risk_label,
            }
            rows.append(row)
            if risk_label:
                risk_by_user.setdefault(leave.user_id, {"employee": employee_name, "rows": []})["rows"].append(row)

        return {
            "rows": rows,
            "risk_groups": list(risk_by_user.values()),
            "risk_count": len(risk_by_user),
            "affected_employee_count": len({row["employee_id"] for row in rows}),
            "affected_leave_count": len(rows),
            "skipped": skipped,
        }

    def _format_range(self, start_date, end_date):
        if start_date == end_date:
            return start_date.strftime("%d %b %Y")
        return f"{start_date.strftime('%d %b %Y')} to {end_date.strftime('%d %b %Y')}"

    def bridge_impact_view(self, request, object_id=None):
        wfh_day = get_object_or_404(WorkFromHomeDay, pk=object_id) if object_id else None
        prompt = request.session.get("wfh_bridge_impact_prompt", {})
        preview = self._wfh_bridge_preview()
        audit_target = wfh_day or request.user

        if request.method == "POST":
            action = request.POST.get("bridge_action")
            reason = (request.POST.get("bridge_reason") or "").strip()
            has_risk = preview["risk_count"] > 0

            if action == "skip":
                _create_admin_audit_log(
                    request,
                    audit_target,
                    {
                        "wfh_bridge_recalculation": {
                            "old": "pending",
                            "new": "skipped",
                            "preview": {
                                "affected_leave_count": preview["affected_leave_count"],
                                "affected_employee_count": preview["affected_employee_count"],
                                "risk_count": preview["risk_count"],
                            },
                        }
                    },
                    reason or "Admin skipped WFH bridge recalculation.",
                    action="SKIP",
                )
                request.session.pop("wfh_bridge_impact_prompt", None)
                self.message_user(request, "WFH bridge recalculation skipped and audited.", level=messages.INFO)
                return redirect("admin:App_workfromhomeday_changelist")

            if action == "apply":
                if not reason:
                    self.message_user(request, "Admin reason is required before applying WFH bridge recalculation.", level=messages.ERROR)
                    return redirect(request.path)
                if has_risk and request.POST.get("balance_risk_override") != "1":
                    self.message_user(request, "Balance risk override confirmation is required.", level=messages.ERROR)
                    return redirect(request.path)

                from App.services.admin_leave_workflow import recalculate_employee_balance
                from App.services.leave_breakdown import reconcile_user_full_day_leave_bridges

                affected_users = set()
                changed_rows = []
                preview_user_ids = {row["employee_id"] for row in preview["rows"]}
                with transaction.atomic():
                    users = list(get_user_model().objects.select_for_update().filter(id__in=preview_user_ids))
                    for user in users:
                        before = {
                            leave.id: {
                                "employee": leave.user.get_full_name().strip() or leave.user.username,
                                "from_date": leave.from_date.isoformat(),
                                "to_date": leave.to_date.isoformat(),
                                "from_datetime": _audit_value(leave.from_datetime),
                                "to_datetime": _audit_value(leave.to_datetime),
                            }
                            for leave in Leave.objects.select_for_update().select_related("user").filter(
                                user=user,
                                status__in=["Pending", "Approved"],
                                leave_type__in=["Sick", "Earned", "Unpaid"],
                                admin_skip_wfh_bridge=False,
                            )
                        }
                        changed_leave_ids = reconcile_user_full_day_leave_bridges(user)
                        after_leaves = Leave.objects.select_related("user").filter(id__in=changed_leave_ids)
                        for leave in after_leaves:
                            old = before.get(leave.id, {})
                            changed_rows.append({
                                "leave_id": leave.id,
                                "employee": old.get("employee") or leave.user.get_full_name().strip() or leave.user.username,
                                "old": old,
                                "new": {
                                    "from_date": leave.from_date.isoformat(),
                                    "to_date": leave.to_date.isoformat(),
                                    "from_datetime": _audit_value(leave.from_datetime),
                                    "to_datetime": _audit_value(leave.to_datetime),
                                },
                            })
                        affected_users.add(user.id)
                    for user in users:
                        recalculate_employee_balance(user, request.user, reason, "WFH bridge schedule recalculation")

                _create_admin_audit_log(
                    request,
                    audit_target,
                    {
                        "wfh_bridge_recalculation": {
                            "old": "preview",
                            "new": "applied",
                            "balance_risk_override": has_risk,
                            "changed_rows": changed_rows,
                            "risk_count": preview["risk_count"],
                        }
                    },
                    reason,
                    action="APPLY",
                )
                request.session.pop("wfh_bridge_impact_prompt", None)
                self.message_user(request, f"Applied WFH bridge recalculation to {len(changed_rows)} leave(s).", level=messages.SUCCESS)
                return redirect("admin:App_workfromhomeday_changelist")

        context = {
            **self.admin_site.each_context(request),
            "title": "Upcoming WFH Bridge Impact Preview",
            "opts": self.model._meta,
            "wfh_day": wfh_day,
            "prompt": prompt,
            "preview": preview,
            "risk_groups_json": preview["risk_groups"],
        }
        return TemplateResponse(request, "admin/wfh_bridge_impact.html", context)


class BaseAdminAuditLogAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    model_label_filter = None
    model_label_filters = None
    action_filter = None
    list_display = ("model_label", "object_repr", "action_label", "change_summary", "updated_by", "changed_at", "reason")
    list_filter = ("model_label", "action", "updated_by", "changed_at")
    search_fields = ("model_label", "object_repr", "updated_by__username", "reason")
    readonly_fields = ("model_label", "object_id", "object_repr", "action", "updated_by", "changed_at", "reason", "changes")
    action_labels = {
        "CREATE": "Record created",
        "UPDATE": "Record updated",
        "DELETE": "Record deleted",
        "IMPORT": "CSV import",
        "APPLY": "Recalculation applied",
        "SKIP": "Recalculation skipped",
        "VIEW": "Record viewed",
        "READ": "Marked as read",
        "SEEN": "Marked as seen",
        "ADMIN_APPROVE": "Leave approved by admin",
        "ADMIN_REJECT": "Leave rejected by admin",
        "ADMIN_SYNC": "Leave synced by admin",
        "ADMIN_DELETE_WF": "Leave deleted through workflow",
        "ADMIN_PREVIEW": "Leave preview reviewed",
        "ADMIN_WORKFLOW_SKIPPED": "Workflow skipped by admin",
    }
    change_summary_labels = {
        "created_record": "Record created",
        "deleted_record": "Record deleted",
        "archive_pdf": "Archive PDF",
        "year_end_carry_forward": "Year-end carry forward",
        "admin_communication": "Admin communication sent",
        "admin_communication_view": "Admin communication viewed",
        "admin_communication_seen": "Admin communication seen",
        "admin_communication_read": "Admin communication read",
        "admin_communication_mark_all_read": "Admin communication mark all read",
        "admin_conflict_preview": "Leave conflict/impact preview",
        "admin_leave_workflow_skipped": "Admin leave workflow skipped",
        "holiday_impact_recalculation": "Holiday impact recalculation",
        "holiday_csv_upload_summary": "Holiday CSV upload summary",
        "wfh_bridge_recalculation": "WFH bridge recalculation",
        "csv_upload": "CSV upload row created",
        "backup_restore": "Backup restore",
        "maintenance_mode": "Maintenance mode",
    }

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if self.model_label_filter:
            return queryset.filter(model_label=self.model_label_filter)
        if self.model_label_filters:
            queryset = queryset.filter(model_label__in=self.model_label_filters)
        if self.action_filter:
            queryset = queryset.filter(action=self.action_filter)
        return queryset

    @admin.display(description="Action", ordering="action")
    def action_label(self, obj):
        return self.action_labels.get(obj.action, obj.action or "-")

    @admin.display(description="Summary")
    def change_summary(self, obj):
        if not obj.changes:
            return "-"
        labels = [
            self.change_summary_labels.get(key, key.replace("_", " ").title())
            for key in obj.changes.keys()
        ]
        return ", ".join(labels)


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

ADMIN_COMMUNICATION_AUDIT_LABELS = (
    "App.Communication",
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
@admin.register(AdminCommunicationAudit)
class AdminCommunicationAuditAdmin(BaseAdminAuditLogAdmin):
    model_label_filters = ADMIN_COMMUNICATION_AUDIT_LABELS

    def get_queryset(self, request):
        return super().get_queryset(request).filter(
            Q(changes__has_key="admin_communication")
            | Q(changes__has_key="admin_communication_view")
            | Q(changes__has_key="admin_communication_seen")
            | Q(changes__has_key="admin_communication_read")
            | Q(changes__has_key="admin_communication_mark_all_read")
        )


@login_required
@never_cache
@admin.register(EmailDeliveryLog)
class EmailDeliveryLogAdmin(ReadOnlyAuditAdminMixin, admin.ModelAdmin):
    list_display = (
        "created_at",
        "email_type",
        "recipient",
        "status",
        "subject",
        "related_user",
        "related_leave",
        "triggered_by",
        "short_error",
    )
    list_filter = ("status", "email_type", "created_at")
    search_fields = (
        "recipient",
        "subject",
        "from_email",
        "error_message",
        "related_user__username",
        "related_user__email",
        "triggered_by__username",
    )
    readonly_fields = (
        "created_at",
        "email_type",
        "subject",
        "from_email",
        "recipient",
        "status",
        "error_message",
        "related_user",
        "related_leave",
        "triggered_by",
        "metadata",
    )
    date_hierarchy = "created_at"
    ordering = ("-created_at", "-id")

    @admin.display(description="Error")
    def short_error(self, obj):
        if not obj.error_message:
            return "-"
        return obj.error_message[:80] + ("..." if len(obj.error_message) > 80 else "")


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
    "AdminCommunicationCenter",
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
    "AdminCommunicationAudit",
    "EmployeeCommunicationAudit",
    "HRCommunicationAudit",
    "EmployeeCommunicationReadSeenAudit",
    "HRCommunicationReadSeenAudit",
    "EmployeeLeaveNotificationReadSeenAudit",
    "HRLeaveNotificationReadSeenAudit",
}

EMAIL_DELIVERY_OBJECT_NAMES = {
    "EmailDeliveryLog",
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
    email_delivery_models = []
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
            elif model.get("object_name") in EMAIL_DELIVERY_OBJECT_NAMES:
                email_delivery_models.append(model)
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
        if email_delivery_models:
            insert_at += 1
        grouped_app_list.insert(insert_at, {
            "name": "Logs",
            "app_label": "logs",
            "app_url": "",
            "has_module_perms": True,
            "models": log_viewer_models,
        })

    if email_delivery_models:
        insert_at = 0
        if audit_models:
            insert_at += 1
        if communication_notification_models:
            insert_at += 1
        if communication_notification_audit_models:
            insert_at += 1
        grouped_app_list.insert(insert_at, {
            "name": "Email Delivery Center",
            "app_label": "email_delivery_center",
            "app_url": "",
            "has_module_perms": True,
            "models": email_delivery_models,
        })

    if backup_management_models:
        insert_at = 0
        if audit_models:
            insert_at += 1
        if communication_notification_models:
            insert_at += 1
        if communication_notification_audit_models:
            insert_at += 1
        if email_delivery_models:
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
