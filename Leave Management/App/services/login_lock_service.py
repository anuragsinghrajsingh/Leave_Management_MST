import hashlib
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from django.core.cache import cache
from django.utils import timezone


LOGIN_RATE_LIMITS = {
    "ADMIN": {"max_attempts": 5, "window": 15 * 60, "lockout": 30 * 60},
    "HR": {"max_attempts": 5, "window": 15 * 60, "lockout": 15 * 60},
    "EMPLOYEE": {"max_attempts": 5, "window": 15 * 60, "lockout": 15 * 60},
}


@dataclass(frozen=True)
class LoginLockStatus:
    portal: str
    username: str
    is_locked: bool
    reason: str
    remaining_seconds: int
    expires_at: object
    failed_attempts: int
    max_attempts: int
    last_failed_ip: str


def safe_username(username):
    return (username or "").strip()


def login_cache_token(value):
    normalized = str(value or "blank").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def login_cache_key(kind, portal, value):
    return f"login_rate:{portal.lower()}:{kind}:{login_cache_token(value)}"


def get_login_rate_config(portal):
    return LOGIN_RATE_LIMITS.get(portal, LOGIN_RATE_LIMITS["EMPLOYEE"])


def detect_user_portal(user):
    if getattr(user, "is_superuser", False):
        return "ADMIN"
    if getattr(user, "role", "") == "HR":
        return "HR"
    return "EMPLOYEE"


def default_lock_minutes_for_portal(portal):
    return max(get_login_rate_config(portal)["lockout"] // 60, 1)


def remember_failed_login_ip(portal, username, ip_address):
    username = safe_username(username)
    if not username or not ip_address:
        return
    cache.set(
        login_cache_key("last_failed_ip", portal, username),
        ip_address,
        get_login_rate_config(portal)["window"],
    )


def get_login_lock_status(portal, username, ip_address=None):
    username = safe_username(username)
    now_ts = timezone.now().timestamp()
    config = get_login_rate_config(portal)
    last_failed_ip = cache.get(login_cache_key("last_failed_ip", portal, username), "") or ""
    status_ip_address = ip_address or last_failed_ip

    lock_sources = [
        ("Manual/admin lock", cache.get(login_cache_key("manual_lock_user", portal, username))),
        ("Wrong password lock", cache.get(login_cache_key("lock_user", portal, username))),
    ]
    if status_ip_address:
        lock_sources.append(("IP wrong password lock", cache.get(login_cache_key("lock_ip", portal, status_ip_address))))

    active_locks = []
    for reason, lock_until in lock_sources:
        try:
            lock_until_ts = float(lock_until or 0)
        except (TypeError, ValueError):
            lock_until_ts = 0
        if lock_until_ts > now_ts:
            active_locks.append((reason, lock_until_ts))

    if active_locks:
        reason, lock_until_ts = max(active_locks, key=lambda item: item[1])
        remaining = max(int(lock_until_ts - now_ts), 0)
        expires_at = timezone.datetime.fromtimestamp(lock_until_ts, tz=timezone.get_current_timezone())
    else:
        reason = ""
        remaining = 0
        expires_at = None

    failed_attempts = int(cache.get(login_cache_key("fail_user", portal, username), 0) or 0)

    return LoginLockStatus(
        portal=portal,
        username=username,
        is_locked=bool(active_locks),
        reason=reason,
        remaining_seconds=remaining,
        expires_at=expires_at,
        failed_attempts=failed_attempts,
        max_attempts=config["max_attempts"],
        last_failed_ip=last_failed_ip,
    )


def lock_user_login(user, minutes, *, portal=None):
    portal = portal or detect_user_portal(user)
    username = safe_username(user.username)
    minutes = max(int(minutes or 0), 1)
    timeout = minutes * 60
    lock_until = timezone.now().timestamp() + timeout
    cache.set(login_cache_key("manual_lock_user", portal, username), lock_until, timeout)
    return get_login_lock_status(portal, username)


def unlock_user_login(user, *, portal=None):
    portal = portal or detect_user_portal(user)
    username = safe_username(user.username)
    status_before = get_login_lock_status(portal, username)
    keys = [
        login_cache_key("manual_lock_user", portal, username),
        login_cache_key("lock_user", portal, username),
        login_cache_key("fail_user", portal, username),
        login_cache_key("last_failed_ip", portal, username),
    ]
    if status_before.last_failed_ip:
        keys.extend([
            login_cache_key("lock_ip", portal, status_before.last_failed_ip),
            login_cache_key("fail_ip", portal, status_before.last_failed_ip),
        ])
    cache.delete_many(keys)
    return get_login_lock_status(portal, username)


def login_lock_status_payload(status):
    return {
        "portal": status.portal,
        "status": "locked" if status.is_locked else "unlocked",
        "reason": status.reason or "",
        "remaining_seconds": status.remaining_seconds,
        "failed_attempts": status.failed_attempts,
        "max_attempts": status.max_attempts,
        "last_failed_ip": status.last_failed_ip,
        "expires_at": status.expires_at.isoformat() if status.expires_at else "",
    }


def record_login_lock_audit(user, *, action, source, reason, old_status=None, new_status=None, duration_minutes=None, mode=""):
    from App.models import AdminAuditLog

    changes = {
        "login_lock_control": {
            "old": login_lock_status_payload(old_status) if old_status else None,
            "new": login_lock_status_payload(new_status) if new_status else None,
            "source": source,
            "duration_minutes": duration_minutes,
            "mode": mode,
        }
    }
    AdminAuditLog.objects.create(
        model_label=user._meta.label,
        object_id=str(user.pk),
        object_repr=str(user),
        action=action,
        updated_by=None,
        reason=(reason or "").strip(),
        changes=changes,
    )


def format_remaining(seconds):
    seconds = max(int(seconds or 0), 0)
    if seconds <= 0:
        return "-"
    minutes = (seconds + 59) // 60
    if minutes < 60:
        return f"{minutes} min"
    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes:
        return f"{hours} hr {remaining_minutes} min"
    return f"{hours} hr"


BACK = object()
EXIT = object()
PAGE_SIZE = 10

ROLE_OPTIONS = {
    "1": ("EMPLOYEE", "Employee"),
    "2": ("HR", "HR"),
    "3": ("Admin", "Admin"),
}


def bootstrap_django_for_direct_run():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django

    django.setup()


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


def pause_to_role_menu():
    input("\nPress Enter to return to role menu...")


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


def status_label(status):
    if status.is_locked:
        return f"Locked: {format_remaining(status.remaining_seconds)}"
    if status.failed_attempts:
        return f"Failed: {status.failed_attempts}/{status.max_attempts}"
    return "Unlocked"


def print_user_details(user):
    profile = getattr(user, "profile", None)
    portal = detect_user_portal(user)
    status = get_login_lock_status(portal, user.username)
    full_name = user.get_full_name().strip() or "-"
    employee_id = getattr(profile, "employee_id", "") or "-"
    department = getattr(profile, "department", "") or "-"
    phone = getattr(profile, "phone", "") or "-"
    expires_at = timezone.localtime(status.expires_at).strftime("%d %b %Y, %I:%M %p") if status.expires_at else "-"

    print("\nUser details")
    print("-" * 56)
    print(f"DB ID: {user.pk}")
    print(f"Username: {user.username}")
    print(f"Full name: {full_name}")
    print(f"Email: {user.email or '-'}")
    print(f"Role: {user.role}")
    print(f"Employee ID: {employee_id}")
    print(f"Department: {department}")
    print(f"Phone: {phone}")
    print(f"Active: {'Yes' if user.is_active else 'No'}")
    print(f"Login status: {'LOCKED' if status.is_locked else 'UNLOCKED'}")
    print(f"Reason: {status.reason or '-'}")
    print(f"Failed attempts: {status.failed_attempts}/{status.max_attempts}")
    print(f"Remaining: {format_remaining(status.remaining_seconds)}")
    print(f"Expires at: {expires_at}")
    print("-" * 56)


def print_current_status(user):
    portal = detect_user_portal(user)
    status = get_login_lock_status(portal, user.username)
    print("\nUser found")
    print(f"Username: {user.username}")
    print(f"Name: {user.get_full_name().strip() or '-'}")
    print(f"Role: {user.role or 'Admin'}")
    print(f"Detected portal: {portal}")
    print("\nCurrent login status")
    print(f"Status: {'LOCKED' if status.is_locked else 'UNLOCKED'}")
    print(f"Reason: {status.reason or '-'}")
    print(f"Failed attempts: {status.failed_attempts}/{status.max_attempts}")
    print(f"Remaining: {format_remaining(status.remaining_seconds)}")
    expires_at = timezone.localtime(status.expires_at).strftime("%d %b %Y, %I:%M %p") if status.expires_at else "-"
    print(f"Expires at: {expires_at}")
    print(f"Last failed IP: {status.last_failed_ip or '-'}")
    return status


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
            pause_to_role_menu()
            return BACK

        print(f"\nShowing {role_label} users {start + 1}-{min(end, total)} of {total}")
        print("-" * 96)
        for index, user in enumerate(users, start=1):
            profile = getattr(user, "profile", None)
            employee_id = getattr(profile, "employee_id", "") or "-"
            full_name = user.get_full_name().strip() or "-"
            portal = detect_user_portal(user)
            status = get_login_lock_status(portal, user.username)
            print(f"{index}. {user.username} | {full_name} | {employee_id} | {user.email or '-'} | {status_label(status)}")
        print("-" * 96)
        print("Number = select user | N = Next page | P = Previous page | B = Back | 0 = Exit")

        valid_numbers = {str(i) for i in range(1, len(users) + 1)}
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


def confirm_action(prompt):
    print("\nFinal confirmation")
    print(prompt)
    print("\n1. Confirm")
    print("B. Back")
    print("0. Exit")
    return prompt_menu("Select option: ", {"1"})


def print_summary(action_label, user, status):
    print("\nFinal summary")
    print("-" * 56)
    print(f"Action: {action_label}")
    print("Status: Complete")
    print(f"User: {user.username}")
    print(f"New login status: {'LOCKED' if status.is_locked else 'UNLOCKED'}")
    print(f"Remaining: {format_remaining(status.remaining_seconds)}")
    print(f"Failed attempts: {status.failed_attempts}/{status.max_attempts}")
    print("Audit log: Created")
    print("-" * 56)


def prompt_audit_reason():
    while True:
        value = input("Audit reason (B=Back, 0=Exit): ").strip()
        lowered = value.lower()
        if lowered in {"b", "back"}:
            return BACK
        if lowered in {"0", "exit", "q", "quit"}:
            return EXIT
        if value:
            return value
        print("Audit reason is required.")


def check_status_action(user, source):
    status = print_current_status(user)
    record_login_lock_audit(
        user,
        action="LOGIN_STATUS_CHECK",
        source=source,
        reason=f"{source} checked login lock status.",
        old_status=None,
        new_status=status,
        mode="status",
    )
    pause_to_role_menu()
    return None


def lock_action(user, source):
    portal = detect_user_portal(user)
    old_status = get_login_lock_status(portal, user.username)
    print_current_status(user)

    while True:
        print("\nLock method")
        print("1. Default duration")
        print("2. Enter duration manually")
        print("B. Back")
        print("0. Exit")
        mode_choice = prompt_menu("Select option: ", {"1", "2"})
        if mode_choice in {BACK, EXIT}:
            return mode_choice
        if mode_choice == "1":
            mode = "default"
            minutes = default_lock_minutes_for_portal(portal)
            print(f"Using {portal} default duration: {minutes} minutes")
            break
        if mode_choice == "2":
            mode = "manual"
            while True:
                raw_minutes = input("Enter lock duration in minutes (B=Back, 0=Exit): ").strip()
                lowered = raw_minutes.lower()
                if lowered in {"b", "back"}:
                    return BACK
                if lowered in {"0", "exit", "q", "quit"}:
                    return EXIT
                try:
                    minutes = int(raw_minutes)
                except ValueError:
                    print("Enter a valid number.")
                    continue
                if minutes <= 0:
                    print("Minutes must be greater than 0.")
                    continue
                break
            break
        print("Choose 1 or 2.")

    reason = prompt_audit_reason()
    if reason is BACK or reason is EXIT:
        return reason

    confirmation = confirm_action(
        f"User: {user.username} ({user.role})\nAction: Lock login\nDuration: {minutes} minutes"
    )
    if confirmation is BACK or confirmation is EXIT:
        return confirmation

    new_status = lock_user_login(user, minutes, portal=portal)
    record_login_lock_audit(
        user,
        action="LOGIN_LOCK",
        source=source,
        reason=reason,
        old_status=old_status,
        new_status=new_status,
        duration_minutes=minutes,
        mode=mode,
    )
    print_summary("Login lock", user, new_status)
    pause_to_role_menu()
    return None


def unlock_action(user, source):
    portal = detect_user_portal(user)
    old_status = get_login_lock_status(portal, user.username)
    print_current_status(user)

    reason = prompt_audit_reason()
    if reason is BACK or reason is EXIT:
        return reason

    confirmation = confirm_action(f"User: {user.username} ({user.role})\nAction: Unlock login")
    if confirmation is BACK or confirmation is EXIT:
        return confirmation

    new_status = unlock_user_login(user, portal=portal)
    record_login_lock_audit(
        user,
        action="LOGIN_UNLOCK",
        source=source,
        reason=reason,
        old_status=old_status,
        new_status=new_status,
        mode="unlock",
    )
    print_summary("Login unlock", user, new_status)
    pause_to_role_menu()
    return None


def handle_selected_user(user, source):
    while True:
        print_user_details(user)
        print("\nLogin action")
        print("1. Check lock status")
        print("2. Lock login")
        print("3. Unlock login")
        print("B. Back")
        print("0. Exit")
        choice = prompt_menu("Select option: ", {"1", "2", "3"})
        if choice is BACK:
            return
        if choice is EXIT:
            return EXIT
        if choice == "1":
            result = check_status_action(user, source)
        elif choice == "2":
            result = lock_action(user, source)
        else:
            result = unlock_action(user, source)
        if result is EXIT:
            return EXIT
        if result is BACK:
            continue
        return


def handle_selected_role(role, role_label, source):
    while True:
        print(f"\n{role_label} menu")
        print("1. Search user")
        print("2. List users")
        print("B. Back")
        print("0. Exit")
        choice = prompt_menu("Select option: ", {"1", "2"})
        if choice is BACK:
            return
        if choice is EXIT:
            return EXIT

        if choice == "1":
            user = choose_user_from_search(role, role_label)
        else:
            user = choose_user_from_list(role, role_label)

        if user is BACK:
            continue
        if user is EXIT:
            return EXIT

        result = handle_selected_user(user, source)
        if result is EXIT:
            return EXIT


def run_login_lock_cli(source="DIRECT_FILE"):
    bootstrap_django_for_direct_run()
    print("\nLogin Lock Service")
    print("Use this tool to check, lock, or unlock a user's login from terminal.")

    while True:
        print("\nMain menu")
        print("1. Employee")
        print("2. HR")
        print("3. Admin")
        print("0. Exit")
        choice = prompt_menu("Select option: ", ROLE_OPTIONS.keys(), allow_back=False)
        if choice is EXIT:
            print("Exiting Login Lock Service.")
            return 0

        role, role_label = ROLE_OPTIONS[choice]
        result = handle_selected_role(role, role_label, source)
        if result is EXIT:
            print("Exiting Login Lock Service.")
            return 0


if __name__ == "__main__":
    raise SystemExit(run_login_lock_cli("DIRECT_FILE"))
