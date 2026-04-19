import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.shortcuts import reverse
from django.utils.timezone import localtime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from App.models import Leave, LeaveNotificationRead, LeaveNotificationSeen, Profile


def get_leave_type_class(leave_type):
    return {
        "Sick": "sick",
        "Unpaid": "unpaid",
        "Earned": "earned",
        "Short": "short",
        "Half": "half",
    }.get(leave_type, "default")


def parse_json_request_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def get_notification_read_ids_for_user(user, leaves):
    leave_ids = [leave.id for leave in leaves]

    if not leave_ids:
        return set()

    try:
        return set(
            LeaveNotificationRead.objects.filter(user=user, leave_id__in=leave_ids)
            .values_list("leave_id", flat=True)
        )
    except (OperationalError, ProgrammingError):
        return set()


def get_notification_seen_ids_for_user(user, leaves):
    leave_ids = [leave.id for leave in leaves]

    if not leave_ids:
        return set()

    try:
        return set(
            LeaveNotificationSeen.objects.filter(user=user, leave_id__in=leave_ids)
            .values_list("leave_id", flat=True)
        )
    except (OperationalError, ProgrammingError):
        return set()


def reset_hr_notification_state_for_leave(leave):
    hr_user_ids = list(
        get_user_model().objects.filter(role="HR").values_list("id", flat=True)
    )

    if hr_user_ids:
        LeaveNotificationRead.objects.filter(leave=leave, user_id__in=hr_user_ids).delete()
        LeaveNotificationSeen.objects.filter(leave=leave, user_id__in=hr_user_ids).delete()


def refresh_pending_leave_notification(leave):
    if leave.status != "Pending":
        return

    reset_hr_notification_state_for_leave(leave)


def get_leave_activity_datetime(leave):
    if leave.status == "Pending":
        return leave.updated_at or leave.created_at

    if leave.status == "Approved":
        return leave.approved_at or leave.created_at

    if leave.status == "Rejected":
        return leave.rejected_at or leave.created_at

    return leave.created_at


def build_hr_pending_notifications(leaves, viewer=None):
    leaves = sorted(
        [leave for leave in leaves if leave.status == "Pending"],
        key=get_leave_activity_datetime,
        reverse=True,
    )
    pending_notifications = []
    read_ids = get_notification_read_ids_for_user(viewer, leaves) if viewer else set()
    seen_ids = get_notification_seen_ids_for_user(viewer, leaves) if viewer else set()
    unread_count = 0

    for leave in leaves:
        try:
            leave_profile = leave.user.profile
        except Profile.DoesNotExist:
            leave_profile = None

        is_read = leave.id in read_ids
        is_new = leave.id not in seen_ids
        activity_at = get_leave_activity_datetime(leave)
        schedule_text = (
            f"{leave.from_date.strftime('%b %d')}, "
            f"{localtime(leave.from_datetime).strftime('%I:%M %p')} → "
            f"{localtime(leave.to_datetime).strftime('%I:%M %p')}"
            if leave.leave_type in ["Short", "Half"]
            else f"{leave.from_date.strftime('%b %d')} → {leave.to_date.strftime('%b %d')}"
        )
        activity_label = "Updated" if leave.updated_at else "Applied"
        if not is_read:
            unread_count += 1

        pending_notifications.append({
            "id": leave.id,
            "employee_id": leave.user_id,
            "username": leave.user.username,
            "display_name": leave.user.get_full_name().strip() or leave.user.username,
            "leave_type": leave.leave_type,
            "leave_type_class": get_leave_type_class(leave.leave_type),
            "from_date": leave.from_date.strftime("%b %d"),
            "to_date": leave.to_date.strftime("%b %d"),
            "from_time": localtime(leave.from_datetime).strftime("%I:%M %p") if leave.from_datetime else "",
            "to_time": localtime(leave.to_datetime).strftime("%I:%M %p") if leave.to_datetime else "",
            "is_time_based": leave.leave_type in ["Short", "Half"],
            "created_at": localtime(activity_at).strftime("%b %d, %Y %I:%M %p"),
            "schedule_text": schedule_text,
            "activity_label": activity_label,
            "activity_text": localtime(activity_at).strftime("%b %d, %Y %I:%M %p"),
            "photo_url": leave_profile.profile_photo.url if leave_profile and leave_profile.profile_photo else None,
            "target_url": f"{reverse('manage_all')}?employee={leave.user_id}&highlight_leave={leave.id}",
            "is_read": is_read,
            "is_new": is_new,
        })

    recent_notification_type_class = pending_notifications[0]["leave_type_class"] if pending_notifications else ""

    return {
        "notifications": pending_notifications,
        "count": unread_count if viewer else len(pending_notifications),
        "recent_type_class": recent_notification_type_class,
    }


def get_hr_notification_context(user, limit=None):
    leaves = Leave.objects.select_related("user", "user__profile").order_by("-created_at")
    notification_payload = build_hr_pending_notifications(leaves, user)
    notifications = notification_payload["notifications"]

    if limit is not None:
        notifications = notifications[:limit]

    return {
        "pending_notifications": notifications,
        "pending_notification_count": notification_payload["count"],
        "recent_notification_type_class": notification_payload["recent_type_class"],
    }


def build_employee_notifications(leaves, viewer=None):
    leaves = sorted(
        [leave for leave in leaves if leave.status in ["Approved", "Rejected"]],
        key=get_leave_activity_datetime,
        reverse=True,
    )
    employee_notifications = []
    read_ids = get_notification_read_ids_for_user(viewer, leaves) if viewer else set()
    seen_ids = get_notification_seen_ids_for_user(viewer, leaves) if viewer else set()
    unread_count = 0

    for leave in leaves:
        try:
            leave_profile = leave.user.profile
        except Profile.DoesNotExist:
            leave_profile = None

        panel_target = "rejected-panel" if leave.status == "Rejected" else "approved-panel"
        is_read = leave.id in read_ids
        is_new = leave.id not in seen_ids
        activity_at = get_leave_activity_datetime(leave)
        schedule_text = (
            f"{leave.from_date.strftime('%b %d')}, "
            f"{localtime(leave.from_datetime).strftime('%I:%M %p')} → "
            f"{localtime(leave.to_datetime).strftime('%I:%M %p')}"
            if leave.leave_type in ["Short", "Half"]
            else f"{leave.from_date.strftime('%b %d')} → {leave.to_date.strftime('%b %d')}"
        )
        headline_text = f"{leave.leave_type} Leave {leave.status}!"
        applied_text = localtime(leave.created_at).strftime("%b %d, %Y %I:%M %p")
        updated_text = localtime(leave.updated_at).strftime("%b %d, %Y %I:%M %p") if leave.updated_at else ""
        if not is_read:
            unread_count += 1

        employee_notifications.append({
            "id": leave.id,
            "employee_id": leave.user_id,
            "username": leave.user.username,
            "display_name": headline_text,
            "headline_text": headline_text,
            "leave_type": leave.leave_type,
            "leave_type_class": get_leave_type_class(leave.leave_type),
            "from_date": leave.from_date.strftime("%b %d"),
            "to_date": leave.to_date.strftime("%b %d"),
            "from_time": localtime(leave.from_datetime).strftime("%I:%M %p") if leave.from_datetime else "",
            "to_time": localtime(leave.to_datetime).strftime("%I:%M %p") if leave.to_datetime else "",
            "is_time_based": leave.leave_type in ["Short", "Half"],
            "created_at": localtime(activity_at).strftime("%b %d, %Y %I:%M %p"),
            "schedule_text": schedule_text,
            "applied_text": applied_text,
            "updated_text": updated_text,
            "status": leave.status,
            "status_class": leave.status.lower(),
            "photo_url": leave_profile.profile_photo.url if leave_profile and leave_profile.profile_photo else None,
            "target_panel": panel_target,
            "target_url": f"{reverse('my_leave')}?panel={panel_target}&highlight_leave={leave.id}",
            "is_read": is_read,
            "is_new": is_new,
        })

    recent_notification_type_class = employee_notifications[0]["leave_type_class"] if employee_notifications else ""

    return {
        "notifications": employee_notifications,
        "count": unread_count if viewer else len(employee_notifications),
        "recent_type_class": recent_notification_type_class,
    }


def get_employee_notification_context(user, limit=None):
    leaves = (
        Leave.objects
        .filter(user=user, status__in=["Approved", "Rejected"])
        .select_related("user", "user__profile")
        .order_by("-created_at")
    )
    notification_payload = build_employee_notifications(leaves, user)
    notifications = notification_payload["notifications"]

    if limit is not None:
        notifications = notifications[:limit]

    return {
        "employee_notifications": notifications,
        "employee_notification_count": notification_payload["count"],
        "employee_recent_notification_type_class": notification_payload["recent_type_class"],
    }


@login_required
@never_cache
def hr_notifications(request):
    if request.user.role != "HR":
        return JsonResponse({"detail": "HR access required."}, status=403)

    leaves = Leave.objects.select_related("user", "user__profile").order_by("-created_at")
    payload = build_hr_pending_notifications(leaves, request.user)
    limit = request.GET.get("limit")

    notifications = payload["notifications"]
    if limit and str(limit).isdigit():
        notifications = notifications[:int(limit)]

    return JsonResponse({
        "count": payload["count"],
        "recent_type_class": payload["recent_type_class"],
        "notifications": notifications,
    })


@login_required
@never_cache
def employee_notifications(request):
    if request.user.role != "EMPLOYEE":
        return JsonResponse({"detail": "Employee access required."}, status=403)

    leaves = (
        Leave.objects
        .filter(user=request.user, status__in=["Approved", "Rejected"])
        .select_related("user", "user__profile")
        .order_by("-created_at")
    )
    payload = build_employee_notifications(leaves, request.user)
    limit = request.GET.get("limit")

    notifications = payload["notifications"]
    if limit and str(limit).isdigit():
        notifications = notifications[:int(limit)]

    return JsonResponse({
        "count": payload["count"],
        "recent_type_class": payload["recent_type_class"],
        "notifications": notifications,
    })


@login_required
@never_cache
@require_POST
def notifications_mark_read(request):
    payload = parse_json_request_body(request)
    ids = [str(value) for value in (payload.get("ids") or []) if str(value).strip()]
    mark_all = bool(payload.get("all"))

    if request.user.role == "HR":
        allowed_leaves = list(Leave.objects.filter(status="Pending").values_list("id", flat=True))
    else:
        allowed_leaves = list(
            Leave.objects.filter(user=request.user, status__in=["Approved", "Rejected"]).values_list("id", flat=True)
        )

    allowed_ids = {str(leave_id) for leave_id in allowed_leaves}
    target_ids = allowed_ids if mark_all else {value for value in ids if value in allowed_ids}

    if target_ids:
        try:
            LeaveNotificationRead.objects.bulk_create(
                [
                    LeaveNotificationRead(user=request.user, leave_id=int(notification_id))
                    for notification_id in target_ids
                ],
                ignore_conflicts=True,
            )
            LeaveNotificationSeen.objects.bulk_create(
                [
                    LeaveNotificationSeen(user=request.user, leave_id=int(notification_id))
                    for notification_id in target_ids
                ],
                ignore_conflicts=True,
            )
        except (OperationalError, ProgrammingError):
            pass

    try:
        read_ids = set(
            LeaveNotificationRead.objects.filter(user=request.user, leave_id__in=allowed_leaves)
            .values_list("leave_id", flat=True)
        )
    except (OperationalError, ProgrammingError):
        read_ids = set()

    return JsonResponse({
        "count": sum(1 for leave_id in allowed_leaves if leave_id not in read_ids),
        "read_ids": sorted(read_ids),
    })


@login_required
@never_cache
@require_POST
def notifications_mark_seen(request):
    payload = parse_json_request_body(request)
    ids = [str(value) for value in (payload.get("ids") or []) if str(value).strip()]

    if request.user.role == "HR":
        allowed_leaves = list(Leave.objects.filter(status="Pending").values_list("id", flat=True))
    else:
        allowed_leaves = list(
            Leave.objects.filter(user=request.user, status__in=["Approved", "Rejected"]).values_list("id", flat=True)
        )

    allowed_ids = {str(leave_id) for leave_id in allowed_leaves}
    target_ids = {value for value in ids if value in allowed_ids}

    if target_ids:
        try:
            LeaveNotificationSeen.objects.bulk_create(
                [
                    LeaveNotificationSeen(user=request.user, leave_id=int(notification_id))
                    for notification_id in target_ids
                ],
                ignore_conflicts=True,
            )
        except (OperationalError, ProgrammingError):
            pass

    return JsonResponse({
        "seen_ids": sorted(int(value) for value in target_ids),
    })
