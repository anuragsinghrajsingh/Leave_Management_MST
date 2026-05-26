import logging
import os
import sys
from email.mime.image import MIMEImage

if __name__ == "__main__":
    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if _PROJECT_ROOT not in sys.path:
        sys.path.insert(0, _PROJECT_ROOT)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.db.models import Q
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localtime, now

from App.models import AdminAuditLog, Communication, EmailDeliveryLog
from App.services.email_delivery_log import record_email_delivery


logger = logging.getLogger("lms_email")
WELCOME_LOGO_CID = "welcome_logo"
PAGE_SIZE = 10
BACK = object()
EXIT = object()


def _employee_display_name(user):
    return user.get_full_name().strip() or user.username


def _portal_url(user=None):
    base_url = getattr(settings, "PORTAL_BASE_URL", "").rstrip("/")
    role = getattr(user, "role", "EMPLOYEE")
    route_name = {
        "Admin": "admin_login",
        "HR": "hr_login",
        "EMPLOYEE": "employee_login",
    }.get(role, "employee_login")
    if base_url:
        return base_url + reverse(route_name)
    return reverse(route_name)


def _format_leave_value(value):
    try:
        numeric_value = float(value or 0)
    except (TypeError, ValueError):
        numeric_value = 0
    return f"{numeric_value:g}"


def _get_leave_summary(user):
    try:
        balance = user.leavebalance
    except Exception:
        balance = None

    if not balance:
        return {
            "total": "0",
            "remaining": "0",
            "sick_total": "0",
            "earned_total": "0",
        }

    return {
        "total": _format_leave_value(balance.total_leave_balance),
        "remaining": _format_leave_value(balance.total_leave_remaining),
        "sick_total": _format_leave_value(balance.sick_total),
        "earned_total": _format_leave_value(balance.earned_total),
    }


def _build_welcome_body(user, profile, leave_summary):
    role = getattr(user, "role", "EMPLOYEE")
    employee_id = getattr(profile, "employee_id", "") or "your employee ID"
    department = getattr(profile, "department", "") or "your department"
    joining_date = getattr(profile, "date_of_joining", None)
    joining_text = joining_date.strftime("%d %b %Y") if joining_date else "your joining date"
    portal_label = {
        "Admin": "admin portal",
        "HR": "HR portal",
        "EMPLOYEE": "employee portal",
    }.get(role, "portal")

    body = (
        f"Welcome to MS Technology, {_employee_display_name(user)}!\n\n"
        "Your user profile has been created successfully.\n\n"
        f"Employee ID: {employee_id}\n"
        f"Department: {department}\n"
        f"Date of joining: {joining_text}\n\n"
    )

    if role == "EMPLOYEE":
        body += (
        "Assigned leave:\n"
        f"Total leave: {leave_summary['total']} days\n"
        f"Sick leave: {leave_summary['sick_total']} days\n"
        f"Earned leave: {leave_summary['earned_total']} days\n"
        f"Current remaining balance: {leave_summary['remaining']} days\n\n"
        )

    body += (
        f"You can now log in to the {portal_label}. If your account is marked for first-login password change, "
        "you will be asked to update your password before continuing."
    )
    return body


def send_employee_welcome_package(employee, triggered_by=None, force_resend=False):
    """
    Sends the one-time welcome communication for a newly created user.
    Returns a small result dict so callers can show a useful status message.
    """
    if not employee:
        return {"sent": False, "email_sent": False, "skipped": True, "reason": "missing_user"}

    try:
        profile = employee.profile
    except Exception:
        return {"sent": False, "email_sent": False, "skipped": True, "reason": "missing_profile"}

    if profile.welcome_sent_at and not force_resend:
        return {"sent": False, "email_sent": False, "skipped": True, "reason": "already_sent"}

    sender = triggered_by if getattr(triggered_by, "is_authenticated", False) else None
    if sender is None:
        sender = employee

    title = "Welcome to MS Technology"
    leave_summary = _get_leave_summary(employee)
    body = _build_welcome_body(employee, profile, leave_summary)
    email_sent = False
    email_error = ""

    with transaction.atomic():
        profile = type(profile).objects.select_for_update().get(pk=profile.pk)
        if profile.welcome_sent_at and not force_resend:
            return {"sent": False, "email_sent": False, "skipped": True, "reason": "already_sent"}

        Communication.objects.create(
            sender=sender,
            recipient=employee,
            message_type="DIRECT",
            title=title,
            body=body,
        )

        profile.welcome_sent_at = now()
        profile.save(update_fields=["welcome_sent_at"])

    if employee.email:
        from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
        context = {
            "employee": employee,
            "profile": profile,
            "leave_summary": leave_summary,
            "display_name": _employee_display_name(employee),
            "portal_url": _portal_url(employee),
            "portal_label": {
                "Admin": "Admin Portal",
                "HR": "HR Portal",
                "EMPLOYEE": "Employee Portal",
            }.get(getattr(employee, "role", "EMPLOYEE"), "Portal"),
            "show_leave_summary": getattr(employee, "role", None) == "EMPLOYEE",
            "sent_at": localtime(now()),
            "logo_cid": WELCOME_LOGO_CID,
        }
        html_body = render_to_string("emails/welcome_employee.html", context)

        try:
            email = EmailMultiAlternatives(
                subject=title,
                body=body,
                from_email=from_email or None,
                to=[employee.email],
            )
            email.attach_alternative(html_body, "text/html")
            logo_path = os.path.join(settings.BASE_DIR, "static", "images", "ms-technology-logo.png")
            if os.path.exists(logo_path):
                with open(logo_path, "rb") as logo_file:
                    logo = MIMEImage(logo_file.read())
                    logo.add_header("Content-ID", f"<{WELCOME_LOGO_CID}>")
                    logo.add_header("Content-Disposition", "inline", filename="ms-technology-logo.png")
                    email.attach(logo)
            email.send(fail_silently=False)
            email_sent = True
            record_email_delivery(
                subject=title,
                recipients=[employee.email],
                status="sent",
                email_type="employee_welcome",
                from_email=from_email,
                related_user=employee,
                triggered_by=triggered_by if getattr(triggered_by, "is_authenticated", False) else None,
            )
        except Exception as exc:
            email_error = str(exc)
            logger.exception("EMPLOYEE_WELCOME_EMAIL_FAILED | user_id=%s | email=%s", employee.pk, employee.email)
            record_email_delivery(
                subject=title,
                recipients=[employee.email],
                status="failed",
                email_type="employee_welcome",
                from_email=from_email,
                error_message=email_error,
                related_user=employee,
                triggered_by=triggered_by if getattr(triggered_by, "is_authenticated", False) else None,
            )
    else:
        email_error = "Employee email is missing."

    return {
        "sent": True,
        "email_sent": email_sent,
        "skipped": False,
        "email_error": email_error,
    }


def _employee_queryset():
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return (
        User.objects.filter(role="EMPLOYEE")
        .select_related("profile")
        .order_by("profile__employee_id", "username", "id")
    )


def _last_welcome_email(user):
    return (
        EmailDeliveryLog.objects.filter(related_user=user, email_type="employee_welcome")
        .order_by("-created_at", "-id")
        .first()
    )


def _welcome_package_status(user):
    profile = getattr(user, "profile", None)
    return "Sent" if getattr(profile, "welcome_sent_at", None) else "Not sent"


def _last_email_status_text(user):
    last_email = _last_welcome_email(user)
    if not last_email:
        return "No log"
    return last_email.status.title()


def _employee_id(user):
    profile = getattr(user, "profile", None)
    return getattr(profile, "employee_id", "") or "-"


def _prompt_menu(prompt, choices, *, allow_back=True, allow_exit=True):
    valid_choices = {str(choice).lower() for choice in choices}
    while True:
        value = input(prompt).strip()
        lowered = value.lower()
        if allow_back and lowered in {"b", "back"}:
            return BACK
        if allow_exit and lowered in {"0", "exit", "q", "quit"}:
            return EXIT
        if lowered in valid_choices:
            return lowered

        options = sorted(valid_choices)
        if allow_back:
            options.append("B")
        if allow_exit:
            options.append("0")
        print("Invalid choice. Select one of:", ", ".join(options))


def _prompt_required_reason(action_label):
    while True:
        reason = input(f"Audit reason for {action_label} (B=Back, 0=Exit): ").strip()
        lowered = reason.lower()
        if lowered in {"b", "back"}:
            return BACK
        if lowered in {"0", "exit", "q", "quit"}:
            return EXIT
        if reason:
            return reason
        print("Audit reason is required.")


def _print_employee_row(index, user):
    print(
        f"{index}. {_employee_id(user)} | {_employee_display_name(user)} | {user.username} | {user.email or '-'}"
    )
    print(
        f"   Welcome package: {_welcome_package_status(user)} | Last email: {_last_email_status_text(user)}"
    )


def _display_employee_details(user):
    profile = getattr(user, "profile", None)
    last_email = _last_welcome_email(user)
    welcome_sent_at = getattr(profile, "welcome_sent_at", None)
    sent_text = localtime(welcome_sent_at).strftime("%d %b %Y, %I:%M %p") if welcome_sent_at else "-"

    print("\nEmployee details")
    print("-" * 54)
    print(f"DB ID: {user.pk}")
    print(f"Username: {user.username}")
    print(f"Full name: {_employee_display_name(user)}")
    print(f"Email: {user.email or '-'}")
    print(f"Employee ID: {_employee_id(user)}")
    print(f"Department: {getattr(profile, 'department', '') or '-'}")
    print(f"Phone: {getattr(profile, 'phone', '') or '-'}")
    print(f"Active: {'Yes' if user.is_active else 'No'}")
    print(f"Welcome package: {_welcome_package_status(user)}")
    print(f"Welcome sent at: {sent_text}")

    if last_email:
        email_time = localtime(last_email.created_at).strftime("%d %b %Y, %I:%M %p")
        print(f"Last welcome email: {last_email.status.title()} at {email_time}")
        if last_email.error_message:
            print(f"Last email error: {last_email.error_message}")
    else:
        print("Last welcome email: No log")
    print("-" * 54)


def _record_welcome_audit(user, action, reason, changes):
    AdminAuditLog.objects.create(
        model_label="App.Profile",
        object_id=str(user.profile.pk),
        object_repr=str(user.profile),
        action=action,
        updated_by=None,
        reason=reason,
        changes=changes,
    )


def _send_or_resend_welcome(user):
    reason = _prompt_required_reason("welcome resend")
    if reason in {BACK, EXIT}:
        return reason

    confirmation = input("Type SEND to send/resend welcome package: ").strip()
    if confirmation != "SEND":
        print("Cancelled.")
        return None

    old_value = getattr(user.profile, "welcome_sent_at", None)
    result = send_employee_welcome_package(user, force_resend=True)
    user.profile.refresh_from_db(fields=["welcome_sent_at"])
    new_value = user.profile.welcome_sent_at
    _record_welcome_audit(
        user,
        "WELCOME_RESEND",
        reason,
        {
            "welcome_sent_at": {
                "old": old_value.isoformat() if old_value else None,
                "new": new_value.isoformat() if new_value else None,
            },
            "email_sent": {"old": None, "new": bool(result.get("email_sent"))},
        },
    )

    print("\nWelcome package result")
    print("-" * 54)
    print(f"Notification: {'Created' if result.get('sent') else 'Not created'}")
    print(f"Email: {'Sent' if result.get('email_sent') else 'Failed/skipped'}")
    if result.get("email_error"):
        print(f"Email error: {result['email_error']}")
    print("Audit: Recorded")
    print("-" * 54)
    return None


def _mark_welcome_not_sent(user):
    reason = _prompt_required_reason("mark welcome as not sent")
    if reason in {BACK, EXIT}:
        return reason

    confirmation = input("Type RESET to clear welcome sent status: ").strip()
    if confirmation != "RESET":
        print("Cancelled.")
        return None

    with transaction.atomic():
        profile = type(user.profile).objects.select_for_update().get(pk=user.profile.pk)
        old_value = profile.welcome_sent_at
        profile.welcome_sent_at = None
        profile.save(update_fields=["welcome_sent_at"])

    user.profile.refresh_from_db(fields=["welcome_sent_at"])
    _record_welcome_audit(
        user,
        "WELCOME_RESET",
        reason,
        {
            "welcome_sent_at": {
                "old": old_value.isoformat() if old_value else None,
                "new": None,
            }
        },
    )
    print("Welcome sent status cleared. Audit recorded.")
    return None


def _employee_actions(user):
    while True:
        _display_employee_details(user)
        print("\nActions")
        print("1. Send/resend welcome package")
        print("2. Mark welcome as not sent")
        print("B. Back")
        print("0. Exit")
        choice = _prompt_menu("Select option: ", {"1", "2"})

        if choice is BACK:
            return None
        if choice is EXIT:
            return EXIT
        if choice == "1":
            result = _send_or_resend_welcome(user)
        else:
            result = _mark_welcome_not_sent(user)

        if result is EXIT:
            return EXIT
        if result is BACK:
            continue
        input("\nPress Enter to continue...")


def _list_employees():
    page = 0

    while True:
        queryset = _employee_queryset()
        total = queryset.count()
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        employees = list(queryset[start:end])

        if total == 0:
            print("No employees found.")
            return None

        print(f"\nShowing employees {start + 1}-{min(end, total)} of {total}")
        print("-" * 54)
        for index, employee in enumerate(employees, start=1):
            _print_employee_row(index, employee)

        print("\nNumber = select employee | N = Next page | P = Previous page | B = Back | 0 = Exit")
        valid_numbers = {str(number) for number in range(1, len(employees) + 1)}
        choice = _prompt_menu("Select option: ", valid_numbers | {"n", "p"})

        if choice is BACK:
            return None
        if choice is EXIT:
            return EXIT
        if choice == "n":
            if end >= total:
                print("Already on the last page.")
            else:
                page += 1
            continue
        if choice == "p":
            if page == 0:
                print("Already on the first page.")
            else:
                page -= 1
            continue

        selected = employees[int(choice) - 1]
        result = _employee_actions(selected)
        if result is EXIT:
            return EXIT


def _search_employees():
    while True:
        term = input("Search by name, username, email, employee ID, or phone (B=Back, 0=Exit): ").strip()
        lowered = term.lower()
        if lowered in {"b", "back"}:
            return None
        if lowered in {"0", "exit", "q", "quit"}:
            return EXIT
        if not term:
            print("Search cannot be blank.")
            continue

        results = list(
            _employee_queryset()
            .filter(
                Q(username__icontains=term)
                | Q(first_name__icontains=term)
                | Q(last_name__icontains=term)
                | Q(email__icontains=term)
                | Q(profile__employee_id__icontains=term)
                | Q(profile__phone__icontains=term)
            )
            .distinct()[:PAGE_SIZE]
        )

        if not results:
            print("No matching employees found.")
            continue

        print(f"\nFound {len(results)} employee(s)")
        print("-" * 54)
        for index, employee in enumerate(results, start=1):
            _print_employee_row(index, employee)

        valid_numbers = {str(number) for number in range(1, len(results) + 1)}
        choice = _prompt_menu("Select employee number (B=Back, 0=Exit): ", valid_numbers)
        if choice is BACK:
            continue
        if choice is EXIT:
            return EXIT

        result = _employee_actions(results[int(choice) - 1])
        if result is EXIT:
            return EXIT


def run_interactive():
    print("\nEmployee Welcome Service")
    print("Use this tool to list employees and send/resend welcome packages.")

    while True:
        print("\nMain menu")
        print("1. List employees")
        print("2. Search employee")
        print("0. Exit")
        choice = _prompt_menu("Select option: ", {"1", "2"}, allow_back=False)

        if choice is EXIT:
            print("Exiting Employee Welcome Service.")
            return 0
        if choice == "1":
            result = _list_employees()
        else:
            result = _search_employees()

        if result is EXIT:
            print("Exiting Employee Welcome Service.")
            return 0


if __name__ == "__main__":
    raise SystemExit(run_interactive())
