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
from App.models import Leave, Profile
from App.services.uptime_tracker import format_current_uptime
from App.views import send_branded_email

logger = logging.getLogger('lms_service_weekly_report')


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

def build_weekly_hr_report_context():
    """
    Compiles data for the 'Human Capital Operational Snapshot'.
    """
    User = get_user_model()
    today = timezone.localdate()
    start_date = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())) - timedelta(days=7)
    logger.info("WEEKLY_REPORT | CONTEXT | Building report context | Start=%s | End=%s", start_date, today)

    # 1. Compile Global Analytics (Past 7 Days)
    all_employees = User.objects.filter(role="EMPLOYEE", is_active=True)
    leave_queryset = Leave.objects.filter(
        created_at__gte=start_date,
        user__is_active=True,
    ).select_related("reviewed_by")
    
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
        
        # Get Leave Balance data
        from App.models import LeaveBalance
        balance = LeaveBalance.objects.filter(user=report_user).first()
        
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
    system_health = _build_system_health(today, start_date)

    context = {
        "period_start": start_date.strftime("%b %d, %Y"),
        "period_end": today.strftime("%b %d, %Y"),
        "total_requests": total_requests,
        "approved_total": approved_total,
        "pending_total": pending_total,
        "rejected_total": rejected_total,
        "employee_count": employee_applied_count,
        "reports": reports,
        "system_health": system_health,
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


def render_weekly_hr_report_html(context=None):
    logger.info("WEEKLY_REPORT | RENDER | Rendering dashboard HTML.")
    context = context or build_weekly_hr_report_context()
    return render_to_string('emails/weekly_hr_report.html', context)


def generate_weekly_hr_report_pdf_bytes():
    from App.services.pdf_generator import generate_pdf_from_html

    logger.info("WEEKLY_REPORT | PDF | Generating weekly report PDF bytes.")
    return generate_pdf_from_html(render_weekly_hr_report_html())


def send_weekly_hr_report():
    """
    Compiles data for the 'Human Capital Operational Snapshot' and sends it to all HR users.
    """
    User = get_user_model()
    today = timezone.localdate()
    start_date = timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())) - timedelta(days=7)

    # 1. Fetch HR Recipients
    hr_emails = list(User.objects.filter(role="HR", is_active=True).values_list("email", flat=True))
    logger.info("WEEKLY_REPORT | EMAIL | Active HR recipient count=%s", len(hr_emails))
    if not hr_emails:
        logger.warning("REPORT | No active HR emails found. Skipping weekly report.")
        return False

    context = build_weekly_hr_report_context()

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
        subject = f"Weekly Operational Snapshot: {start_date.strftime('%d %b')} - {today.strftime('%d %b, %Y')}"
        email = EmailMessage(
            subject=subject,
            body=cover_html,
            from_email=f"HR Portal <{settings.DEFAULT_FROM_EMAIL}>",
            to=to_email,
        )
        email.content_subtype = "html"
        
        # Attach the PDF
        filename = f"HR_Snapshot_{today.strftime('%Y%m%d')}.pdf"
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
        logger.error(f"REPORTS | FAILED | Could not send weekly report PDF: {e}")
        return False


def main():
    logger.info("WEEKLY_REPORT | MANUAL_RUN | Opened direct runner.")
    print("--- Weekly HR Report Manual Runner ---")
    print("This will send the weekly report email to all active HR users.")
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = input("Type SEND to continue: ").strip()

    if confirmation != "SEND":
        logger.info("WEEKLY_REPORT | MANUAL_RUN | Cancelled by confirmation.")
        print("Cancelled. Weekly report was not sent.")
        return

    logger.info("WEEKLY_REPORT | MANUAL_RUN | Confirmation accepted.")
    sent = send_weekly_hr_report()
    if sent:
        print("SUCCESS: Weekly HR report sent.")
    else:
        print("FAILED: Weekly HR report was not sent. Check logs/settings.")


if __name__ == "__main__":
    main()
