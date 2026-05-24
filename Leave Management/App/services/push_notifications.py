import json
import logging
import os
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from django.utils.timezone import now
from django.utils import timezone


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

from App.models import AdminAuditLog, PushSubscription


logger = logging.getLogger("lms_push")
PAGE_SIZE = 10


def push_is_configured():
    return bool(
        getattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", "")
        and getattr(settings, "WEB_PUSH_VAPID_PRIVATE_KEY", "")
        and getattr(settings, "WEB_PUSH_VAPID_SUBJECT", "")
    )


def build_push_payload(title, body, *, url="/", tag="", kind="general", icon="/static/images/ms-technology-logo.png"):
    return {
        "title": title,
        "body": body,
        "url": url or "/",
        "tag": tag or kind,
        "kind": kind,
        "icon": icon,
        "badge": icon,
    }


def send_push_to_user(user, title, body, *, url="/", tag="", kind="general"):
    if not user or not push_is_configured():
        return {"sent": 0, "failed": 0, "skipped": True}

    payload = build_push_payload(title, body, url=url, tag=tag, kind=kind)
    return send_push_payload_to_user(user, payload)


def send_push_payload_to_user(user, payload):
    if not user or not push_is_configured():
        return {"sent": 0, "failed": 0, "skipped": True}

    try:
        from pywebpush import WebPushException, webpush
    except ImportError:
        logger.warning("PUSH_SKIPPED | pywebpush is not installed")
        return {"sent": 0, "failed": 0, "skipped": True}

    subscriptions = PushSubscription.objects.filter(user=user, is_active=True)
    sent = 0
    failed = 0

    for subscription in subscriptions:
        subscription_info = {
            "endpoint": subscription.endpoint,
            "keys": {
                "p256dh": subscription.p256dh,
                "auth": subscription.auth,
            },
        }

        try:
            webpush(
                subscription_info=subscription_info,
                data=json.dumps(payload),
                vapid_private_key=settings.WEB_PUSH_VAPID_PRIVATE_KEY,
                vapid_claims={"sub": settings.WEB_PUSH_VAPID_SUBJECT},
            )
            PushSubscription.objects.filter(pk=subscription.pk).update(
                last_sent_at=now(),
                last_error="",
                is_active=True,
            )
            sent += 1
        except WebPushException as exc:
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            error_message = str(exc)
            updates = {"last_error": error_message}
            if status_code in {400, 403, 404, 410}:
                updates["is_active"] = False
            PushSubscription.objects.filter(pk=subscription.pk).update(**updates)
            logger.warning(
                "PUSH_SEND_FAILED | user_id=%s | subscription_id=%s | status=%s | deactivated=%s",
                user.pk,
                subscription.pk,
                status_code,
                status_code in {400, 403, 404, 410},
            )
            failed += 1
        except Exception as exc:
            PushSubscription.objects.filter(pk=subscription.pk).update(last_error=str(exc))
            logger.exception("PUSH_SEND_ERROR | user_id=%s | subscription_id=%s", user.pk, subscription.pk)
            failed += 1

    return {"sent": sent, "failed": failed, "skipped": False}


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


def _profile_value(user, field_name, default="-"):
    profile = getattr(user, "profile", None)
    return getattr(profile, field_name, "") or default


def _user_label(user):
    employee_id = _profile_value(user, "employee_id")
    name = user.get_full_name() or user.username
    return f"{name} | {user.role or '-'} | {employee_id} | {user.email or '-'}"


def _user_queryset(mode="all", term=""):
    User = get_user_model()
    qs = User.objects.select_related("profile")
    if mode == "active":
        qs = qs.filter(push_subscriptions__is_active=True)
    elif mode == "inactive":
        qs = qs.filter(Q(push_subscriptions__is_active=False) | ~Q(push_subscriptions__last_error=""))
    elif mode == "any":
        qs = qs.filter(push_subscriptions__isnull=False)

    if term:
        qs = qs.filter(
            Q(username__icontains=term)
            | Q(email__icontains=term)
            | Q(first_name__icontains=term)
            | Q(last_name__icontains=term)
            | Q(profile__employee_id__icontains=term)
        )

    return (
        qs.annotate(
            active_push_count=Count("push_subscriptions", filter=Q(push_subscriptions__is_active=True), distinct=True),
            inactive_push_count=Count("push_subscriptions", filter=Q(push_subscriptions__is_active=False), distinct=True),
            failed_push_count=Count("push_subscriptions", filter=~Q(push_subscriptions__last_error=""), distinct=True),
        )
        .distinct()
        .order_by("username")
    )


def _select_user(qs, title):
    page = 1
    while True:
        total = qs.count()
        total_pages = max((total + PAGE_SIZE - 1) // PAGE_SIZE, 1)
        page = max(1, min(page, total_pages))
        start = (page - 1) * PAGE_SIZE
        users = list(qs[start:start + PAGE_SIZE])

        print(f"\n{title}")
        print(f"Showing page {page}/{total_pages} | Total users: {total}")
        if not users:
            print("No users found.")

        for index, user in enumerate(users, start=1):
            print(
                f"{index}. ID #{user.id} | {_user_label(user)} | "
                f"Active: {user.active_push_count} | Inactive: {user.inactive_push_count} | Failed: {user.failed_push_count}"
            )

        print("\nN = Next page | P = Previous page | B = Back | 0 = Exit")
        choice = _safe_input("Select user number, or type ID <user id>: ").lower()
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
        if choice.startswith("id "):
            raw_id = choice[3:].strip()
            if raw_id.isdigit():
                user = qs.filter(id=int(raw_id)).first()
                if user:
                    return user
            print("User ID not found in this list.")
            continue
        if choice.isdigit():
            selected_index = int(choice)
            if 1 <= selected_index <= len(users):
                return users[selected_index - 1]
            print("Select a number from the visible list.")
            continue
        print("Invalid choice.")


def _search_user(mode="any"):
    term = _safe_input("Search by username, email, name, or employee ID (B=Back, 0=Exit): ")
    if term.lower() == "0":
        return "exit"
    if term.lower() == "b":
        return None
    return _select_user(_user_queryset(mode=mode, term=term), f"Search results for '{term or 'all'}'")


def _subscription_queryset(user, mode="all"):
    qs = PushSubscription.objects.filter(user=user).order_by("-is_active", "-last_seen_at", "-id")
    if mode == "active":
        qs = qs.filter(is_active=True)
    elif mode == "inactive":
        qs = qs.filter(Q(is_active=False) | ~Q(last_error=""))
    return qs


def _subscription_label(subscription):
    browser = subscription.browser or "-"
    device = subscription.device_label or "-"
    status = "Active" if subscription.is_active else "Inactive"
    error = subscription.last_error[:80] if subscription.last_error else "-"
    return (
        f"ID #{subscription.id} | {browser} | {device} | {status} | "
        f"Last seen: {_format_datetime(subscription.last_seen_at)} | Last error: {error}"
    )


def _show_user_subscriptions(user, mode="all", title_prefix="Subscriptions"):
    qs = _subscription_queryset(user, mode=mode)
    subscriptions = list(qs)
    print(f"\n{title_prefix} for {_user_label(user)}")
    if not subscriptions:
        print("No subscriptions found.")
        return None
    for index, subscription in enumerate(subscriptions, start=1):
        print(f"{index}. {_subscription_label(subscription)}")
    return subscriptions


def _select_subscription(user, mode="all"):
    while True:
        subscriptions = _show_user_subscriptions(user, mode=mode)
        if not subscriptions:
            _safe_input("\nPress Enter to continue...")
            return None

        choice = _safe_input("\nSelect subscription number, or type ID <subscription id> (B=Back, 0=Exit): ").lower()
        if choice == "0":
            return "exit"
        if choice == "b":
            return None
        if choice.startswith("id "):
            raw_id = choice[3:].strip()
            if raw_id.isdigit():
                subscription = PushSubscription.objects.filter(user=user, id=int(raw_id)).first()
                if subscription and (mode != "active" or subscription.is_active):
                    return subscription
            print("Subscription ID not found for this user/list.")
            continue
        if choice.isdigit():
            selected_index = int(choice)
            if 1 <= selected_index <= len(subscriptions):
                return subscriptions[selected_index - 1]
            print("Select a number from the visible list.")
            continue
        print("Invalid choice.")


def _view_users(mode, title):
    user = _select_user(_user_queryset(mode=mode), title)
    if user == "exit":
        return "exit"
    if user:
        _show_user_subscriptions(user, mode=mode if mode in {"active", "inactive"} else "all")
        _safe_input("\nPress Enter to continue...")
    return None


def _search_user_subscriptions():
    user = _search_user(mode="any")
    if user == "exit":
        return "exit"
    if user:
        _show_user_subscriptions(user)
        _safe_input("\nPress Enter to continue...")
    return None


def _send_test_push_to_user():
    user = _search_user(mode="active")
    if user == "exit":
        return "exit"
    if not user:
        return None

    _show_user_subscriptions(user, mode="active", title_prefix="Active subscriptions")
    active_count = PushSubscription.objects.filter(user=user, is_active=True).count()
    if not active_count:
        print("This user has no active subscriptions.")
        _safe_input("\nPress Enter to continue...")
        return None

    confirmation = _safe_input("Type SEND to send test push (B=Back, 0=Exit): ")
    if confirmation.lower() == "0":
        return "exit"
    if confirmation.lower() == "b":
        return None
    if confirmation != "SEND":
        print("Test push cancelled.")
        return None

    result = send_push_to_user(
        user,
        "Leave Management test notification",
        "Push notification is working for this browser/device.",
        url="/dashboard/",
        tag=f"push-test-terminal-{user.pk}",
        kind="test",
    )
    AdminAuditLog.objects.create(
        model_label="PushSubscription",
        object_id=str(user.pk),
        object_repr=f"Push test for {user.username}",
        action="PUSH_TEST",
        reason="Terminal push test",
        changes={"sent": result.get("sent"), "failed": result.get("failed"), "skipped": result.get("skipped")},
    )
    print(f"Test push result: sent={result.get('sent')} failed={result.get('failed')} skipped={result.get('skipped')}")
    _safe_input("\nPress Enter to continue...")
    return None


def _deactivate_one_subscription():
    while True:
        print("\nDeactivate One Subscription")
        print("1. List users with active subscriptions")
        print("2. Search user")
        print("B. Back")
        print("0. Exit")

        choice = _safe_input("Choose an option: ").lower()
        if choice == "0":
            return "exit"
        if choice == "b":
            return None
        if choice == "1":
            user = _select_user(_user_queryset(mode="active"), "Users with active subscriptions")
        elif choice == "2":
            user = _search_user(mode="active")
        else:
            print("Invalid choice.")
            continue

        if user == "exit":
            return "exit"
        if not user:
            continue

        subscription = _select_subscription(user, mode="active")
        if subscription == "exit":
            return "exit"
        if not subscription:
            continue

        print("\nSelected subscription")
        print(f"User: {_user_label(user)}")
        print(_subscription_label(subscription))

        reason = _safe_input("Audit reason (B=Back, 0=Exit): ")
        if reason.lower() == "0":
            return "exit"
        if reason.lower() == "b":
            continue
        if not reason:
            print("Reason is required.")
            continue

        confirmation = _safe_input("Type DEACTIVATE to confirm (B=Back, 0=Exit): ")
        if confirmation.lower() == "0":
            return "exit"
        if confirmation.lower() == "b":
            continue
        if confirmation != "DEACTIVATE":
            print("Deactivate cancelled.")
            continue

        subscription.is_active = False
        subscription.last_error = subscription.last_error or "Manually deactivated from terminal."
        subscription.save(update_fields=["is_active", "last_error", "updated_at"])
        AdminAuditLog.objects.create(
            model_label="PushSubscription",
            object_id=str(subscription.id),
            object_repr=f"{user.username} push subscription #{subscription.id}",
            action="PUSH_DEACTIVATE",
            reason=reason,
            changes={
                "user": user.username,
                "subscription_id": subscription.id,
                "browser": subscription.browser,
                "device_label": subscription.device_label,
                "is_active": False,
            },
        )
        print(f"Subscription #{subscription.id} deactivated.")
        _safe_input("\nPress Enter to continue...")
        return None


def _deactivate_all_failed():
    qs = PushSubscription.objects.filter(Q(is_active=False) | ~Q(last_error=""))
    total = qs.count()
    users = qs.values("user_id").distinct().count()
    print("\nDeactivate All Failed/Inactive Subscriptions")
    print(f"Failed/inactive subscriptions found: {total}")
    print(f"Users affected: {users}")
    if not total:
        _safe_input("\nPress Enter to continue...")
        return None

    reason = _safe_input("Audit reason (B=Back, 0=Exit): ")
    if reason.lower() == "0":
        return "exit"
    if reason.lower() == "b":
        return None
    if not reason:
        print("Reason is required.")
        return None

    confirmation = _safe_input("Type DEACTIVATE_FAILED to confirm (B=Back, 0=Exit): ")
    if confirmation.lower() == "0":
        return "exit"
    if confirmation.lower() == "b":
        return None
    if confirmation != "DEACTIVATE_FAILED":
        print("Cleanup cancelled.")
        return None

    updated = qs.update(is_active=False, updated_at=now())
    AdminAuditLog.objects.create(
        model_label="PushSubscription",
        object_id="bulk",
        object_repr="Failed push subscriptions",
        action="PUSH_CLEANUP",
        reason=reason,
        changes={"deactivated": updated, "users_affected": users},
    )
    print(f"Deactivated/kept inactive {updated} failed subscription(s).")
    _safe_input("\nPress Enter to continue...")
    return None


def _show_summary():
    total = PushSubscription.objects.count()
    active = PushSubscription.objects.filter(is_active=True).count()
    inactive = PushSubscription.objects.filter(is_active=False).count()
    failed = PushSubscription.objects.exclude(last_error="").count()
    users_active = PushSubscription.objects.filter(is_active=True).values("user_id").distinct().count()
    users_failed = PushSubscription.objects.exclude(last_error="").values("user_id").distinct().count()
    latest_failure = PushSubscription.objects.exclude(last_error="").select_related("user__profile").order_by("-updated_at", "-id").first()

    print("\nPush Notification Summary")
    print(f"Total subscriptions: {total}")
    print(f"Active subscriptions: {active}")
    print(f"Inactive subscriptions: {inactive}")
    print(f"Failed subscriptions: {failed}")
    print(f"Users with active subscriptions: {users_active}")
    print(f"Users with failed subscriptions: {users_failed}")
    if latest_failure:
        print(f"Last failure: #{latest_failure.id} | {_user_label(latest_failure.user)} | {latest_failure.last_error[:160]}")
    else:
        print("Last failure: -")
    print(f"Push configured: {'Yes' if push_is_configured() else 'No'}")
    _safe_input("\nPress Enter to continue...")


def run_interactive():
    while True:
        print("\nPush Notification Manager")
        print("1. View users with active subscriptions")
        print("2. View users with inactive/failed subscriptions")
        print("3. Search user subscriptions")
        print("4. Send test push to user")
        print("5. Deactivate one subscription")
        print("6. Deactivate all failed subscriptions")
        print("7. Summary")
        print("0. Exit")

        choice = _safe_input("Choose an option: ").lower()
        if choice in {"0", "exit", "q", "quit"}:
            print("Exit.")
            return 0
        if choice == "1":
            result = _view_users("active", "Users with active subscriptions")
        elif choice == "2":
            result = _view_users("inactive", "Users with inactive/failed subscriptions")
        elif choice == "3":
            result = _search_user_subscriptions()
        elif choice == "4":
            result = _send_test_push_to_user()
        elif choice == "5":
            result = _deactivate_one_subscription()
        elif choice == "6":
            result = _deactivate_all_failed()
        elif choice == "7":
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
