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

    django.setup()

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.timezone import localtime, now

from App.services.email_delivery_log import record_email_delivery


logger = logging.getLogger("lms_email")
FORCED_PASSWORD_ROLES = {"EMPLOYEE", "HR"}


def user_can_be_forced_to_change_password(user):
    return bool(user and getattr(user, "role", None) in FORCED_PASSWORD_ROLES)


def send_forced_password_email(user, event, triggered_by=None):
    if not user or not getattr(user, "email", ""):
        return False


def send_password_reset_email(user, triggered_by=None):
    if not user or not getattr(user, "email", ""):
        return False

    subject = "Your password was reset"
    display_name = user.get_full_name().strip() or user.username
    intro = (
        "Your account password was reset by an administrator. "
        "Use the new password shared with you securely to log in."
    )
    body = (
        "Your password was reset\n\n"
        f"{intro}\n\n"
        f"User: {display_name}\n"
        f"Username: {user.username}\n"
        f"Role: {user.role}\n"
        f"Time: {localtime(now()).strftime('%d %b %Y, %I:%M %p')}\n"
        "\nFor security, this email does not include the password.\n"
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    portal_path = "admin_login" if user.role == "Admin" else "hr_login" if user.role == "HR" else "employee_login"
    portal_url = (getattr(settings, "PORTAL_BASE_URL", "") or "").rstrip("/") + reverse(portal_path)
    triggered_by_name = ""
    if getattr(triggered_by, "is_authenticated", False):
        triggered_by_name = triggered_by.get_full_name().strip() or triggered_by.username

    html_body = render_to_string(
        "emails/forced_password_notification.html",
        {
            "status_label": "Password Reset",
            "status_class": "updated",
            "title": "Your password was reset",
            "intro_text": intro,
            "display_name": display_name,
            "username": user.username,
            "role": "Employee" if user.role == "EMPLOYEE" else user.role,
            "event_time": localtime(now()),
            "triggered_by_name": triggered_by_name,
            "portal_url": portal_url,
            "event": "reset",
        },
    )

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email or None,
            to=[user.email],
        )
        email.attach_alternative(html_body, "text/html")
        logo_path = os.path.join(settings.BASE_DIR, "static", "images", "ms-technology-logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as logo_file:
                logo = MIMEImage(logo_file.read())
                logo.add_header("Content-ID", "<logo_image>")
                logo.add_header("Content-Disposition", "inline", filename="ms-technology-logo.png")
                email.attach(logo)
        email.send(fail_silently=False)
        record_email_delivery(
            subject=subject,
            recipients=[user.email],
            status="sent",
            email_type="password_reset_notification",
            from_email=from_email,
            related_user=user,
            triggered_by=triggered_by,
        )
        return True
    except Exception as exc:
        logger.exception("PASSWORD_RESET_EMAIL_FAILED | user_id=%s", user.pk)
        record_email_delivery(
            subject=subject,
            recipients=[user.email],
            status="failed",
            email_type="password_reset_notification",
            from_email=from_email,
            error_message=str(exc),
            related_user=user,
            triggered_by=triggered_by,
        )
        return False

    event_map = {
        "forced": {
            "subject": "Password change required",
            "status_label": "Action Required",
            "status_class": "pending",
            "title": "Password change required",
            "intro": "Your account has been marked for password change. Please log in and update your password before continuing.",
        },
        "cleared": {
            "subject": "Password change requirement removed",
            "status_label": "Requirement Removed",
            "status_class": "updated",
            "title": "Password change requirement removed",
            "intro": "The password change requirement has been removed from your account. You can continue using the portal normally.",
        },
        "completed": {
            "subject": "Password changed successfully",
            "status_label": "Completed",
            "status_class": "approved",
            "title": "Password changed successfully",
            "intro": "Your password was changed successfully. If you did not perform this action, contact the administrator immediately.",
        },
    }
    config = event_map.get(event, event_map["forced"])
    subject = config["subject"]
    body = (
        f"{config['title']}\n\n"
        f"{config['intro']}\n\n"
        f"User: {user.get_full_name().strip() or user.username}\n"
        f"Username: {user.username}\n"
        f"Role: {user.role}\n"
        f"Time: {localtime(now()).strftime('%d %b %Y, %I:%M %p')}\n"
    )
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    portal_path = "admin_login" if user.role == "Admin" else "hr_login" if user.role == "HR" else "employee_login"
    portal_url = (getattr(settings, "PORTAL_BASE_URL", "") or "").rstrip("/") + reverse(portal_path)
    triggered_by_name = ""
    if getattr(triggered_by, "is_authenticated", False):
        triggered_by_name = triggered_by.get_full_name().strip() or triggered_by.username
    html_body = render_to_string(
        "emails/forced_password_notification.html",
        {
            "status_label": config["status_label"],
            "status_class": config["status_class"],
            "title": config["title"],
            "intro_text": config["intro"],
            "display_name": user.get_full_name().strip() or user.username,
            "username": user.username,
            "role": "Employee" if user.role == "EMPLOYEE" else user.role,
            "event_time": localtime(now()),
            "triggered_by_name": triggered_by_name,
            "portal_url": portal_url,
            "event": event,
        },
    )

    try:
        email = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=from_email or None,
            to=[user.email],
        )
        email.attach_alternative(html_body, "text/html")
        logo_path = os.path.join(settings.BASE_DIR, "static", "images", "ms-technology-logo.png")
        if os.path.exists(logo_path):
            with open(logo_path, "rb") as logo_file:
                logo = MIMEImage(logo_file.read())
                logo.add_header("Content-ID", "<logo_image>")
                logo.add_header("Content-Disposition", "inline", filename="ms-technology-logo.png")
                email.attach(logo)
        email.send(fail_silently=False)
        record_email_delivery(
            subject=subject,
            recipients=[user.email],
            status="sent",
            email_type=f"forced_password_{event}",
            from_email=from_email,
            related_user=user,
            triggered_by=triggered_by,
        )
        return True
    except Exception as exc:
        logger.exception("FORCED_PASSWORD_EMAIL_FAILED | user_id=%s | event=%s", user.pk, event)
        record_email_delivery(
            subject=subject,
            recipients=[user.email],
            status="failed",
            email_type=f"forced_password_{event}",
            from_email=from_email,
            error_message=str(exc),
            related_user=user,
            triggered_by=triggered_by,
        )
        return False


def _setup_django_for_cli():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def _prompt_choice(prompt, valid_choices):
    valid = {str(choice) for choice in valid_choices}
    while True:
        value = input(prompt).strip()
        if value in valid:
            return value
        print("Invalid choice. Please select one of:", ", ".join(sorted(valid)))


def _display_user_row(index, user):
    profile = getattr(user, "profile", None)
    employee_id = getattr(profile, "employee_id", "") or "-"
    full_name = user.get_full_name().strip() or "-"
    email = user.email or "-"
    status = "ON" if user.must_change_password else "OFF"
    print(f"{index}. DB ID: {user.pk} | {full_name} | {user.username} | {employee_id} | {email} | Force: {status}")


def _query_users_for_role(role):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return (
        User.objects.filter(role=role, is_active=True)
        .select_related("profile")
        .order_by("first_name", "last_name", "username", "id")
    )


def _list_users(role):
    users = list(_query_users_for_role(role)[:50])
    if not users:
        print(f"No {role} users found.")
        return []
    print(f"\nShowing first {len(users)} {role} users:")
    for index, user in enumerate(users, start=1):
        _display_user_row(index, user)
    return users


def _search_users(role):
    from django.db.models import Q

    term = input("Enter name, username, email, employee ID, or phone: ").strip()
    if not term:
        print("Search text cannot be blank.")
        return []

    users = list(
        _query_users_for_role(role)
        .filter(
            Q(username__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(email__icontains=term)
            | Q(profile__employee_id__icontains=term)
            | Q(profile__phone__icontains=term)
        )
        .distinct()[:50]
    )
    if not users:
        print("No matching users found.")
        return []

    print(f"\nFound {len(users)} matching {role} users:")
    for index, user in enumerate(users, start=1):
        _display_user_row(index, user)
    return users


def _select_from_list(users):
    if not users:
        return None
    choice = _prompt_choice("Select number, or 0 to go back: ", range(0, len(users) + 1))
    if choice == "0":
        return None
    return users[int(choice) - 1]


def _select_by_database_id(role):
    from django.contrib.auth import get_user_model

    raw_id = input("Enter user database ID, or 0 to go back: ").strip()
    if raw_id == "0":
        return None
    if not raw_id.isdigit():
        print("Database ID must be numeric.")
        return None

    User = get_user_model()
    user = User.objects.filter(pk=int(raw_id), role=role, is_active=True).select_related("profile").first()
    if not user:
        print(f"No active {role} user found with database ID {raw_id}.")
        return None
    return user


def _confirm(message):
    value = input(f"{message} (y/n): ").strip().lower()
    return value in {"y", "yes"}


def _apply_force_password_action(user, event):
    old_value = user.must_change_password
    if event == "forced":
        user.must_change_password = True
        user.save(update_fields=["must_change_password"])
        print("Done. Force password change is now ON.")
    elif event == "cleared":
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])
        print("Done. Force password change is now OFF.")
    else:
        print("No status changed.")

    _record_cli_force_password_audit(user, event, old_value, user.must_change_password)

    if _confirm("Send email notification"):
        sent = send_forced_password_email(user, event)
        print("Email sent." if sent else "Email failed. Check email logs.")


def _record_cli_force_password_audit(user, event, old_value, new_value):
    from App.models import AdminAuditLog

    action = "FORCE_PASSWORD_CHANGE" if event == "forced" else "CLEAR_FORCE_PASSWORD_CHANGE"
    reason = (
        "Force password change enabled from terminal service."
        if event == "forced"
        else "Force password change cleared from terminal service."
    )
    AdminAuditLog.objects.create(
        model_label="App.CustomUser",
        object_id=str(user.pk),
        object_repr=str(user),
        action=action,
        updated_by=None,
        reason=reason,
        changes={
            "must_change_password": {
                "old": old_value,
                "new": new_value,
            }
        },
    )


def _manage_selected_user(user):
    while True:
        profile = getattr(user, "profile", None)
        employee_id = getattr(profile, "employee_id", "") or "-"
        full_name = user.get_full_name().strip() or "-"
        print("\nSelected user")
        print(f"Name: {full_name}")
        print(f"Username: {user.username}")
        print(f"Employee ID: {employee_id}")
        print(f"Email: {user.email or '-'}")
        print(f"Role: {user.role}")
        print(f"Current force password status: {'ON' if user.must_change_password else 'OFF'}")
        print("\nActions")
        print("1. Turn force password change ON")
        print("2. Turn force password change OFF")
        print("3. Send email notification only")
        print("0. Back")
        choice = _prompt_choice("Select option: ", {"0", "1", "2", "3"})
        if choice == "0":
            return
        if choice == "1":
            if user.must_change_password:
                print("Force password change is already ON.")
                continue
            if _confirm(f"Force {user.username} to change password on next login"):
                _apply_force_password_action(user, "forced")
        elif choice == "2":
            if not user.must_change_password:
                print("Force password change is already OFF.")
                continue
            if _confirm(f"Remove force password change for {user.username}"):
                _apply_force_password_action(user, "cleared")
        elif choice == "3":
            event = "forced" if user.must_change_password else "cleared"
            sent = send_forced_password_email(user, event)
            print("Email sent." if sent else "Email failed. Check email logs.")


def _role_menu(role):
    while True:
        label = "Employee" if role == "EMPLOYEE" else "HR"
        print(f"\n{label} Password Force Menu (active users only)")
        print("1. Show active user list")
        print("2. Search active users by name, username, email, employee ID, or phone")
        print("3. Enter user database ID directly")
        print("0. Back")
        choice = _prompt_choice("Select option: ", {"0", "1", "2", "3"})
        if choice == "0":
            return
        if choice == "1":
            user = _select_from_list(_list_users(role))
        elif choice == "2":
            user = _select_from_list(_search_users(role))
        else:
            user = _select_by_database_id(role)

        if user:
            _manage_selected_user(user)


def run_cli():
    _setup_django_for_cli()
    print("\nForce Password Change Manager")
    print("Only active Employee and HR users are shown or accepted.")
    while True:
        print("\n1. Employee")
        print("2. HR")
        print("0. Exit")
        choice = _prompt_choice("Select option: ", {"0", "1", "2"})
        if choice == "0":
            print("Exiting Force Password Change Manager.")
            return
        if choice == "1":
            _role_menu("EMPLOYEE")
        elif choice == "2":
            _role_menu("HR")


if __name__ == "__main__":
    run_cli()
