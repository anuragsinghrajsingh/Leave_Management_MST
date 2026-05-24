import csv
import json
import os
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, time, timedelta
from io import StringIO
from pathlib import Path


def _setup_django_for_direct_run():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


if __name__ == "__main__":
    _setup_django_for_direct_run()

from django.contrib.auth import get_user_model
from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from App.models import (
    AdminAuditLog,
    Communication,
    CommunicationRead,
    CommunicationSeen,
    CompanyHoliday,
    EmailDeliveryLog,
    Leave,
    LeaveBalance,
    LeaveBalanceAudit,
    LeaveNotificationRead,
    LeaveNotificationSeen,
    WorkFromHomeDay,
    YearEndCarryForwardRun,
)
from App.services.leave_breakdown import calculate_leave_breakdown_for_leave


REPORT_TYPES = (
    ("employee_master", "Employee master report"),
    ("leave_request", "Leave request report"),
    ("leave_balance", "Leave balance report"),
    ("leave_balance_audit", "Leave balance audit report"),
    ("admin_audit", "Admin audit report"),
    ("delete_audit", "Delete audit report"),
    ("communication", "Communication report"),
    ("communication_read_seen", "Communication read/seen report"),
    ("leave_notification_read_seen", "Leave notification read/seen report"),
    ("email_delivery", "Email delivery report"),
    ("holiday", "Holiday report"),
    ("wfh_rules", "WFH rules report"),
    ("year_end", "Year-end carry-forward report"),
    ("service_audit", "Backup/restore/service audit report"),
    ("system_health_snapshot", "System health snapshot report"),
    ("hr_summary", "HR summary report"),
)

PERIOD_TYPES = (
    ("custom", "Custom date range"),
    ("monthly", "Monthly"),
    ("quarterly", "Quarterly"),
    ("six_month", "Six-month"),
    ("yearly", "Yearly"),
)

EXPORT_FORMATS = (
    ("csv", "CSV"),
    ("pdf", "PDF"),
)

COLUMN_LABELS = {
    "user_id": "User ID",
    "username": "Username",
    "full_name": "Full Name",
    "email": "Email",
    "role": "Role",
    "active": "Active",
    "staff": "Staff",
    "superuser": "Superuser",
    "employee_id": "Employee ID",
    "department": "Department",
    "phone": "Phone",
    "joining_date": "Joining Date",
    "leave_id": "Leave ID",
    "employee": "Employee",
    "leave_type": "Leave Type",
    "status": "Status",
    "requested_from": "Requested From",
    "requested_to": "Requested To",
    "saved_from": "Saved From",
    "saved_to": "Saved To",
    "from_datetime": "From Date/Time",
    "to_datetime": "To Date/Time",
    "reason": "Reason",
    "rejection_reason": "Rejection Reason",
    "deducted_from": "Deducted From",
    "reviewed_by": "Reviewed By",
    "applied_at": "Applied At",
    "updated_at": "Updated At",
    "approved_at": "Approved At",
    "rejected_at": "Rejected At",
    "working_days": "Working Days",
    "section": "Section",
    "period_type": "Period Type",
    "period_start": "Period Start",
    "period_end": "Period End",
    "total_employees": "Total Employees",
    "active_employees": "Active Employees",
    "inactive_employees": "Inactive Employees",
    "employees_included": "Employees Included",
    "total_leave_requests": "Total Leave Requests",
    "approved_requests": "Approved Requests",
    "rejected_requests": "Rejected Requests",
    "pending_requests": "Pending Requests",
    "approval_rate": "Approval Rate %",
    "rejection_rate": "Rejection Rate %",
    "pending_rate": "Pending Rate %",
    "average_requests_per_employee": "Average Requests Per Employee",
    "average_approved_leave_days_per_employee": "Average Approved Leave Days Per Employee",
    "total_working_days_in_period": "Total Working Days In Period",
    "total_holidays_in_period": "Total Holidays In Period",
    "wfh_weekdays_active": "Active WFH Weekdays",
}


def column_label(key):
    return COLUMN_LABELS.get(key, key.replace("_", " ").title())


def build_report_export(filters, actor=None):
    report_type = filters["report_type"]
    rows = _build_rows(report_type, filters)
    title = dict(REPORT_TYPES).get(report_type, report_type)
    extension = filters["export_format"]
    timestamp = timezone.localtime(timezone.now()).strftime("%Y%m%d-%H%M%S")
    filename = f"{report_type}_{timestamp}.{extension}"

    if extension == "pdf":
        return {
            "filename": filename,
            "content_type": "application/pdf",
            "content": _rows_to_pdf(title, rows, filters, actor),
            "row_count": len(rows),
            "title": title,
        }

    return {
        "filename": filename,
        "content_type": "text/csv",
        "content": _rows_to_csv(rows),
        "row_count": len(rows),
        "title": title,
    }


def get_report_row_count(filters):
    return len(_build_rows(filters["report_type"], filters))


def describe_export_filters(filters):
    safe = dict(filters)
    return {
        key: str(value)
        for key, value in safe.items()
        if value not in ("", None, [], {})
    }


def describe_period(filters):
    start, end = _period_range(filters)
    period_type = filters.get("period_type") or "custom"
    year = filters.get("year") or (start.year if start else timezone.localdate().year)
    if period_type == "monthly":
        return f"Monthly: {date(int(year), int(filters.get('month') or timezone.localdate().month), 1).strftime('%B %Y')}"
    if period_type == "quarterly":
        return f"Quarterly: Q{filters.get('quarter') or 1} {year}"
    if period_type == "six_month":
        half_label = "Jan-Jun" if (filters.get("half_year") or "first") == "first" else "Jul-Dec"
        return f"Six-month: {half_label} {year}"
    if period_type == "yearly":
        return f"Yearly: {year}"
    if start and end:
        return f"Custom: {start.strftime('%d %b %Y')} - {end.strftime('%d %b %Y')}"
    if start:
        return f"Custom: From {start.strftime('%d %b %Y')}"
    if end:
        return f"Custom: Until {end.strftime('%d %b %Y')}"
    return "Custom: All available dates"


def _period_range(filters):
    today = timezone.localdate()
    year = int(filters.get("year") or today.year)
    period_type = filters.get("period_type") or "custom"

    if period_type == "monthly":
        month = int(filters.get("month") or today.month)
        start = date(year, month, 1)
        end = date(year + (month == 12), 1 if month == 12 else month + 1, 1) - timedelta(days=1)
        return start, end

    if period_type == "quarterly":
        quarter = int(filters.get("quarter") or 1)
        start_month = ((quarter - 1) * 3) + 1
        start = date(year, start_month, 1)
        end = date(year, start_month + 3, 1) - timedelta(days=1) if start_month < 10 else date(year, 12, 31)
        return start, end

    if period_type == "six_month":
        half = filters.get("half_year") or "first"
        start = date(year, 1, 1) if half == "first" else date(year, 7, 1)
        end = date(year, 6, 30) if half == "first" else date(year, 12, 31)
        return start, end

    if period_type == "yearly":
        return date(year, 1, 1), date(year, 12, 31)

    return filters.get("date_from"), filters.get("date_to")


def _date_time_bounds(filters):
    start, end = _period_range(filters)
    start_dt = timezone.make_aware(datetime.combine(start, time.min)) if start else None
    end_dt = timezone.make_aware(datetime.combine(end, time.max)) if end else None
    return start_dt, end_dt


def _users(filters):
    User = get_user_model()
    qs = User.objects.select_related("profile").all()
    if filters.get("employee"):
        qs = qs.filter(pk=filters["employee"].pk)
    if filters.get("role"):
        qs = qs.filter(role=filters["role"])
    if filters.get("active_status") == "active":
        qs = qs.filter(is_active=True)
    elif filters.get("active_status") == "inactive":
        qs = qs.filter(is_active=False)
    if filters.get("department"):
        qs = qs.filter(profile__department__icontains=filters["department"])
    return qs.order_by("username", "id")


def _leaves(filters):
    start, end = _period_range(filters)
    qs = Leave.objects.select_related("user", "user__profile", "reviewed_by").all()
    if start:
        qs = qs.filter(to_date__gte=start)
    if end:
        qs = qs.filter(from_date__lte=end)
    if filters.get("employee"):
        qs = qs.filter(user=filters["employee"])
    if filters.get("department"):
        qs = qs.filter(user__profile__department__icontains=filters["department"])
    if filters.get("leave_status"):
        qs = qs.filter(status=filters["leave_status"])
    if filters.get("leave_type"):
        qs = qs.filter(leave_type=filters["leave_type"])
    if filters.get("deducted_from"):
        qs = qs.filter(deducted_from=filters["deducted_from"])
    if filters.get("reviewed_by"):
        qs = qs.filter(reviewed_by=filters["reviewed_by"])
    return qs.order_by("-created_at", "-id")


def _build_rows(report_type, filters):
    builders = {
        "employee_master": _employee_master_rows,
        "leave_request": _leave_request_rows,
        "leave_balance": _leave_balance_rows,
        "leave_balance_audit": _leave_balance_audit_rows,
        "admin_audit": _admin_audit_rows,
        "delete_audit": _delete_audit_rows,
        "communication": _communication_rows,
        "communication_read_seen": _communication_read_seen_rows,
        "leave_notification_read_seen": _leave_notification_read_seen_rows,
        "email_delivery": _email_delivery_rows,
        "holiday": _holiday_rows,
        "wfh_rules": _wfh_rows,
        "year_end": _year_end_rows,
        "service_audit": _service_audit_rows,
        "system_health_snapshot": _system_health_rows,
        "hr_summary": _hr_summary_rows,
    }
    return builders[report_type](filters)


def _profile_value(user, attr):
    profile = getattr(user, "profile", None)
    return getattr(profile, attr, "") if profile else ""


def _name(user):
    if not user:
        return ""
    return user.get_full_name().strip() or user.username


def _json(value):
    return json.dumps(value or {}, default=str, ensure_ascii=False)


def _employee_master_rows(filters):
    rows = []
    for user in _users(filters):
        rows.append({
            "user_id": user.id,
            "username": user.username,
            "full_name": _name(user),
            "email": user.email,
            "role": user.role,
            "active": user.is_active,
            "staff": user.is_staff,
            "superuser": user.is_superuser,
            "employee_id": _profile_value(user, "employee_id"),
            "department": _profile_value(user, "department"),
            "phone": _profile_value(user, "phone"),
            "joining_date": _profile_value(user, "date_of_joining"),
        })
    return rows


def _leave_request_rows(filters):
    rows = []
    for leave in _leaves(filters):
        rows.append({
            "leave_id": leave.id,
            "employee": _name(leave.user),
            "employee_id": _profile_value(leave.user, "employee_id"),
            "department": _profile_value(leave.user, "department"),
            "leave_type": leave.leave_type,
            "status": leave.status,
            "requested_from": leave.requested_from_date,
            "requested_to": leave.requested_to_date,
            "saved_from": leave.from_date,
            "saved_to": leave.to_date,
            "from_datetime": leave.from_datetime,
            "to_datetime": leave.to_datetime,
            "reason": leave.reason,
            "rejection_reason": leave.rejection_reason or "",
            "deducted_from": leave.deducted_from,
            "reviewed_by": _name(leave.reviewed_by),
            "applied_at": leave.created_at,
            "updated_at": leave.updated_at,
            "approved_at": leave.approved_at,
            "rejected_at": leave.rejected_at,
            "working_days": _leave_value(leave),
        })
    return rows


def _leave_value(leave):
    if leave.leave_type == "Short":
        return 0.25
    if leave.leave_type == "Half":
        return 0.5
    try:
        return calculate_leave_breakdown_for_leave(leave)["working_days"]
    except Exception:
        return ""


def _leave_balance_rows(filters):
    qs = LeaveBalance.objects.select_related("user", "user__profile")
    if filters.get("employee"):
        qs = qs.filter(user=filters["employee"])
    if filters.get("department"):
        qs = qs.filter(user__profile__department__icontains=filters["department"])
    rows = []
    for balance in qs.order_by("user__username"):
        rows.append({
            "employee": _name(balance.user),
            "employee_id": _profile_value(balance.user, "employee_id"),
            "department": _profile_value(balance.user, "department"),
            "sick_total": balance.sick_total,
            "sick_used": balance.sick_used,
            "sick_remaining": balance.sick_total - balance.sick_used,
            "earned_total": balance.earned_total,
            "earned_used": balance.earned_used,
            "earned_remaining": balance.earned_total - balance.earned_used,
            "unpaid": balance.unpaid,
            "total_balance": balance.total_leave_balance,
            "total_remaining": balance.total_leave_remaining,
            "last_year_end_processed": balance.last_year_end_processed,
        })
    return rows


def _leave_balance_audit_rows(filters):
    start_dt, end_dt = _date_time_bounds(filters)
    qs = LeaveBalanceAudit.objects.select_related("employee", "employee__profile", "updated_by")
    if start_dt:
        qs = qs.filter(changed_at__gte=start_dt)
    if end_dt:
        qs = qs.filter(changed_at__lte=end_dt)
    if filters.get("employee"):
        qs = qs.filter(employee=filters["employee"])
    rows = []
    for audit in qs.order_by("-changed_at", "-id"):
        rows.append({
            "employee": _name(audit.employee),
            "employee_id": _profile_value(audit.employee, "employee_id"),
            "department": _profile_value(audit.employee, "department"),
            "changed_by": _name(audit.updated_by),
            "changed_at": audit.changed_at,
            "reason": audit.reason,
            "changes": _json(audit.changes),
        })
    return rows


def _admin_audit_queryset(filters):
    start_dt, end_dt = _date_time_bounds(filters)
    qs = AdminAuditLog.objects.select_related("updated_by")
    if start_dt:
        qs = qs.filter(changed_at__gte=start_dt)
    if end_dt:
        qs = qs.filter(changed_at__lte=end_dt)
    if filters.get("admin_action"):
        qs = qs.filter(action__icontains=filters["admin_action"])
    return qs.order_by("-changed_at", "-id")


def _admin_audit_rows(filters):
    return [{
        "model": audit.model_label,
        "object_id": audit.object_id,
        "object": audit.object_repr,
        "action": audit.action,
        "changed_by": _name(audit.updated_by),
        "changed_at": audit.changed_at,
        "reason": audit.reason,
        "changes": _json(audit.changes),
    } for audit in _admin_audit_queryset(filters)]


def _delete_audit_rows(filters):
    return [{
        "deleted_model": audit.model_label,
        "deleted_object_id": audit.object_id,
        "deleted_object": audit.object_repr,
        "deleted_by": _name(audit.updated_by),
        "deleted_at": audit.changed_at,
        "reason": audit.reason,
        "snapshot": _json(audit.changes),
    } for audit in _admin_audit_queryset(filters).filter(action__icontains="DELETE")]


def _communication_rows(filters):
    start_dt, end_dt = _date_time_bounds(filters)
    qs = Communication.objects.select_related("sender", "recipient")
    if start_dt:
        qs = qs.filter(created_at__gte=start_dt)
    if end_dt:
        qs = qs.filter(created_at__lte=end_dt)
    if filters.get("role"):
        qs = qs.filter(Q(audience_role=filters["role"]) | Q(recipient__role=filters["role"]))
    rows = []
    for item in qs.order_by("-created_at", "-id"):
        rows.append({
            "message_id": item.id,
            "message_type": item.message_type,
            "sender": _name(item.sender),
            "recipient": _name(item.recipient),
            "audience_role": item.audience_role or "",
            "title": item.title,
            "body": item.body,
            "created_at": item.created_at,
        })
    return rows


def _communication_read_seen_rows(filters):
    start_dt, end_dt = _date_time_bounds(filters)
    read_qs = CommunicationRead.objects.select_related("user", "communication")
    seen_qs = CommunicationSeen.objects.select_related("user", "communication")
    if start_dt:
        read_qs = read_qs.filter(read_at__gte=start_dt)
        seen_qs = seen_qs.filter(seen_at__gte=start_dt)
    if end_dt:
        read_qs = read_qs.filter(read_at__lte=end_dt)
        seen_qs = seen_qs.filter(seen_at__lte=end_dt)
    rows = []
    for item in read_qs.order_by("-read_at", "-id"):
        rows.append({"event": "read", "user": _name(item.user), "communication_id": item.communication_id, "title": item.communication.title, "time": item.read_at})
    for item in seen_qs.order_by("-seen_at", "-id"):
        rows.append({"event": "seen", "user": _name(item.user), "communication_id": item.communication_id, "title": item.communication.title, "time": item.seen_at})
    return sorted(rows, key=lambda row: str(row["time"]), reverse=True)


def _leave_notification_read_seen_rows(filters):
    start_dt, end_dt = _date_time_bounds(filters)
    read_qs = LeaveNotificationRead.objects.select_related("user", "leave", "leave__user")
    seen_qs = LeaveNotificationSeen.objects.select_related("user", "leave", "leave__user")
    if start_dt:
        read_qs = read_qs.filter(read_at__gte=start_dt)
        seen_qs = seen_qs.filter(seen_at__gte=start_dt)
    if end_dt:
        read_qs = read_qs.filter(read_at__lte=end_dt)
        seen_qs = seen_qs.filter(seen_at__lte=end_dt)
    rows = []
    for item in read_qs.order_by("-read_at", "-id"):
        rows.append({"event": "read", "user": _name(item.user), "leave_id": item.leave_id, "leave_employee": _name(item.leave.user), "leave_type": item.leave.leave_type, "status": item.leave.status, "time": item.read_at})
    for item in seen_qs.order_by("-seen_at", "-id"):
        rows.append({"event": "seen", "user": _name(item.user), "leave_id": item.leave_id, "leave_employee": _name(item.leave.user), "leave_type": item.leave.leave_type, "status": item.leave.status, "time": item.seen_at})
    return sorted(rows, key=lambda row: str(row["time"]), reverse=True)


def _email_delivery_rows(filters):
    start_dt, end_dt = _date_time_bounds(filters)
    qs = EmailDeliveryLog.objects.select_related("related_user", "related_leave", "triggered_by")
    if start_dt:
        qs = qs.filter(created_at__gte=start_dt)
    if end_dt:
        qs = qs.filter(created_at__lte=end_dt)
    if filters.get("email_status"):
        qs = qs.filter(status=filters["email_status"])
    rows = []
    for item in qs.order_by("-created_at", "-id"):
        rows.append({
            "email_type": item.email_type,
            "subject": item.subject,
            "from_email": item.from_email,
            "recipient": item.recipient,
            "status": item.status,
            "related_user": _name(item.related_user),
            "related_leave": item.related_leave_id or "",
            "triggered_by": _name(item.triggered_by),
            "error": item.error_message,
            "timestamp": item.created_at,
        })
    return rows


def _holiday_rows(filters):
    start, end = _period_range(filters)
    qs = CompanyHoliday.objects.all()
    if start:
        qs = qs.filter(date__gte=start)
    if end:
        qs = qs.filter(date__lte=end)
    return [{"name": item.name, "date": item.date, "optional": item.is_optional} for item in qs.order_by("date")]


def _wfh_rows(filters):
    return [{"weekday": item.get_weekday_display(), "active": item.is_active, "updated_at": item.updated_at} for item in WorkFromHomeDay.objects.order_by("weekday")]


def _year_end_rows(filters):
    return [{"year": item.year, "completed_at": item.completed_at, "status": "completed" if item.completed_at else "pending"} for item in YearEndCarryForwardRun.objects.order_by("-year")]


def _service_audit_rows(filters):
    qs = _admin_audit_queryset(filters).filter(
        Q(action__icontains="SERVICE")
        | Q(action__icontains="RESTORE")
        | Q(action__icontains="MAINTENANCE")
        | Q(changes__has_key="service_action")
        | Q(changes__has_key="database_restore")
        | Q(changes__has_key="maintenance_mode")
        | Q(changes__has_key="archive_pdf")
    )
    return [{
        "action": audit.action,
        "object": audit.object_repr,
        "changed_by": _name(audit.updated_by),
        "changed_at": audit.changed_at,
        "reason": audit.reason,
        "changes": _json(audit.changes),
    } for audit in qs]


def _system_health_rows(filters):
    from django.conf import settings
    from django.db import connection
    from App.services.maintenance_mode import is_maintenance_mode_enabled
    from App.services.startup_checks import get_backup_catchup_status, get_weekly_report_catchup_status, get_year_end_catchup_status

    backup = get_backup_catchup_status()
    weekly = get_weekly_report_catchup_status()
    year_end = get_year_end_catchup_status()
    return [
        {"section": "database", "metric": "vendor", "value": connection.vendor},
        {"section": "database", "metric": "engine", "value": settings.DATABASES["default"]["ENGINE"]},
        {"section": "email", "metric": "host", "value": settings.EMAIL_HOST},
        {"section": "email", "metric": "default_from", "value": settings.DEFAULT_FROM_EMAIL},
        {"section": "maintenance", "metric": "enabled", "value": is_maintenance_mode_enabled()},
        {"section": "startup", "metric": "backup_should_run", "value": backup["should_run"]},
        {"section": "startup", "metric": "weekly_report_should_run", "value": weekly["should_run"]},
        {"section": "startup", "metric": "year_end_should_run", "value": year_end["should_run"]},
    ]


def _hr_summary_rows(filters):
    start, end = _period_range(filters)
    leaves = list(_leaves(filters))
    users = list(_users(filters))
    balances = {balance.user_id: balance for balance in LeaveBalance.objects.select_related("user")}
    holidays = CompanyHoliday.objects.filter(date__gte=start, date__lte=end) if start and end else CompanyHoliday.objects.none()
    active_wfh = list(WorkFromHomeDay.objects.filter(is_active=True).order_by("weekday"))

    approved = [leave for leave in leaves if leave.status == "Approved"]
    rejected = [leave for leave in leaves if leave.status == "Rejected"]
    pending = [leave for leave in leaves if leave.status == "Pending"]
    leave_values = {leave.id: float(_leave_value(leave) or 0) for leave in leaves}
    approved_days = sum(leave_values[leave.id] for leave in approved)
    leave_type_counts = Counter(leave.leave_type for leave in leaves)
    leave_type_days = defaultdict(float)
    for leave in leaves:
        leave_type_days[leave.leave_type] += leave_values[leave.id]

    rows = []
    employees_included = len(users)
    total_requests = len(leaves)
    rows.append({
        "section": "Overview",
        "period_type": filters.get("period_type"),
        "period_start": start,
        "period_end": end,
        "total_employees": get_user_model().objects.count(),
        "active_employees": get_user_model().objects.filter(is_active=True).count(),
        "inactive_employees": get_user_model().objects.filter(is_active=False).count(),
        "employees_included": employees_included,
        "total_leave_requests": total_requests,
        "approved_requests": len(approved),
        "rejected_requests": len(rejected),
        "pending_requests": len(pending),
        "approval_rate": _rate(len(approved), total_requests),
        "rejection_rate": _rate(len(rejected), total_requests),
        "pending_rate": _rate(len(pending), total_requests),
        "average_requests_per_employee": round(total_requests / employees_included, 2) if employees_included else 0,
        "average_approved_leave_days_per_employee": round(approved_days / employees_included, 2) if employees_included else 0,
        "total_working_days_in_period": _working_days_between(start, end),
        "total_holidays_in_period": holidays.count(),
        "wfh_weekdays_active": ", ".join(item.get_weekday_display() for item in active_wfh),
    })

    for leave_type in ["Sick", "Earned", "Unpaid", "Short", "Half"]:
        rows.append({
            "section": "Leave Type Summary",
            "leave_type": leave_type,
            "request_count": leave_type_counts.get(leave_type, 0),
            "working_or_equivalent_days_used": round(leave_type_days.get(leave_type, 0), 2),
        })

    department_groups = defaultdict(list)
    for leave in leaves:
        department_groups[_profile_value(leave.user, "department") or "Not assigned"].append(leave)
    for department, dept_leaves in sorted(department_groups.items()):
        dept_user_ids = {leave.user_id for leave in dept_leaves}
        type_counter = Counter(leave.leave_type for leave in dept_leaves)
        dept_days = sum(leave_values[leave.id] for leave in dept_leaves)
        rows.append({
            "section": "Department Summary",
            "department": department,
            "employee_count": len(dept_user_ids),
            "active_employee_count": get_user_model().objects.filter(id__in=dept_user_ids, is_active=True).count(),
            "total_leave_requests": len(dept_leaves),
            "approved_count": sum(1 for leave in dept_leaves if leave.status == "Approved"),
            "rejected_count": sum(1 for leave in dept_leaves if leave.status == "Rejected"),
            "pending_count": sum(1 for leave in dept_leaves if leave.status == "Pending"),
            "total_leave_days": round(dept_days, 2),
            "average_leave_days_per_employee": round(dept_days / len(dept_user_ids), 2) if dept_user_ids else 0,
            "most_used_leave_type": type_counter.most_common(1)[0][0] if type_counter else "",
            "sick_leave_days": round(sum(leave_values[leave.id] for leave in dept_leaves if leave.leave_type == "Sick"), 2),
            "earned_leave_days": round(sum(leave_values[leave.id] for leave in dept_leaves if leave.leave_type == "Earned"), 2),
            "unpaid_leave_days": round(sum(leave_values[leave.id] for leave in dept_leaves if leave.leave_type == "Unpaid"), 2),
        })

    for user in users:
        user_leaves = [leave for leave in leaves if leave.user_id == user.id]
        if not user_leaves and not filters.get("include_zero_activity"):
            continue
        balance = balances.get(user.id)
        latest = max(user_leaves, key=lambda leave: leave.created_at, default=None)
        rows.append({
            "section": "Employee Summary",
            "employee_id": _profile_value(user, "employee_id"),
            "employee_name": _name(user),
            "department": _profile_value(user, "department"),
            "role": user.role,
            "joining_date": _profile_value(user, "date_of_joining"),
            "total_requests": len(user_leaves),
            "approved_requests": sum(1 for leave in user_leaves if leave.status == "Approved"),
            "rejected_requests": sum(1 for leave in user_leaves if leave.status == "Rejected"),
            "pending_requests": sum(1 for leave in user_leaves if leave.status == "Pending"),
            "sick_used": balance.sick_used if balance else "",
            "earned_used": balance.earned_used if balance else "",
            "unpaid_used": balance.unpaid if balance else "",
            "short_count": sum(1 for leave in user_leaves if leave.leave_type == "Short"),
            "half_count": sum(1 for leave in user_leaves if leave.leave_type == "Half"),
            "remaining_sick": (balance.sick_total - balance.sick_used) if balance else "",
            "remaining_earned": (balance.earned_total - balance.earned_used) if balance else "",
            "total_remaining": balance.total_leave_remaining if balance else "",
            "most_recent_leave_date": latest.from_date if latest else "",
            "most_recent_leave_status": latest.status if latest else "",
        })

    total_sick = sum((balance.sick_total for balance in balances.values()), 0)
    used_sick = sum((balance.sick_used for balance in balances.values()), 0)
    total_earned = sum((balance.earned_total for balance in balances.values()), 0)
    used_earned = sum((balance.earned_used for balance in balances.values()), 0)
    low_sick = [balance.user.username for balance in balances.values() if balance.sick_total - balance.sick_used <= 2]
    low_earned = [balance.user.username for balance in balances.values() if balance.earned_total - balance.earned_used <= 2]
    rows.append({
        "section": "Balance Summary",
        "total_sick_allocated": total_sick,
        "total_sick_used": used_sick,
        "total_sick_remaining": round(total_sick - used_sick, 2),
        "total_earned_allocated": total_earned,
        "total_earned_used": used_earned,
        "total_earned_remaining": round(total_earned - used_earned, 2),
        "total_unpaid_taken": sum((balance.unpaid for balance in balances.values()), 0),
        "employees_with_low_sick_balance": ", ".join(low_sick),
        "employees_with_low_earned_balance": ", ".join(low_earned),
        "employees_with_unusual_negative_balance": ", ".join(balance.user.username for balance in balances.values() if balance.sick_total - balance.sick_used < 0 or balance.earned_total - balance.earned_used < 0),
    })

    reviewer_groups = defaultdict(list)
    for leave in leaves:
        reviewer_groups[_name(leave.reviewed_by) or "Not reviewed"].append(leave)
    for reviewer, reviewer_leaves in reviewer_groups.items():
        decision_times = [_decision_hours(leave) for leave in reviewer_leaves if _decision_hours(leave) is not None]
        rows.append({
            "section": "Approval Workflow",
            "reviewer": reviewer,
            "requests_reviewed": sum(1 for leave in reviewer_leaves if leave.reviewed_by_id),
            "approved_by_reviewer": sum(1 for leave in reviewer_leaves if leave.status == "Approved"),
            "rejected_by_reviewer": sum(1 for leave in reviewer_leaves if leave.status == "Rejected"),
            "average_decision_time_hours": round(sum(decision_times) / len(decision_times), 2) if decision_times else "",
            "pending_requests_older_than_2_days": sum(1 for leave in pending if leave.created_at and leave.created_at <= timezone.now() - timedelta(days=2)),
            "fastest_decision_time_hours": round(min(decision_times), 2) if decision_times else "",
            "slowest_decision_time_hours": round(max(decision_times), 2) if decision_times else "",
        })

    rows.append({
        "section": "Holiday/WFH Impact",
        "holidays_in_period": holidays.count(),
        "optional_holidays_in_period": holidays.filter(is_optional=True).count(),
        "wfh_weekdays_active": ", ".join(item.get_weekday_display() for item in active_wfh),
        "leave_requests_affected_by_wfh_bridge": sum(1 for leave in leaves if leave.requested_from_date and (leave.requested_from_date != leave.from_date or leave.requested_to_date != leave.to_date)),
        "leave_requests_overlapping_holidays": sum(1 for leave in leaves if holidays.filter(date__gte=leave.from_date, date__lte=leave.to_date).exists()),
        "working_days_excluded_by_holidays_weekends": "See leave request report for row-level breakdown",
    })

    start_dt, end_dt = _date_time_bounds(filters)
    email_qs = EmailDeliveryLog.objects.all()
    comm_qs = Communication.objects.all()
    if start_dt:
        email_qs = email_qs.filter(created_at__gte=start_dt)
        comm_qs = comm_qs.filter(created_at__gte=start_dt)
    if end_dt:
        email_qs = email_qs.filter(created_at__lte=end_dt)
        comm_qs = comm_qs.filter(created_at__lte=end_dt)
    rows.append({
        "section": "Communication/Email",
        "leave_alert_emails_sent": email_qs.filter(status="sent", email_type__icontains="leave").count(),
        "leave_alert_emails_failed": email_qs.filter(status="failed", email_type__icontains="leave").count(),
        "admin_hr_employee_messages_sent": comm_qs.count(),
        "announcements_sent": comm_qs.filter(message_type="ANNOUNCEMENT").count(),
        "unread_admin_messages_count": "See communication read/seen report",
        "failed_email_count_by_type": _json(dict(Counter(email_qs.filter(status="failed").values_list("email_type", flat=True)))),
    })

    rows.append({
        "section": "Risk/Attention",
        "high_leave_usage_employees": ", ".join(_top_leave_users(leaves, leave_values)),
        "employees_with_many_unpaid_leaves": ", ".join(_many_unpaid_users(leaves)),
        "employees_with_pending_requests": ", ".join(sorted({_name(leave.user) for leave in pending})),
        "employees_with_low_remaining_balance": ", ".join(sorted(set(low_sick + low_earned))),
        "departments_with_high_leave_load": ", ".join(_top_departments(department_groups, leave_values)),
        "pending_requests_older_than_2_days": sum(1 for leave in pending if leave.created_at and leave.created_at <= timezone.now() - timedelta(days=2)),
        "failed_leave_related_emails": email_qs.filter(status="failed", email_type__icontains="leave").count(),
        "inactive_users_with_pending_or_future_approved_leaves": _inactive_future_leave_count(end),
    })
    return rows


def _rate(part, whole):
    return round((part / whole) * 100, 2) if whole else 0


def _working_days_between(start, end):
    if not start or not end:
        return ""
    holidays = set(CompanyHoliday.objects.filter(date__gte=start, date__lte=end).values_list("date", flat=True))
    current = start
    total = 0
    while current <= end:
        if current.weekday() < 5 and current not in holidays:
            total += 1
        current += timedelta(days=1)
    return total


def _decision_hours(leave):
    decision_at = leave.approved_at or leave.rejected_at
    if not decision_at or not leave.created_at:
        return None
    return (decision_at - leave.created_at).total_seconds() / 3600


def _top_leave_users(leaves, leave_values):
    totals = defaultdict(float)
    for leave in leaves:
        totals[_name(leave.user)] += leave_values.get(leave.id, 0)
    return [name for name, _ in sorted(totals.items(), key=lambda item: item[1], reverse=True)[:10]]


def _many_unpaid_users(leaves):
    counts = Counter(_name(leave.user) for leave in leaves if leave.leave_type == "Unpaid")
    return [name for name, count in counts.items() if count >= 2]


def _top_departments(department_groups, leave_values):
    totals = []
    for department, leaves in department_groups.items():
        totals.append((department, sum(leave_values.get(leave.id, 0) for leave in leaves)))
    return [department for department, _ in sorted(totals, key=lambda item: item[1], reverse=True)[:5]]


def _inactive_future_leave_count(end):
    qs = Leave.objects.filter(user__is_active=False, status__in=["Pending", "Approved"])
    if end:
        qs = qs.filter(to_date__gte=timezone.localdate())
    return qs.count()


def _rows_to_csv(rows):
    output = StringIO()
    if not rows:
        return b"No data\n"
    fieldnames = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    label_fieldnames = [column_label(key) for key in fieldnames]
    writer = csv.DictWriter(output, fieldnames=label_fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({
            column_label(key): _string_value(row.get(key, ""))
            for key in fieldnames
        })
    return output.getvalue().encode("utf-8-sig")


def _rows_to_pdf(title, rows, filters, actor=None):
    described_filters = describe_export_filters(filters)
    lines = [
        title,
        "=" * min(len(title), 80),
        f"Generated at: {timezone.localtime(timezone.now()).strftime('%d %b %Y, %I:%M %p')}",
        f"Generated by: {_name(actor)}",
        f"Period: {describe_period(filters)}",
        f"Rows: {len(rows)}",
        "",
    ]
    if described_filters:
        lines.append("Filters")
        lines.append("-" * 40)
        for key, value in described_filters.items():
            if key in {"reason", "export_format"}:
                continue
            lines.append(f"- {column_label(key)}: {value}")
        lines.append("")
    current_section = None
    for index, row in enumerate(rows[:500], start=1):
        section = row.get("section")
        if section and section != current_section:
            current_section = section
            lines.append(str(section).upper())
            lines.append("-" * min(len(str(section)), 80))
        prefix = f"{index}."
        if section:
            prefix = f"{index}. [{section}]"
        lines.append(prefix)
        for key, value in row.items():
            if key == "section":
                continue
            lines.append(f"  {column_label(key)}: {_string_value(value)}")
        lines.append("")
    if len(rows) > 500:
        lines.append(f"... truncated in PDF after 500 rows. Use CSV for full {len(rows)} rows.")
    return _simple_pdf(lines)


def _string_value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return timezone.localtime(value).strftime("%d %b %Y, %I:%M %p") if timezone.is_aware(value) else value.strftime("%d %b %Y, %I:%M %p")
    if isinstance(value, date):
        return value.strftime("%d %b %Y")
    return str(value)


def _pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _simple_pdf(lines):
    page_lines = []
    for line in lines:
        text = _string_value(line)
        while len(text) > 105:
            page_lines.append(text[:105])
            text = text[105:]
        page_lines.append(text)

    pages = [page_lines[index:index + 42] for index in range(0, len(page_lines), 42)] or [[]]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{' '.join(f'{3 + i * 2} 0 R' for i in range(len(pages)))}] /Count {len(pages)} >>".encode("latin-1"),
    ]
    for page_index, page in enumerate(pages):
        page_obj_id = 3 + page_index * 2
        content_obj_id = page_obj_id + 1
        stream_lines = ["BT", "/F1 9 Tf", "40 780 Td"]
        for line in page:
            stream_lines.append(f"({_pdf_escape(line)}) Tj")
            stream_lines.append("0 -16 Td")
        stream_lines.append("ET")
        stream = "\n".join(stream_lines).encode("latin-1", errors="replace")
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_obj_id} 0 R >>".encode("latin-1"))
        objects.append(b"<< /Length " + str(len(stream)).encode("latin-1") + b" >>\nstream\n" + stream + b"\nendstream")

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
    pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("latin-1"))
    return bytes(pdf)


def _safe_input(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return "0"


def _choose_from_options(title, options, *, allow_back=True):
    while True:
        print(f"\n{title}")
        for index, (_value, label) in enumerate(options, start=1):
            print(f"{index}. {label}")
        if allow_back:
            print("B. Back")
        print("0. Exit")

        choice = _safe_input("Choose an option: ").lower()
        if choice in {"0", "exit", "q", "quit"}:
            return None
        if allow_back and choice in {"b", "back"}:
            return "BACK"
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1][0]
        print("Invalid choice.")


def _parse_date(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _ask_year():
    today_year = timezone.localdate().year
    while True:
        value = _safe_input(f"Enter year [{today_year}] (B=Back, 0=Exit): ").lower()
        if value in {"0", "exit", "q", "quit"}:
            return None
        if value in {"b", "back"}:
            return "BACK"
        if not value:
            return today_year
        if value.isdigit() and 1900 <= int(value) <= 9999:
            return int(value)
        print("Invalid year.")


def _ask_period_filters():
    while True:
        period_type = _choose_from_options("Select period type:", PERIOD_TYPES, allow_back=False)
        if period_type is None:
            return None

        filters = {"period_type": period_type}
        if period_type == "custom":
            while True:
                start_text = _safe_input("Enter from date YYYY-MM-DD, or blank for no start (B=Back, 0=Exit): ").lower()
                if start_text in {"0", "exit", "q", "quit"}:
                    return None
                if start_text in {"b", "back"}:
                    break

                end_text = _safe_input("Enter to date YYYY-MM-DD, or blank for no end (B=Back, 0=Exit): ").lower()
                if end_text in {"0", "exit", "q", "quit"}:
                    return None
                if end_text in {"b", "back"}:
                    break

                start = _parse_date(start_text) if start_text else None
                end = _parse_date(end_text) if end_text else None
                if start_text and not start:
                    print("Invalid from date.")
                    continue
                if end_text and not end:
                    print("Invalid to date.")
                    continue
                if start and end and start > end:
                    print("Invalid date range. From date cannot be after to date.")
                    continue
                filters["date_from"] = start
                filters["date_to"] = end
                return filters
            continue

        year = _ask_year()
        if year is None:
            return None
        if year == "BACK":
            continue
        filters["year"] = year

        if period_type == "monthly":
            month = _choose_from_options(
                "Select month:",
                [(str(index), date(2000, index, 1).strftime("%B")) for index in range(1, 13)],
            )
            if month is None:
                return None
            if month == "BACK":
                continue
            filters["month"] = int(month)
        elif period_type == "quarterly":
            quarter = _choose_from_options("Select quarter:", [("1", "Q1"), ("2", "Q2"), ("3", "Q3"), ("4", "Q4")])
            if quarter is None:
                return None
            if quarter == "BACK":
                continue
            filters["quarter"] = int(quarter)
        elif period_type == "six_month":
            half = _choose_from_options("Select half-year:", [("first", "Jan-Jun"), ("second", "Jul-Dec")])
            if half is None:
                return None
            if half == "BACK":
                continue
            filters["half_year"] = half

        return filters


def _lookup_user(prompt, *, role=None):
    while True:
        value = _safe_input(prompt).strip()
        lowered = value.lower()
        if lowered in {"", "skip", "s"}:
            return None
        if lowered in {"0", "exit", "q", "quit"}:
            return "EXIT"
        if lowered in {"b", "back"}:
            return "BACK"

        query = Q(username__iexact=value) | Q(email__iexact=value) | Q(profile__employee_id__iexact=value)
        users = get_user_model().objects.select_related("profile").filter(query)
        if role:
            users = users.filter(role=role)
        user = users.first()
        if user:
            return user
        print("No user found for that username/email/employee ID.")


def _ask_yes_no(prompt, default=False):
    suffix = "Y/n" if default else "y/N"
    while True:
        value = _safe_input(f"{prompt} ({suffix}): ").lower()
        if not value:
            return default
        if value in {"y", "yes"}:
            return True
        if value in {"n", "no"}:
            return False
        print("Type Y or N.")


def _ask_optional_filters(report_type):
    filters = {}
    print("\nOptional filters")
    print("Press Enter to skip any filter.")

    if report_type in {"employee_master", "leave_request", "leave_balance", "leave_balance_audit", "hr_summary"}:
        employee = _lookup_user("Employee username/email/employee ID (Enter=Skip, B=Back, 0=Exit): ", role=None)
        if employee == "EXIT":
            return None
        if employee == "BACK":
            return "BACK"
        if employee:
            filters["employee"] = employee

    if report_type in {"employee_master", "communication", "hr_summary"}:
        role = _choose_from_options("Filter by role:", [("", "No role filter"), ("EMPLOYEE", "Employee"), ("HR", "HR"), ("Admin", "Admin")])
        if role is None:
            return None
        if role == "BACK":
            return "BACK"
        if role:
            filters["role"] = role

    if report_type in {"employee_master", "hr_summary"}:
        active_status = _choose_from_options("Filter by active status:", [("", "All"), ("active", "Active only"), ("inactive", "Inactive only")])
        if active_status is None:
            return None
        if active_status == "BACK":
            return "BACK"
        if active_status:
            filters["active_status"] = active_status

    if report_type in {"employee_master", "leave_request", "leave_balance", "hr_summary"}:
        department = _safe_input("Department contains (Enter=Skip, B=Back, 0=Exit): ")
        if department.lower() in {"0", "exit", "q", "quit"}:
            return None
        if department.lower() in {"b", "back"}:
            return "BACK"
        if department:
            filters["department"] = department

    if report_type in {"leave_request", "hr_summary"}:
        leave_status = _choose_from_options("Filter by leave status:", [("", "All"), ("Pending", "Pending"), ("Approved", "Approved"), ("Rejected", "Rejected")])
        if leave_status is None:
            return None
        if leave_status == "BACK":
            return "BACK"
        if leave_status:
            filters["leave_status"] = leave_status

        leave_type = _choose_from_options("Filter by leave type:", [("", "All"), ("Short", "Short"), ("Half", "Half"), ("Unpaid", "Unpaid"), ("Sick", "Sick"), ("Earned", "Earned")])
        if leave_type is None:
            return None
        if leave_type == "BACK":
            return "BACK"
        if leave_type:
            filters["leave_type"] = leave_type

        deducted_from = _choose_from_options("Filter by deducted from:", [("", "All"), ("Earned", "Earned"), ("Sick", "Sick"), ("Unpaid", "Unpaid"), ("None", "None")])
        if deducted_from is None:
            return None
        if deducted_from == "BACK":
            return "BACK"
        if deducted_from:
            filters["deducted_from"] = deducted_from

    if report_type == "leave_request":
        reviewer = _lookup_user("Reviewed by username/email/employee ID (Enter=Skip, B=Back, 0=Exit): ")
        if reviewer == "EXIT":
            return None
        if reviewer == "BACK":
            return "BACK"
        if reviewer:
            filters["reviewed_by"] = reviewer

    if report_type in {"admin_audit", "delete_audit", "service_audit"}:
        action = _safe_input("Admin/service action contains (Enter=Skip, B=Back, 0=Exit): ")
        if action.lower() in {"0", "exit", "q", "quit"}:
            return None
        if action.lower() in {"b", "back"}:
            return "BACK"
        if action:
            filters["admin_action"] = action

    if report_type == "email_delivery":
        email_status = _safe_input("Email status contains, e.g. sent/failed (Enter=Skip, B=Back, 0=Exit): ")
        if email_status.lower() in {"0", "exit", "q", "quit"}:
            return None
        if email_status.lower() in {"b", "back"}:
            return "BACK"
        if email_status:
            filters["email_status"] = email_status

    if report_type == "hr_summary":
        filters["include_zero_activity"] = _ask_yes_no("Include employees with zero leave activity?", default=False)

    return filters


def _ask_audit_reason():
    while True:
        reason = _safe_input("Enter audit reason (B=Back, 0=Exit): ")
        lowered = reason.lower()
        if lowered in {"0", "exit", "q", "quit"}:
            return None
        if lowered in {"b", "back"}:
            return "BACK"
        if reason:
            return reason
        print("Audit reason is required.")


def _output_dir():
    output_dir = Path(settings.BASE_DIR) / "generated_reports"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def _save_export(export):
    output_path = _output_dir() / export["filename"]
    output_path.write_bytes(export["content"])
    return output_path


def _record_export_audit(filters, export, reason, output_path, result="success", error_message=""):
    AdminAuditLog.objects.create(
        model_label="ReportExportService",
        object_id=export.get("filename") or filters.get("report_type", "report_export"),
        object_repr=export.get("title") or dict(REPORT_TYPES).get(filters.get("report_type"), "Report export"),
        action="REPORT_EXPORT",
        updated_by=None,
        reason=reason,
        changes={
            "result": result,
            "filters": describe_export_filters(filters),
            "filename": export.get("filename"),
            "row_count": export.get("row_count"),
            "output_path": str(output_path) if output_path else "",
            "error": error_message,
        },
    )


def _print_export_summary(filters, export_format, reason):
    print("\nExport summary")
    print("-" * 56)
    print(f"Report: {dict(REPORT_TYPES).get(filters['report_type'])}")
    print(f"Period: {describe_period(filters)}")
    print(f"Format: {export_format.upper()}")
    print(f"Reason: {reason}")
    useful_filters = describe_export_filters(filters)
    if useful_filters:
        print("Filters:")
        for key, value in useful_filters.items():
            if key in {"report_type", "period_type", "export_format", "date_from", "date_to", "year", "month", "quarter", "half_year"}:
                continue
            print(f"- {column_label(key)}: {value}")
    print("-" * 56)


def run_interactive():
    print("\nReport Export Service")
    print("Generate CSV/PDF reports and save them into generated_reports.")

    while True:
        report_type = _choose_from_options("Select report type:", REPORT_TYPES, allow_back=False)
        if report_type is None:
            print("Exit.")
            return

        while True:
            period_filters = _ask_period_filters()
            if period_filters is None:
                print("Exit.")
                return

            optional_filters = _ask_optional_filters(report_type)
            if optional_filters is None:
                print("Exit.")
                return
            if optional_filters == "BACK":
                continue

            export_format = _choose_from_options("Select export format:", EXPORT_FORMATS)
            if export_format is None:
                print("Exit.")
                return
            if export_format == "BACK":
                continue

            reason = _ask_audit_reason()
            if reason is None:
                print("Exit.")
                return
            if reason == "BACK":
                continue

            filters = {
                "report_type": report_type,
                "export_format": export_format,
                **period_filters,
                **optional_filters,
            }
            _print_export_summary(filters, export_format, reason)

            confirmation = _safe_input("Type EXPORT to generate report (B=Back, 0=Exit): ")
            if confirmation.lower() in {"0", "exit", "q", "quit"}:
                print("Exit.")
                return
            if confirmation.lower() in {"b", "back"}:
                continue
            if confirmation != "EXPORT":
                print("Cancelled. Report was not exported.")
                return

            try:
                export = build_report_export(filters)
                output_path = _save_export(export)
                _record_export_audit(filters, export, reason, output_path, result="success")
            except Exception as exc:
                error_export = {
                    "filename": "",
                    "title": dict(REPORT_TYPES).get(report_type, report_type),
                    "row_count": 0,
                }
                _record_export_audit(filters, error_export, reason, None, result="failed", error_message=str(exc))
                print(f"FAILED: Could not export report. {exc}")
                print("Audit log: Created")
                return

            print("\nSUCCESS: Report exported")
            print(f"Title: {export['title']}")
            print(f"Rows: {export['row_count']}")
            print(f"Location: {output_path}")
            print("Audit log: Created")
            return


if __name__ == "__main__":
    run_interactive()
