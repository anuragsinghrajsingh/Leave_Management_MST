import logging
import os
from email.mime.image import MIMEImage

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localtime, now

from App.models import Communication
from App.services.email_delivery_log import record_email_delivery


logger = logging.getLogger("lms_email")
WELCOME_LOGO_CID = "welcome_logo"


def _employee_display_name(user):
    return user.get_full_name().strip() or user.username


def _portal_url():
    base_url = getattr(settings, "PORTAL_BASE_URL", "").rstrip("/")
    if base_url:
        return base_url + reverse("employee_login")
    return reverse("employee_login")


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
    employee_id = getattr(profile, "employee_id", "") or "your employee ID"
    department = getattr(profile, "department", "") or "your department"
    joining_date = getattr(profile, "date_of_joining", None)
    joining_text = joining_date.strftime("%d %b %Y") if joining_date else "your joining date"

    return (
        f"Welcome to MS Technology, {_employee_display_name(user)}!\n\n"
        "Your employee profile has been created successfully.\n\n"
        f"Employee ID: {employee_id}\n"
        f"Department: {department}\n"
        f"Date of joining: {joining_text}\n\n"
        "Assigned leave:\n"
        f"Total leave: {leave_summary['total']} days\n"
        f"Sick leave: {leave_summary['sick_total']} days\n"
        f"Earned leave: {leave_summary['earned_total']} days\n"
        f"Current remaining balance: {leave_summary['remaining']} days\n\n"
        "You can now log in to the employee portal and start using the leave management system."
    )


def send_employee_welcome_package(employee, triggered_by=None):
    """
    Sends the one-time welcome communication for a newly created employee.
    Returns a small result dict so callers can show a useful status message.
    """
    if not employee or getattr(employee, "role", None) != "EMPLOYEE":
        return {"sent": False, "email_sent": False, "skipped": True, "reason": "not_employee"}

    try:
        profile = employee.profile
    except Exception:
        return {"sent": False, "email_sent": False, "skipped": True, "reason": "missing_profile"}

    if profile.welcome_sent_at:
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
        if profile.welcome_sent_at:
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
            "portal_url": _portal_url(),
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
