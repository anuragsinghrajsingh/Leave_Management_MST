import logging
import os
import sys
import time
from datetime import datetime, timedelta
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

from django.utils import timezone
from django.db.models import Count, Q
from django.contrib.auth import get_user_model
from django.template.loader import render_to_string
from django.conf import settings
from App.models import AdminAuditLog, Leave, LeaveBalance, Profile
from App.services.uptime_tracker import format_current_uptime
from App.views import send_branded_email

logger = logging.getLogger('lms_service_weekly_report')

EMPLOYEE_PAGE_SIZE = 10


def _get_recent_backup_files(today, days=7):
    backup_dir = Path(settings.BASE_DIR) / "backups"
    if not backup_dir.exists():
        return []

    start_day = today - timedelta(days=days - 1)
    return [
        backup
        for backup in backup_dir.glob("backup_*.zip")
        if start_day <= timezone.localdate(timezone.make_aware(
            timezone.datetime.fromtimestamp(backup.stat().st_mtime)
        )) <= today
    ]


def _build_backup_health(today):
    recent_backups = _get_recent_backup_files(today)
    backup_days = {
        timezone.localdate(timezone.make_aware(
            timezone.datetime.fromtimestamp(backup.stat().st_mtime)
        ))
        for backup in recent_backups
    }
    last_backup = max(recent_backups, key=lambda item: item.stat().st_mtime, default=None)

    backup_summary = f"{len(backup_days)}/7 Successful"
    if last_backup:
        last_backup_dt = timezone.localtime(timezone.make_aware(
            timezone.datetime.fromtimestamp(last_backup.stat().st_mtime)
        ))
        last_backup_text = last_backup_dt.strftime("%b %d, %I:%M %p")
    else:
        last_backup_text = "No backup found"

    return backup_summary, last_backup_text


def _count_recent_unauthorized_attempts(start_date):
    security_log_dir = Path(settings.BASE_DIR) / "logs" / "security"
    if not security_log_dir.exists():
        return 0

    attempts = 0
    for log_file in security_log_dir.glob("unauthorized.log*"):
        if timezone.make_aware(
            timezone.datetime.fromtimestamp(log_file.stat().st_mtime)
        ) < start_date:
            continue

        try:
            for line in log_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if "UNAUTHORIZED_ACCESS_ATTEMPT" not in line:
                    continue

                try:
                    timestamp_text = line.split(" | ", 1)[0].split("] ", 1)[1]
                    line_timestamp = timezone.make_aware(
                        datetime.strptime(timestamp_text, "%Y-%m-%d %H:%M:%S,%f")
                    )
                except (IndexError, ValueError):
                    # Keep malformed matching entries visible rather than silently hiding them.
                    attempts += 1
                    continue

                if line_timestamp >= start_date:
                    attempts += 1
        except OSError:
            logger.warning("REPORTS | Could not read security log file: %s", log_file)

    return attempts


def _measure_database_latency_ms():
    started = time.perf_counter()
    Leave.objects.exists()
    return max(round((time.perf_counter() - started) * 1000), 1)


def _build_system_health(today, start_date):
    logger.info("WEEKLY_REPORT | HEALTH | Building system health | Today=%s | Start=%s", today, start_date)
    backup_summary, last_backup_text = _build_backup_health(today)
    unauthorized_attempts = _count_recent_unauthorized_attempts(start_date)
    pending_notifications = Leave.objects.filter(
        status="Pending",
        user__is_active=True,
    ).count()
    db_latency_ms = _measure_database_latency_ms()

    return {
        "backups": backup_summary,
        "last_backup": last_backup_text,
        "security": f"{unauthorized_attempts} Unauthorized Attempts",
        "uptime": format_current_uptime(),
        "perf": f"{db_latency_ms}ms DB query",
        "notifications": f"{pending_notifications} pending",
    }

def get_week_range(week="current"):
    today = timezone.localdate()
    current_start = today - timedelta(days=today.weekday())
    week_key = str(week or "current").strip().lower()

    if week_key in {"previous", "prev", "-1"}:
        start_day = current_start - timedelta(days=7)
    else:
        start_day = current_start

    end_day = start_day + timedelta(days=6)
    return start_day, end_day


def build_weekly_hr_report_context(week="current", start_day=None, end_day=None, employee_id=None, employee_ids=None, include_system_health=True):
    """
    Compiles data for the 'Human Capital Operational Snapshot'.
    """
    User = get_user_model()
    if start_day is None or end_day is None:
        start_day, end_day = get_week_range(week)

    start_date = timezone.make_aware(timezone.datetime.combine(start_day, timezone.datetime.min.time()))
    end_date = timezone.make_aware(timezone.datetime.combine(end_day, timezone.datetime.max.time()))
    logger.info("WEEKLY_REPORT | CONTEXT | Building report context | Start=%s | End=%s", start_date, end_date)

    # 1. Compile Global Analytics (Selected Week)
    employee_filter_options = []
    for employee in User.objects.filter(role="EMPLOYEE", is_active=True).select_related("profile").order_by("first_name", "last_name", "username", "id"):
        profile = getattr(employee, "profile", None)
        employee_filter_options.append({
            "id": employee.id,
            "label": f"{employee.get_full_name() or employee.username} - {getattr(profile, 'employee_id', 'N/A') if profile else 'N/A'}",
        })

    all_employees = User.objects.filter(role="EMPLOYEE", is_active=True).select_related("profile").order_by("first_name", "last_name", "username", "id")
    if employee_id:
        all_employees = all_employees.filter(id=employee_id)
    if employee_ids:
        all_employees = all_employees.filter(id__in=employee_ids)
    all_employees = list(all_employees)

    leave_queryset = Leave.objects.filter(
        created_at__gte=start_date,
        created_at__lte=end_date,
        user__is_active=True,
    ).select_related("reviewed_by")
    if employee_id:
        leave_queryset = leave_queryset.filter(user_id=employee_id)
    if employee_ids:
        leave_queryset = leave_queryset.filter(user_id__in=employee_ids)
    
    balances_by_user_id = {
        balance.user_id: balance
        for balance in LeaveBalance.objects.filter(user__in=all_employees)
    }

    reports = []
    for report_user in all_employees:
        report_profile = getattr(report_user, "profile", None)
        
        # Get statistics for this user in the past 7 days
        user_leaves = leave_queryset.filter(user=report_user)
        stats = user_leaves.aggregate(
            total=Count("id"),
            approved=Count("id", filter=Q(status="Approved")),
            pending=Count("id", filter=Q(status="Pending")),
            rejected=Count("id", filter=Q(status="Rejected")),
        )
        
        # Get ALL leaves from the past 7 days for this employee (no limit)
        detailed_leaves = user_leaves.order_by("-created_at")
        
        balance = balances_by_user_id.get(report_user.id)
        
        reports.append({
            "user": report_user,
            "profile": report_profile,
            "full_name": report_user.get_full_name() or report_user.username,
            "total": stats["total"] or 0,
            "approved": stats["approved"] or 0,
            "pending": stats["pending"] or 0,
            "rejected": stats["rejected"] or 0,
            "leaves": detailed_leaves,
            "sick_used": balance.sick_used if balance else 0,
            "earned_used": balance.earned_used if balance else 0,
            "unpaid_used": balance.unpaid if balance else 0,
        })
    logger.info("WEEKLY_REPORT | CONTEXT | Employee report rows built | Count=%s", len(reports))

    # Global Totals (Past 7 Days)
    total_requests = leave_queryset.count()
    approved_total = leave_queryset.filter(status="Approved").count()
    pending_total = leave_queryset.filter(status="Pending").count()
    rejected_total = leave_queryset.filter(status="Rejected").count()
    employee_applied_count = leave_queryset.values("user").distinct().count()

    # 2. System Health Stats
    system_health = _build_system_health(end_day, start_date)

    context = {
        "period_start": start_day.strftime("%b %d, %Y"),
        "period_end": end_day.strftime("%b %d, %Y"),
        "period_start_iso": start_day.isoformat(),
        "period_end_iso": end_day.isoformat(),
        "week_key": str(week or "current"),
        "selected_employee_scope": "selected" if employee_id or employee_ids else "all",
        "selected_employee_count": len(reports),
        "total_requests": total_requests,
        "approved_total": approved_total,
        "pending_total": pending_total,
        "rejected_total": rejected_total,
        "employee_count": employee_applied_count,
        "reports": reports,
        "employee_filter_options": employee_filter_options,
        "system_health": system_health,
        "show_system_health": include_system_health,
        "portal_link": settings.SITE_URL if hasattr(settings, 'SITE_URL') else "http://localhost:8000"
    }
    logger.info(
        "WEEKLY_REPORT | CONTEXT | Totals | Requests=%s | Approved=%s | Pending=%s | Rejected=%s | Employees=%s",
        total_requests,
        approved_total,
        pending_total,
        rejected_total,
        employee_applied_count,
    )
    return context


def render_weekly_hr_report_html(context=None, week="current"):
    logger.info("WEEKLY_REPORT | RENDER | Rendering dashboard HTML.")
    context = context or build_weekly_hr_report_context(week=week)
    return render_to_string('emails/weekly_hr_report.html', context)


def generate_weekly_hr_report_pdf_bytes(context=None, week="current"):
    from App.services.pdf_generator import generate_pdf_from_html

    logger.info("WEEKLY_REPORT | PDF | Generating weekly report PDF bytes.")
    return generate_pdf_from_html(render_weekly_hr_report_html(context=context, week=week))


def generate_weekly_hr_report_pdf_file(context=None, week="current"):
    context = context or build_weekly_hr_report_context(week=week)
    output_dir = Path(settings.BASE_DIR) / "generated_pdfs"
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = timezone.localtime().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / (
        f"weekly_hr_report_{context['period_start_iso']}_to_{context['period_end_iso']}_{timestamp}.pdf"
    )
    pdf_bytes = generate_weekly_hr_report_pdf_bytes(context=context, week=week)
    output_path.write_bytes(pdf_bytes)
    logger.info(
        "WEEKLY_REPORT | PDF_ONLY | Saved weekly report PDF | Output=%s | Size=%s bytes",
        output_path,
        len(pdf_bytes),
    )
    return output_path


def _get_active_hr_emails():
    User = get_user_model()
    return list(
        User.objects.filter(role="HR", is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )


def send_weekly_hr_report(context=None, week="current"):
    """
    Compiles data for the 'Human Capital Operational Snapshot' and sends it to all HR users.
    """
    context = context or build_weekly_hr_report_context(week=week)
    start_label = context["period_start"]
    end_label = context["period_end"]
    end_day = datetime.strptime(context["period_end_iso"], "%Y-%m-%d").date()

    # 1. Fetch HR Recipients
    hr_emails = _get_active_hr_emails()
    logger.info("WEEKLY_REPORT | EMAIL | Active HR recipient count=%s", len(hr_emails))
    if not hr_emails:
        logger.warning("REPORT | No active HR emails found. Skipping weekly report.")
        return False

    # Render the gorgeous HTML
    dashboard_html = render_weekly_hr_report_html(context)
    
    # Render the simple cover email
    cover_html = render_to_string('emails/weekly_hr_report_cover.html', context)
    
    # Ensure to_email is a list
    to_email = hr_emails
        
    try:
        from App.services.pdf_generator import generate_pdf_from_html
        from django.core.mail import EmailMessage
        
        # 5. Generate High-Fidelity PDF Snapshot
        logger.info("REPORTS | Generating PDF Snapshot...")
        pdf_bytes = generate_pdf_from_html(dashboard_html)
        
        # 6. Send the Email with Attachment
        subject = f"Weekly Operational Snapshot: {start_label} - {end_label}"
        email = EmailMessage(
            subject=subject,
            body=cover_html,
            from_email=f"HR Portal <{settings.DEFAULT_FROM_EMAIL}>",
            to=to_email,
        )
        email.content_subtype = "html"
        
        # Attach the PDF
        filename = f"HR_Snapshot_{end_day.strftime('%Y%m%d')}.pdf"
        email.attach(filename, pdf_bytes, 'application/pdf')
        
        email.send(fail_silently=False)
        from App.services.email_delivery_log import record_email_delivery
        record_email_delivery(
            subject=subject,
            recipients=to_email,
            status="sent",
            email_type="weekly_hr_report",
            from_email=f"HR Portal <{settings.DEFAULT_FROM_EMAIL}>",
            metadata={"attachment": filename},
        )
        
        logger.info("REPORTS | SUCCESS | Weekly report PDF sent | Recipients=%s | Attachment=%s", len(to_email), filename)
        return True
        
    except Exception as e:
        from App.services.email_delivery_log import record_email_delivery
        record_email_delivery(
            subject=locals().get("subject", "Weekly Operational Snapshot"),
            recipients=to_email,
            status="failed",
            email_type="weekly_hr_report",
            from_email=f"HR Portal <{settings.DEFAULT_FROM_EMAIL}>",
            error_message=str(e),
        )
        logger.exception("REPORTS | FAILED | Could not send weekly report PDF")
        return False


def _employee_report_label(user):
    profile = getattr(user, "profile", None)
    employee_code = getattr(profile, "employee_id", "") if profile else ""
    department = getattr(profile, "department", "") if profile else ""
    full_name = user.get_full_name() or user.username
    return " | ".join([
        full_name,
        employee_code or "No employee ID",
        user.username or "No username",
        user.email or "No email",
        department or "No department",
    ])


def _employee_search_text(employee):
    profile = getattr(employee, "profile", None)
    fields = [
        employee.get_full_name(),
        employee.username,
        employee.email,
        getattr(profile, "employee_id", "") if profile else "",
        getattr(profile, "phone", "") if profile else "",
        getattr(profile, "department", "") if profile else "",
    ]
    return " ".join(str(field).lower() for field in fields if field)


def _search_employee_entries(employee_entries):
    term = input("\nSearch by name, username, email, employee ID, phone, or department: ").strip()
    if not term:
        print("Search cannot be blank.")
        return None

    needle = term.lower()
    results = [
        entry
        for entry in employee_entries
        if needle in _employee_search_text(entry[1])
    ]
    if not results:
        print("No matching employees found.")
        return None

    print(f"Search active: {term} ({len(results)} match(es))")
    return results


def _print_employee_page(employee_entries, page, search_active=False):
    total = len(employee_entries)
    total_pages = max(1, (total + EMPLOYEE_PAGE_SIZE - 1) // EMPLOYEE_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * EMPLOYEE_PAGE_SIZE
    end = min(start + EMPLOYEE_PAGE_SIZE, total)

    title = "Search results" if search_active else "Active employees"
    print(f"\n{title} - page {page}/{total_pages} ({total} total):")
    for index, employee in employee_entries[start:end]:
        print(f"{index}. {_employee_report_label(employee)}")
    print("N. Next page")
    print("P. Previous page")
    print("S. Search employees")
    if search_active:
        print("A. Show all employees")
    print("B. Back")
    print("0. Exit")

    return page, total_pages


def _print_selected_employees(selected_employees):
    if not selected_employees:
        print("\nSelected employees: none")
        return

    print("\nSelected employees:")
    for index, employee in enumerate(selected_employees, start=1):
        print(f"{index}. {_employee_report_label(employee)}")


def _ask_include_system_health():
    while True:
        choice = input("\nInclude System & Security Oversight section? Type Y or N: ").strip().lower()
        if choice in {"y", "yes"}:
            return True
        if choice in {"", "n", "no"}:
            return False
        print("Invalid choice. Type Y to include it, or N to hide it.")


def _parse_date_input(value):
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _ask_report_period():
    while True:
        print("\nSelect report period:")
        print("1. Current week")
        print("2. Previous week")
        print("3. Custom date range")
        print("0. Exit")
        choice = input("Choose 1, 2, 3, or 0: ").strip().lower()

        if choice in {"c", "cancel", "q", "quit"}:
            return None
        if choice in {"", "1", "current"}:
            start_day, end_day = get_week_range("current")
            print(f"Selected: Current week ({start_day} to {end_day})")
            return {"week": "current", "start_day": start_day, "end_day": end_day}
        if choice in {"2", "previous", "prev"}:
            start_day, end_day = get_week_range("previous")
            print(f"Selected: Previous week ({start_day} to {end_day})")
            return {"week": "previous", "start_day": start_day, "end_day": end_day}
        if choice in {"3", "custom"}:
            while True:
                start_text = input("Enter start date YYYY-MM-DD (B=Back, 0=Exit): ").strip().lower()
                if start_text in {"b", "back"}:
                    break
                if start_text in {"0", "c", "cancel", "q", "quit"}:
                    return None

                end_text = input("Enter end date YYYY-MM-DD (B=Back, 0=Exit): ").strip().lower()
                if end_text in {"b", "back"}:
                    break
                if end_text in {"0", "c", "cancel", "q", "quit"}:
                    return None

                start_day = _parse_date_input(start_text)
                end_day = _parse_date_input(end_text)
                if not start_day or not end_day:
                    print("Invalid date. Use YYYY-MM-DD.")
                    continue
                if start_day > end_day:
                    print("Invalid date range. Start date cannot be after end date.")
                    continue

                print(f"Selected: Custom range ({start_day} to {end_day})")
                return {"week": "custom", "start_day": start_day, "end_day": end_day}
            continue

        print("Invalid choice. Choose 1, 2, 3, or C.")


def _print_report_summary(context, action_label, hr_recipient_count=None):
    report_count = context.get("selected_employee_count", len(context.get("reports", [])))
    if context.get("selected_employee_scope") == "selected":
        employee_scope = f"{report_count} selected employee(s)"
    else:
        employee_scope = f"All active employees ({report_count})"

    print("\nReport summary")
    print("-" * 56)
    print(f"Period: {context['period_start']} - {context['period_end']}")
    print(f"Employees: {employee_scope}")
    print(f"Leave requests: {context['total_requests']}")
    print(f"System Health: {'Included' if context.get('show_system_health') else 'Hidden'}")
    print(f"Action: {action_label}")
    if hr_recipient_count is not None:
        print(f"HR recipients: {hr_recipient_count}")
    print("-" * 56)


def _print_hr_recipients(hr_emails):
    print("\nHR recipients:")
    if not hr_emails:
        print("- No active HR email recipients found.")
        return

    for index, email in enumerate(hr_emails, start=1):
        print(f"{index}. {email}")


def _ask_audit_reason(action_label):
    while True:
        reason = input(f"Enter audit reason for {action_label} (B=Back, 0=Exit): ").strip()
        lowered = reason.lower()
        if lowered in {"b", "back"}:
            return "BACK"
        if lowered in {"0", "c", "cancel", "q", "quit"}:
            return None
        if reason:
            return reason
        print("Audit reason is required.")


def _record_weekly_report_audit(action, context, *, result, reason, output_path=None, hr_emails=None, error_message=None):
    changes = {
        "period": {
            "start": context.get("period_start_iso"),
            "end": context.get("period_end_iso"),
        },
        "employee_scope": context.get("selected_employee_scope"),
        "selected_employee_count": context.get("selected_employee_count"),
        "leave_requests": context.get("total_requests"),
        "system_health": "included" if context.get("show_system_health") else "hidden",
        "result": result,
    }
    if output_path:
        changes["output_path"] = str(output_path)
    if hr_emails is not None:
        changes["hr_recipients"] = list(hr_emails)
    if error_message:
        changes["error"] = error_message

    AdminAuditLog.objects.create(
        model_label="WeeklyReportService",
        object_id=f"{context.get('period_start_iso')}:{context.get('period_end_iso')}",
        object_repr=f"Weekly report {context.get('period_start')} - {context.get('period_end')}",
        action=action,
        updated_by=None,
        reason=reason,
        changes=changes,
    )


def build_manual_weekly_report_context_from_prompt(week="current", start_day=None, end_day=None):
    """
    Interactive selector for manual weekly report sends only.
    Scheduled/background sends should call send_weekly_hr_report() directly.
    """
    User = get_user_model()
    employees = list(
        User.objects.filter(role="EMPLOYEE", is_active=True)
        .select_related("profile")
        .order_by("first_name", "last_name", "username", "id")
    )

    if not employees:
        print("No active employees found. The report will include no employee rows.")
        include_system_health = _ask_include_system_health()
        return build_weekly_hr_report_context(
            week=week,
            start_day=start_day,
            end_day=end_day,
            include_system_health=include_system_health,
        )

    employee_by_number = {}
    employee_by_code = {}
    employee_entries = []
    for index, employee in enumerate(employees, start=1):
        profile = getattr(employee, "profile", None)
        employee_code = getattr(profile, "employee_id", "") if profile else ""
        employee_by_number[str(index)] = employee
        employee_entries.append((index, employee))
        if employee_code:
            employee_by_code[employee_code.lower()] = employee

    while True:
        print("\nSelect employee scope for this weekly report:")
        print("1. All employees")
        print("2. Single employee")
        print("3. Multiple employees")
        print("0. Exit")
        scope = input("Choose 1, 2, 3, or 0: ").strip().lower()

        if scope in {"c", "cancel", "q", "quit"}:
            return None

        if scope in {"", "1"}:
            print("Selected: All employees")
            include_system_health = _ask_include_system_health()
            return build_weekly_hr_report_context(
                week=week,
                start_day=start_day,
                end_day=end_day,
                include_system_health=include_system_health,
            )

        if scope not in {"2", "3"}:
            print("Invalid choice. Please select again.")
            continue

        if scope == "2":
            page = 1
            visible_entries = employee_entries
            search_active = False
            while True:
                page, total_pages = _print_employee_page(visible_entries, page, search_active=search_active)
                selected_text = input("\nEnter employee number/ID (B=Back, 0=Exit): ").strip()
                selected_key = selected_text.lower()
                if selected_key in {"n", "next"}:
                    if page >= total_pages:
                        print("Already on the last page.")
                    else:
                        page += 1
                    continue
                if selected_key in {"p", "prev", "previous"}:
                    if page <= 1:
                        print("Already on the first page.")
                    else:
                        page -= 1
                    continue
                if selected_key in {"s", "search"}:
                    search_results = _search_employee_entries(employee_entries)
                    if search_results:
                        visible_entries = search_results
                        search_active = True
                        page = 1
                    continue
                if selected_key in {"a", "all"} and search_active:
                    visible_entries = employee_entries
                    search_active = False
                    page = 1
                    continue
                if selected_key in {"b", "back"}:
                    break
                if selected_key in {"c", "cancel", "q", "quit"}:
                    return None

                selected_employee = employee_by_number.get(selected_text) or employee_by_code.get(selected_key)
                if not selected_employee:
                    print("Invalid employee selection. Try again, type B to go back, or C to cancel.")
                    continue

                print(f"Selected: {_employee_report_label(selected_employee)}")
                include_system_health = _ask_include_system_health()
                return build_weekly_hr_report_context(
                    week=week,
                    start_day=start_day,
                    end_day=end_day,
                    employee_ids=[selected_employee.id],
                    include_system_health=include_system_health,
                )

        if scope == "3":
            page = 1
            visible_entries = employee_entries
            search_active = False
            selected_employees = []
            selected_ids = set()
            while True:
                _print_selected_employees(selected_employees)
                page, total_pages = _print_employee_page(visible_entries, page, search_active=search_active)
                selected_text = input(
                    "\nEnter employee numbers/IDs to add, DONE to continue, REMOVE <number>, CLEAR, B=Back, 0=Exit: "
                ).strip()
                selected_key = selected_text.lower()
                if selected_key in {"n", "next"}:
                    if page >= total_pages:
                        print("Already on the last page.")
                    else:
                        page += 1
                    continue
                if selected_key in {"p", "prev", "previous"}:
                    if page <= 1:
                        print("Already on the first page.")
                    else:
                        page -= 1
                    continue
                if selected_key in {"s", "search"}:
                    search_results = _search_employee_entries(employee_entries)
                    if search_results:
                        visible_entries = search_results
                        search_active = True
                        page = 1
                    continue
                if selected_key in {"a", "all"} and search_active:
                    visible_entries = employee_entries
                    search_active = False
                    page = 1
                    continue
                if selected_key in {"b", "back"}:
                    break
                if selected_key in {"c", "cancel", "q", "quit"}:
                    return None
                if selected_key in {"clear", "reset"}:
                    selected_employees = []
                    selected_ids = set()
                    print("Selection cleared.")
                    continue
                if selected_key.startswith("remove "):
                    remove_text = selected_key.split(" ", 1)[1].strip()
                    if not remove_text.isdigit() or not (1 <= int(remove_text) <= len(selected_employees)):
                        print("Invalid remove number. Use REMOVE 1, REMOVE 2, etc.")
                        continue
                    removed = selected_employees.pop(int(remove_text) - 1)
                    selected_ids.discard(removed.id)
                    print(f"Removed: {_employee_report_label(removed)}")
                    continue
                if selected_key in {"done", "d", "continue"}:
                    if not selected_employees:
                        print("Select at least one employee before continuing.")
                        continue

                    print("Final selected employees:")
                    for employee in selected_employees:
                        print(f"- {_employee_report_label(employee)}")
                    include_system_health = _ask_include_system_health()
                    return build_weekly_hr_report_context(
                        week=week,
                        start_day=start_day,
                        end_day=end_day,
                        employee_ids=[employee.id for employee in selected_employees],
                        include_system_health=include_system_health,
                    )

                invalid_tokens = []
                added_employees = []

                for token in [part.strip() for part in selected_text.split(",") if part.strip()]:
                    employee = employee_by_number.get(token) or employee_by_code.get(token.lower())
                    if not employee:
                        invalid_tokens.append(token)
                        continue
                    if employee.id in selected_ids:
                        continue
                    selected_employees.append(employee)
                    selected_ids.add(employee.id)
                    added_employees.append(employee)

                if invalid_tokens:
                    print(f"Invalid selection: {', '.join(invalid_tokens)}")
                    print("Try again, type DONE to continue, B to go back, or C to cancel.")
                    continue

                if not added_employees:
                    print("No new employees added. Try again, type DONE to continue, B to go back, or C to cancel.")
                    continue

                print("Added:")
                for employee in added_employees:
                    print(f"- {_employee_report_label(employee)}")


def main():
    logger.info("WEEKLY_REPORT | MANUAL_RUN | Opened direct runner.")
    print("--- Weekly HR Report Manual Runner ---")
    print("This can send the weekly report email to HR or generate a PDF only.")
    period = _ask_report_period()
    if period is None:
        logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled by period selection.")
        print("Cancelled. Weekly report was not sent or generated.")
        return

    context = build_manual_weekly_report_context_from_prompt(
        week=period["week"],
        start_day=period["start_day"],
        end_day=period["end_day"],
    )
    if context is None:
        logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled by employee selection.")
        print("Cancelled. Weekly report was not sent or generated.")
        return

    while True:
        print("\nWhat do you want to do?")
        print("1. Send email to HR")
        print("2. Generate PDF only")
        print("3. Cancel")
        action = input("Choose 1, 2, or 3: ").strip().lower()

        if action in {"3", "c", "cancel", "q", "quit"}:
            logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled by action selection.")
            print("Cancelled. Weekly report was not sent or generated.")
            return

        if action in {"1", "send", "email"}:
            hr_emails = _get_active_hr_emails()
            _print_hr_recipients(hr_emails)
            if not hr_emails:
                logger.warning("WEEKLY_REPORT | MANUAL_RUN | Email send blocked because no active HR recipients exist.")
                print("Cannot send email because no active HR users with email addresses were found.")
                print("Choose PDF-only or add an active HR email first.")
                continue

            _print_report_summary(context, "Send email to HR", hr_recipient_count=len(hr_emails))
            audit_reason = _ask_audit_reason("weekly report email send")
            if audit_reason == "BACK":
                continue
            if audit_reason is None:
                logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled email by audit reason prompt.")
                print("Cancelled. Weekly report was not sent.")
                return

            print("Confirmation is case-sensitive. Type SEND to send, or anything else to cancel.")
            confirmation = input("Type SEND to continue: ").strip()
            if confirmation != "SEND":
                logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled email by confirmation.")
                print("Cancelled. Weekly report was not sent.")
                return

            logger.info("WEEKLY_REPORT | MANUAL_RUN | Email confirmation accepted.")
            sent = send_weekly_hr_report(context=context)
            _record_weekly_report_audit(
                "SERVICE_WEEKLY_SEND",
                context,
                result="success" if sent else "failed",
                reason=audit_reason,
                hr_emails=hr_emails,
            )
            if sent:
                print("SUCCESS: Weekly HR report sent.")
                print("Audit log: Created")
            else:
                print("FAILED: Weekly HR report was not sent. Check logs/settings.")
                print("Audit log: Created")
            return

        if action in {"2", "pdf", "generate"}:
            _print_report_summary(context, "Generate PDF only")
            audit_reason = _ask_audit_reason("weekly report PDF generation")
            if audit_reason == "BACK":
                continue
            if audit_reason is None:
                logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled PDF by audit reason prompt.")
                print("Cancelled. Weekly report PDF was not generated.")
                return

            print("Confirmation is case-sensitive. Type PDF to generate, or anything else to cancel.")
            confirmation = input("Type PDF to continue: ").strip()
            if confirmation != "PDF":
                logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled PDF by confirmation.")
                print("Cancelled. Weekly report PDF was not generated.")
                return

            try:
                logger.info("WEEKLY_REPORT | MANUAL_RUN | PDF-only confirmation accepted.")
                output_path = generate_weekly_hr_report_pdf_file(context=context)
            except Exception as exc:
                logger.exception("WEEKLY_REPORT | PDF_ONLY | Failed to generate weekly report PDF")
                _record_weekly_report_audit(
                    "SERVICE_WEEKLY_PDF",
                    context,
                    result="failed",
                    reason=audit_reason,
                    error_message=str(exc),
                )
                print("FAILED: Weekly report PDF was not generated. Check logs/settings.")
                print("Audit log: Created")
                return

            _record_weekly_report_audit(
                "SERVICE_WEEKLY_PDF",
                context,
                result="success",
                reason=audit_reason,
                output_path=output_path,
            )
            print(f"SUCCESS: Weekly HR report PDF generated: {output_path}")
            print("Audit log: Created")
            return

        print("Invalid choice. Choose 1, 2, or 3.")


if __name__ == "__main__":
    main()
