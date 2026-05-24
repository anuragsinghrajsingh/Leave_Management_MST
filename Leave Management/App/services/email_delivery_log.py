import logging
import os
import sys
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

from django.conf import settings
from django.core.mail import EmailMessage
from django.db.models import Count, Q
from django.utils import timezone

from App.models import AdminAuditLog, EmailDeliveryLog


logger = logging.getLogger("lms_email")
PAGE_SIZE = 10


def normalize_recipients(recipients):
    if not recipients:
        return []
    if isinstance(recipients, str):
        return [recipients]
    return [recipient for recipient in recipients if recipient]


def record_email_delivery(
    *,
    subject,
    recipients,
    status,
    email_type="general",
    from_email="",
    error_message="",
    related_user=None,
    related_leave=None,
    triggered_by=None,
    metadata=None,
):
    rows = []
    metadata = metadata or {}
    resolved_error_message = error_message or ("No error" if status == "sent" else "")
    for recipient in normalize_recipients(recipients):
        rows.append(
            EmailDeliveryLog(
                email_type=email_type[:80],
                subject=(subject or "")[:255],
                from_email=(from_email or "")[:255],
                recipient=recipient,
                status=status,
                error_message=resolved_error_message,
                related_user=related_user,
                related_leave=related_leave,
                triggered_by=triggered_by,
                metadata=metadata,
            )
        )

    if not rows:
        return 0

    try:
        EmailDeliveryLog.objects.bulk_create(rows)
        return len(rows)
    except Exception:
        logger.exception("EMAIL_DELIVERY_LOG_WRITE_FAILED | subject=%s | status=%s", subject, status)
        return 0


def _safe_input(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return "0"


def _format_datetime(value):
    if not value:
        return "-"
    return timezone.localtime(value).strftime("%Y-%m-%d %H:%M")


def _user_label(user):
    if not user:
        return "-"
    employee_id = getattr(getattr(user, "profile", None), "employee_id", "")
    if employee_id:
        return f"{user.get_full_name() or user.username} ({user.username}, {employee_id})"
    return f"{user.get_full_name() or user.username} ({user.username})"


def _print_log_row(index, log):
    print(
        f"{index}. #{log.id} | {log.status.upper()} | {log.email_type} | "
        f"{log.recipient} | {_format_datetime(log.created_at)}"
    )
    print(f"   Subject: {log.subject or '-'}")
    if log.related_user_id:
        print(f"   User: {_user_label(log.related_user)}")
    if log.error_message and log.status == "failed":
        print(f"   Error: {log.error_message[:160]}")


def _print_log_detail(log):
    print("\nEmail Delivery Detail")
    print(f"ID: #{log.id}")
    print(f"Status: {log.status}")
    print(f"Type: {log.email_type}")
    print(f"Subject: {log.subject or '-'}")
    print(f"From: {log.from_email or '-'}")
    print(f"Recipient: {log.recipient}")
    print(f"Created: {_format_datetime(log.created_at)}")
    print(f"Related user: {_user_label(log.related_user)}")
    print(f"Related leave: #{log.related_leave_id}" if log.related_leave_id else "Related leave: -")
    print(f"Triggered by: {_user_label(log.triggered_by)}")
    print(f"Error: {log.error_message or '-'}")
    print(f"Metadata: {log.metadata or {}}")


def _base_queryset():
    return EmailDeliveryLog.objects.select_related("related_user__profile", "related_leave", "triggered_by__profile")


def _list_logs(qs, *, title):
    page = 1
    while True:
        total = qs.count()
        total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = max(1, min(page, total_pages))
        start = (page - 1) * PAGE_SIZE
        logs = list(qs[start:start + PAGE_SIZE])

        print(f"\n{title}")
        print(f"Showing page {page}/{total_pages} | Total: {total}")
        if not logs:
            print("No email logs found.")
        for offset, log in enumerate(logs, start=1):
            _print_log_row(start + offset, log)

        print("\nN = Next page | P = Previous page | ID = View detail | B = Back | 0 = Exit")
        choice = _safe_input("Choose: ").lower()
        if choice == "0":
            return "exit"
        if choice == "b":
            return None
        if choice == "n":
            if page < total_pages:
                page += 1
            else:
                print("Already on the last page.")
            continue
        if choice == "p":
            if page > 1:
                page -= 1
            else:
                print("Already on the first page.")
            continue
        if choice.isdigit():
            log = EmailDeliveryLog.objects.filter(id=int(choice)).select_related(
                "related_user__profile", "related_leave", "triggered_by__profile"
            ).first()
            if not log:
                print("Email log not found.")
                continue
            _print_log_detail(log)
            _safe_input("\nPress Enter to continue...")
            continue
        print("Invalid choice.")


def _search_logs(status=None):
    term = _safe_input("Search subject, recipient, type, username, employee ID, or error (B=Back, 0=Exit): ").strip()
    if term.lower() == "0":
        return "exit"
    if term.lower() == "b":
        return None
    qs = _base_queryset()
    if status:
        qs = qs.filter(status=status)
    if term:
        qs = qs.filter(
            Q(subject__icontains=term)
            | Q(recipient__icontains=term)
            | Q(email_type__icontains=term)
            | Q(error_message__icontains=term)
            | Q(related_user__username__icontains=term)
            | Q(related_user__email__icontains=term)
            | Q(related_user__profile__employee_id__icontains=term)
        )
    return _list_logs(qs, title=f"Search results for '{term or 'all'}'")


def _show_summary():
    print("\nEmail Delivery Summary")
    total = EmailDeliveryLog.objects.count()
    sent = EmailDeliveryLog.objects.filter(status="sent").count()
    failed = EmailDeliveryLog.objects.filter(status="failed").count()
    print(f"Total logs: {total}")
    print(f"Sent: {sent}")
    print(f"Failed: {failed}")

    print("\nBy email type:")
    rows = (
        EmailDeliveryLog.objects.values("email_type", "status")
        .annotate(count=Count("id"))
        .order_by("email_type", "status")
    )
    if not rows:
        print("-")
    for row in rows:
        print(f"{row['email_type']} | {row['status']}: {row['count']}")
    _safe_input("\nPress Enter to continue...")


def _get_log_by_id(prompt="Enter email log ID (B=Back, 0=Exit): "):
    raw_id = _safe_input(prompt).lower()
    if raw_id == "0":
        return "exit"
    if raw_id == "b":
        return None
    if not raw_id.isdigit():
        print("Enter a valid numeric email log ID.")
        return None
    log = _base_queryset().filter(id=int(raw_id)).first()
    if not log:
        print("Email log not found.")
        return None
    return log


def _send_retry_notice():
    log = _get_log_by_id("Enter failed email log ID to send retry notice (B=Back, 0=Exit): ")
    if log in {None, "exit"}:
        return log
    if log.status != "failed":
        print("This log is not failed. Retry notice is only for failed email logs.")
        return None

    _print_log_detail(log)
    print("\nThis will not recreate the exact original email body.")
    print("It sends a simple notice that the previous email is being retried/checked.")

    reason = _safe_input("Audit reason (B=Back, 0=Exit): ")
    if reason.lower() == "0":
        return "exit"
    if reason.lower() == "b":
        return None
    if not reason:
        print("Reason is required.")
        return None

    confirmation = _safe_input("Type SEND to send retry notice (B=Back, 0=Exit): ")
    if confirmation.lower() == "0":
        return "exit"
    if confirmation.lower() == "b":
        return None
    if confirmation != "SEND":
        print("Retry cancelled.")
        return None

    subject = f"Retry notice: {log.subject or 'Email notification'}"
    body = (
        "Hello,\n\n"
        "This is a retry/check notice from the Leave Management email system.\n\n"
        f"Original email type: {log.email_type}\n"
        f"Original subject: {log.subject or '-'}\n"
        f"Original failed at: {_format_datetime(log.created_at)}\n\n"
        "If you still do not receive the expected original message, please contact HR/admin.\n"
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "")

    try:
        EmailMessage(subject, body, from_email, [log.recipient]).send(fail_silently=False)
        record_email_delivery(
            subject=subject,
            recipients=[log.recipient],
            status="sent",
            email_type=f"retry_{log.email_type}"[:80],
            from_email=from_email,
            related_user=log.related_user,
            related_leave=log.related_leave,
            metadata={"original_email_log_id": log.id},
        )
        AdminAuditLog.objects.create(
            model_label="EmailDeliveryLog",
            object_id=str(log.id),
            object_repr=str(log),
            action="EMAIL_RETRY",
            reason=reason,
            changes={
                "recipient": log.recipient,
                "email_type": log.email_type,
                "retry_notice": "sent",
            },
        )
        print("Retry notice sent.")
    except Exception as exc:
        logger.exception("EMAIL_RETRY_NOTICE_FAILED | email_log_id=%s", log.id)
        record_email_delivery(
            subject=subject,
            recipients=[log.recipient],
            status="failed",
            email_type=f"retry_{log.email_type}"[:80],
            from_email=from_email,
            error_message=str(exc),
            related_user=log.related_user,
            related_leave=log.related_leave,
            metadata={"original_email_log_id": log.id},
        )
        print(f"Retry notice failed: {exc}")

    _safe_input("\nPress Enter to continue...")
    return None


def run_interactive():
    while True:
        print("\nEmail Delivery Log")
        print("1. View latest email logs")
        print("2. View failed email logs")
        print("3. Search email logs")
        print("4. View email log by ID")
        print("5. Send retry notice for failed log")
        print("6. Summary")
        print("0. Exit")

        choice = _safe_input("Choose an option: ").lower()
        if choice in {"0", "exit", "q", "quit"}:
            print("Exit.")
            return 0
        if choice == "1":
            result = _list_logs(_base_queryset(), title="Latest email logs")
        elif choice == "2":
            result = _list_logs(_base_queryset().filter(status="failed"), title="Failed email logs")
        elif choice == "3":
            result = _search_logs()
        elif choice == "4":
            log = _get_log_by_id()
            if log == "exit":
                result = "exit"
            elif log:
                _print_log_detail(log)
                _safe_input("\nPress Enter to continue...")
                result = None
            else:
                result = None
        elif choice == "5":
            result = _send_retry_notice()
        elif choice == "6":
            _show_summary()
            result = None
        else:
            print("Invalid choice.")
            continue

        if result == "exit":
            print("Exit.")
            return 0


if __name__ == "__main__":
    raise SystemExit(run_interactive())
