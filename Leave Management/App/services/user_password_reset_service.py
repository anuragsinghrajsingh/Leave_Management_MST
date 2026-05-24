import getpass
import os
import secrets
import string
import subprocess
import sys


BACK = object()
EXIT = object()
PAGE_SIZE = 10


ROLE_OPTIONS = {
    "1": ("EMPLOYEE", "Employee"),
    "2": ("HR", "HR"),
    "3": ("Admin", "Admin"),
}


def setup_django():
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


def generate_password(length=14):
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(char.islower() for char in password)
            and any(char.isupper() for char in password)
            and any(char.isdigit() for char in password)
            and any(char in "!@#$%^&*" for char in password)
        ):
            return password


def prompt_menu(prompt, choices, *, allow_back=True, allow_exit=True):
    valid_choices = {str(choice) for choice in choices}
    while True:
        value = input(prompt).strip()
        lowered = value.lower()
        if allow_back and lowered in {"b", "back"}:
            return BACK
        if allow_exit and lowered in {"0", "exit", "q", "quit"}:
            return EXIT
        if value in valid_choices:
            return value
        options = sorted(valid_choices)
        if allow_back:
            options.append("B")
        if allow_exit:
            options.append("0")
        print("Invalid choice. Select one of:", ", ".join(options))


def prompt_lookup():
    while True:
        value = input("Enter username, email, or employee ID (B=Back, 0=Exit): ").strip()
        lowered = value.lower()
        if lowered in {"b", "back"}:
            return BACK
        if lowered in {"0", "exit", "q", "quit"}:
            return EXIT
        if value:
            return value
        print("Lookup cannot be blank.")


def prompt_manual_password():
    while True:
        password = getpass.getpass("Enter new password (B=Back, 0=Exit): ")
        if password.lower() in {"b", "back"}:
            return BACK
        if password.lower() in {"0", "exit", "q", "quit"}:
            return EXIT
        if not password:
            print("Password cannot be blank.")
            continue

        confirm = getpass.getpass("Confirm new password (B=Back, 0=Exit): ")
        if confirm.lower() in {"b", "back"}:
            return BACK
        if confirm.lower() in {"0", "exit", "q", "quit"}:
            return EXIT
        if password != confirm:
            print("Passwords do not match. Try again.")
            continue
        return password


def get_user_by_lookup(role, lookup):
    from django.contrib.auth import get_user_model
    from django.db.models import Q

    User = get_user_model()
    query = Q(username__iexact=lookup) | Q(email__iexact=lookup) | Q(profile__employee_id__iexact=lookup)
    return User.objects.select_related("profile").filter(role=role).filter(query).distinct().first()


def get_users_for_role(role):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.select_related("profile").filter(role=role).order_by("username", "id")


def print_user_row(index, user):
    profile = getattr(user, "profile", None)
    employee_id = getattr(profile, "employee_id", "") or "-"
    full_name = user.get_full_name().strip() or "-"
    force_status = "ON" if getattr(user, "must_change_password", False) else "OFF"
    print(
        f"{index}. {user.username} | {full_name} | {employee_id} | "
        f"{user.email or '-'} | Active: {'Yes' if user.is_active else 'No'} | Force: {force_status}"
    )


def choose_user_from_list(role, role_label):
    page = 0

    while True:
        queryset = get_users_for_role(role)
        total = queryset.count()
        start = page * PAGE_SIZE
        end = start + PAGE_SIZE
        users = list(queryset[start:end])

        if total == 0:
            print(f"\nNo {role_label} users found.")
            return BACK

        print(f"\nShowing {role_label} users {start + 1}-{min(end, total)} of {total}")
        print("-" * 96)
        for index, user in enumerate(users, start=1):
            print_user_row(index, user)
        print("-" * 96)
        print("Number = select user | N = Next page | P = Previous page | B = Back | 0 = Exit")

        valid_numbers = {str(number) for number in range(1, len(users) + 1)}
        choice = prompt_menu("Select option: ", valid_numbers | {"n", "p"})
        if choice is BACK:
            return BACK
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
        return users[int(choice) - 1]


def choose_user_from_search(role, role_label):
    while True:
        lookup = prompt_lookup()
        if lookup is BACK:
            return BACK
        if lookup is EXIT:
            return EXIT

        user = get_user_by_lookup(role, lookup)
        if not user:
            print(f"No {role_label} found for that username/email/employee ID.")
            continue
        return user


def display_user_details(user):
    profile = getattr(user, "profile", None)
    full_name = user.get_full_name().strip() or "-"
    employee_id = getattr(profile, "employee_id", "") or "-"
    department = getattr(profile, "department", "") or "-"
    phone = getattr(profile, "phone", "") or "-"
    force_status = "ON" if getattr(user, "must_change_password", False) else "OFF"

    print("\nUser details")
    print("-" * 48)
    print(f"DB ID: {user.pk}")
    print(f"Username: {user.username}")
    print(f"Full name: {full_name}")
    print(f"Email: {user.email or '-'}")
    print(f"Role: {user.role}")
    print(f"Employee ID: {employee_id}")
    print(f"Department: {department}")
    print(f"Phone: {phone}")
    print(f"Active: {'Yes' if user.is_active else 'No'}")
    print(f"Force password change: {force_status}")
    print("-" * 48)


def reset_password_only(user, password, reason):
    from App.models import AdminAuditLog

    reason = (reason or "").strip()
    if not reason:
        raise ValueError("Audit reason is required before resetting a password.")

    user.set_password(password)
    user.save(update_fields=["password"])

    AdminAuditLog.objects.create(
        model_label="App.CustomUser",
        object_id=str(user.pk),
        object_repr=str(user),
        action="PASSWORD_RESET",
        updated_by=None,
        reason=reason,
        changes={"password": {"old": "[hidden]", "new": "[reset from terminal]"}},
    )


def set_force_password_change(user, enabled):
    from App.models import AdminAuditLog

    old_value = bool(getattr(user, "must_change_password", False))
    user.must_change_password = bool(enabled)
    user.save(update_fields=["must_change_password"])

    AdminAuditLog.objects.create(
        model_label="App.CustomUser",
        object_id=str(user.pk),
        object_repr=str(user),
        action="FORCE_PASSWORD_CHANGE" if enabled else "CLEAR_FORCE_PASSWORD_CHANGE",
        updated_by=None,
        reason="Force password change updated after terminal password reset.",
        changes={"must_change_password": {"old": old_value, "new": bool(enabled)}},
    )


def copy_to_clipboard(value):
    if sys.platform.startswith("win"):
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"],
            input=value,
            text=True,
            capture_output=True,
            timeout=5,
        )
        return completed.returncode == 0

    if sys.platform == "darwin":
        completed = subprocess.run(["pbcopy"], input=value, text=True, capture_output=True, timeout=5)
        return completed.returncode == 0

    completed = subprocess.run(["xclip", "-selection", "clipboard"], input=value, text=True, capture_output=True, timeout=5)
    return completed.returncode == 0


def maybe_copy_generated_password(password):
    print(f"\nTemporary password: {password}")
    print("Share this password securely. It is shown only in this terminal output.")
    print("\nCopy password to clipboard?")
    print("1. Yes")
    print("2. No")
    choice = prompt_menu("Select option: ", {"1", "2"}, allow_back=False, allow_exit=False)
    if choice == "2":
        return

    try:
        if copy_to_clipboard(password):
            print("Password copied to clipboard.")
        else:
            print("Could not copy password. Please copy it manually from terminal.")
    except Exception:
        print("Could not copy password. Please copy it manually from terminal.")


def ask_force_password_change(user):
    from App.services.forced_password_service import user_can_be_forced_to_change_password

    if not user_can_be_forced_to_change_password(user):
        print("\nForce password change: Not available for Admin users. Skipped.")
        return None

    while True:
        print("\nForce password change on next login?")
        print("1. Yes")
        print("2. No")
        print("B. Back/Skip")
        choice = prompt_menu("Select option: ", {"1", "2"}, allow_back=True, allow_exit=False)
        if choice is BACK:
            print("Force password change skipped.")
            return None
        return choice == "1"


def ask_send_email(user, force_enabled):
    from App.services.forced_password_service import user_can_be_forced_to_change_password

    if not user.email:
        print("\nEmail notification: user has no email. Skipped.")
        return False

    if not user_can_be_forced_to_change_password(user):
        print("\nEmail notification: force-password email is only available for Employee/HR. Skipped.")
        return False

    if force_enabled is not True:
        print("\nEmail notification: skipped because force password change is not ON.")
        return False

    while True:
        print("\nSend email notification?")
        print("1. Yes")
        print("2. No")
        print("B. Back/Skip")
        choice = prompt_menu("Select option: ", {"1", "2"}, allow_back=True, allow_exit=False)
        if choice is BACK:
            print("Email notification skipped.")
            return False
        return choice == "1"


def ask_send_password_reset_email(user):
    if not user.email:
        print("\nPassword reset email: user has no email. Skipped.")
        return False

    while True:
        print("\nSend password reset email notification?")
        print("1. Yes")
        print("2. No")
        print("B. Back/Skip")
        choice = prompt_menu("Select option: ", {"1", "2"}, allow_back=True, allow_exit=False)
        if choice is BACK:
            print("Password reset email skipped.")
            return False
        return choice == "1"


def choose_password():
    while True:
        print("\nPassword reset method")
        print("1. Generate password automatically")
        print("2. Enter password manually")
        print("B. Back")
        print("0. Exit")
        choice = prompt_menu("Select option: ", {"1", "2"})
        if choice in {BACK, EXIT}:
            return choice, None
        if choice == "1":
            return "generate", generate_password()
        password = prompt_manual_password()
        if password is BACK:
            continue
        if password is EXIT:
            return EXIT, None
        return "manual", password


def prompt_audit_reason():
    while True:
        reason = input("Enter audit reason for password reset (B=Back, 0=Exit): ").strip()
        lowered = reason.lower()
        if lowered in {"b", "back"}:
            return BACK
        if lowered in {"0", "exit", "q", "quit"}:
            return EXIT
        if reason:
            return reason
        print("Audit reason is required. Password reset will not continue without it.")


def confirm_reset(user, method, reason):
    print("\nFinal confirmation")
    print(f"User: {user.username} ({user.role})")
    print(f"Method: {'Generated password' if method == 'generate' else 'Manual password'}")
    print(f"Audit reason: {reason}")
    print("\n1. Reset password")
    print("B. Back")
    print("0. Exit")
    choice = prompt_menu("Select option: ", {"1"})
    return choice


def handle_selected_user(user):
    while True:
        display_user_details(user)
        method, password = choose_password()
        if method is BACK:
            return BACK
        if method is EXIT:
            return EXIT

        reason = prompt_audit_reason()
        if reason is BACK:
            continue
        if reason is EXIT:
            return EXIT

        confirmation = confirm_reset(user, method, reason)
        if confirmation is BACK:
            continue
        if confirmation is EXIT:
            return EXIT

        reset_password_only(user, password, reason)
        print("\nPassword reset complete.")

        if method == "generate":
            maybe_copy_generated_password(password)

        reset_email_sent = False
        if ask_send_password_reset_email(user):
            from App.services.forced_password_service import send_password_reset_email

            reset_email_sent = send_password_reset_email(user)
            print("Password reset email sent." if reset_email_sent else "Password reset email could not be sent.")

        force_choice = ask_force_password_change(user)
        force_status = "Skipped"
        if force_choice is not None:
            set_force_password_change(user, force_choice)
            user.refresh_from_db(fields=["must_change_password"])
            force_status = "ON" if user.must_change_password else "OFF"

        email_sent = False
        send_email = ask_send_email(user, force_choice)
        if send_email:
            from App.services.forced_password_service import send_forced_password_email

            email_sent = send_forced_password_email(user, "forced")

        print("\nFinal summary")
        print("-" * 48)
        print("Password reset: Complete")
        print(f"Password reset email: {'Sent' if reset_email_sent else 'Not sent/skipped'}")
        print(f"Force password change: {force_status}")
        print(f"Force password email: {'Sent' if email_sent else 'Not sent/skipped'}")
        print("-" * 48)
        input("Press Enter to return to role menu...")
        return None


def handle_selected_role(role, role_label):
    while True:
        print(f"\n{role_label} menu")
        print("1. List users")
        print("2. Search user")
        print("B. Back")
        print("0. Exit")
        choice = prompt_menu("Select option: ", {"1", "2"})
        if choice is BACK:
            return
        if choice is EXIT:
            return EXIT

        if choice == "1":
            user = choose_user_from_list(role, role_label)
        else:
            user = choose_user_from_search(role, role_label)

        if user is BACK:
            continue
        if user is EXIT:
            return EXIT

        result = handle_selected_user(user)
        if result is EXIT:
            return EXIT


def run_interactive():
    setup_django()
    print("\nPassword Reset Service")
    print("Use this tool to reset a user's password from terminal.")

    while True:
        print("\nMain menu")
        print("1. Employee")
        print("2. HR")
        print("3. Admin")
        print("0. Exit")
        choice = prompt_menu("Select option: ", ROLE_OPTIONS.keys(), allow_back=False)
        if choice is EXIT:
            print("Exiting Password Reset Service.")
            return 0

        role, role_label = ROLE_OPTIONS[choice]
        result = handle_selected_role(role, role_label)
        if result is EXIT:
            print("Exiting Password Reset Service.")
            return 0


if __name__ == "__main__":
    raise SystemExit(run_interactive())
