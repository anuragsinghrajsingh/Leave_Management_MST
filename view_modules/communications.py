import json

from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils.timezone import localtime
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from App.models import Communication, CommunicationRead, CommunicationSeen, Profile


def parse_json_request_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


def truncate_communication_body(value, limit=120):
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


def get_communication_queryset(user):
    queryset = Communication.objects.select_related(
        "sender",
        "sender__profile",
        "recipient",
        "recipient__profile",
    )

    if user.role == "HR":
        return queryset.filter(
            Q(sender=user) |
            Q(recipient=user) |
            Q(audience_role="HR")
        ).order_by("-created_at")

    return queryset.filter(
        Q(sender=user) |
        Q(recipient=user) |
        Q(message_type="ANNOUNCEMENT", audience_role="EMPLOYEE")
    ).order_by("-created_at")


def get_communication_read_ids_for_user(user, communications):
    communication_ids = [communication.id for communication in communications]

    if not communication_ids:
        return set()

    try:
        return set(
            CommunicationRead.objects.filter(user=user, communication_id__in=communication_ids)
            .values_list("communication_id", flat=True)
        )
    except (OperationalError, ProgrammingError):
        return set()


def get_communication_seen_ids_for_user(user, communications):
    communication_ids = [communication.id for communication in communications]

    if not communication_ids:
        return set()

    try:
        return set(
            CommunicationSeen.objects.filter(user=user, communication_id__in=communication_ids)
            .values_list("communication_id", flat=True)
        )
    except (OperationalError, ProgrammingError):
        return set()


def build_communication_items(communications, viewer, read_ids=None, seen_ids=None):
    items = []
    read_ids = read_ids or set()
    seen_ids = seen_ids or set()

    for communication in communications:
        try:
            sender_profile = communication.sender.profile
        except Profile.DoesNotExist:
            sender_profile = None

        sender_name = communication.sender.get_full_name().strip() or communication.sender.username
        recipient_name = ""

        if communication.recipient_id:
            recipient_name = communication.recipient.get_full_name().strip() or communication.recipient.username

        if communication.message_type == "ANNOUNCEMENT":
            audience_label = "All employees"
            direction_class = "announcement"
            item_title = communication.title.strip() or "Announcement"
            type_label = "Announcement"
        elif communication.sender_id == viewer.id:
            audience_label = "To HR" if communication.audience_role == "HR" else (recipient_name or "Direct message")
            direction_class = "outgoing"
            item_title = communication.title.strip() or "Message sent"
            type_label = "Sent"
        else:
            audience_label = "From " + sender_name
            direction_class = "incoming"
            item_title = communication.title.strip() or "New message"
            type_label = "Inbox"

        is_outgoing = communication.sender_id == viewer.id
        is_read = is_outgoing or communication.id in read_ids
        is_new = (not is_outgoing) and communication.id not in seen_ids

        items.append({
            "id": communication.id,
            "title": item_title,
            "body_preview": truncate_communication_body(communication.body),
            "body_full": communication.body,
            "created_at": localtime(communication.created_at).strftime("%b %d, %Y %I:%M %p"),
            "sender_name": sender_name,
            "recipient_name": recipient_name,
            "audience_label": audience_label,
            "direction_class": direction_class,
            "type_label": type_label,
            "type_class": "announcement" if communication.message_type == "ANNOUNCEMENT" else "direct",
            "is_outgoing": is_outgoing,
            "is_read": is_read,
            "is_new": is_new,
            "photo_url": sender_profile.profile_photo.url if sender_profile and sender_profile.profile_photo else None,
            "username": communication.sender.username,
        })

    return items


def get_communication_badge_count(queryset, user):
    incoming_ids = list(queryset.exclude(sender=user).values_list("id", flat=True))

    if not incoming_ids:
        return 0

    try:
        read_ids = set(
            CommunicationRead.objects.filter(user=user, communication_id__in=incoming_ids)
            .values_list("communication_id", flat=True)
        )
    except (OperationalError, ProgrammingError):
        read_ids = set()

    return sum(1 for communication_id in incoming_ids if communication_id not in read_ids)


def get_communication_recipients_for_user(user):
    if user.role != "HR":
        return []

    employees = get_user_model().objects.filter(role="EMPLOYEE").select_related("profile").order_by("first_name", "username")
    recipients = []

    for employee in employees:
        recipients.append({
            "id": employee.id,
            "label": employee.get_full_name().strip() or employee.username,
        })

    return recipients


def get_communication_context(user, limit=8):
    queryset = get_communication_queryset(user)
    communications = list(queryset[:limit])
    read_ids = get_communication_read_ids_for_user(user, communications)
    seen_ids = get_communication_seen_ids_for_user(user, communications)
    items = build_communication_items(communications, user, read_ids, seen_ids)

    return {
        "communication_items": items,
        "communication_count": get_communication_badge_count(queryset, user),
        "communication_recipients": get_communication_recipients_for_user(user),
        "communication_empty_text": "No announcements or messages yet.",
    }


@login_required
@never_cache
def communications_feed(request):
    queryset = get_communication_queryset(request.user)
    communications = list(queryset[:8])
    read_ids = get_communication_read_ids_for_user(request.user, communications)
    seen_ids = get_communication_seen_ids_for_user(request.user, communications)
    items = build_communication_items(communications, request.user, read_ids, seen_ids)
    return JsonResponse({
        "count": get_communication_badge_count(queryset, request.user),
        "items": items,
    })


@login_required
@never_cache
@require_POST
def communications_mark_read(request):
    payload = parse_json_request_body(request)
    ids = [str(value) for value in (payload.get("ids") or []) if str(value).strip()]
    target_type = str(payload.get("target_type") or "").strip().upper()

    queryset = get_communication_queryset(request.user).exclude(sender=request.user)

    if target_type == "ANNOUNCEMENT":
        queryset = queryset.filter(message_type="ANNOUNCEMENT")
    elif target_type == "DIRECT":
        queryset = queryset.filter(message_type="DIRECT")

    if ids:
        queryset = queryset.filter(id__in=ids)

    communication_ids = list(queryset.values_list("id", flat=True))

    if communication_ids:
        try:
            CommunicationRead.objects.bulk_create(
                [
                    CommunicationRead(user=request.user, communication_id=communication_id)
                    for communication_id in communication_ids
                ],
                ignore_conflicts=True,
            )
            CommunicationSeen.objects.bulk_create(
                [
                    CommunicationSeen(user=request.user, communication_id=communication_id)
                    for communication_id in communication_ids
                ],
                ignore_conflicts=True,
            )
        except (OperationalError, ProgrammingError):
            pass

    full_queryset = get_communication_queryset(request.user)
    communications = list(full_queryset[:8])
    read_ids = get_communication_read_ids_for_user(request.user, communications)
    seen_ids = get_communication_seen_ids_for_user(request.user, communications)
    items = build_communication_items(communications, request.user, read_ids, seen_ids)

    return JsonResponse({
        "count": get_communication_badge_count(full_queryset, request.user),
        "items": items,
    })


@login_required
@never_cache
@require_POST
def communications_send(request):
    user = request.user
    message_type = (request.POST.get("message_type") or "DIRECT").strip().upper()
    title = (request.POST.get("title") or "").strip()
    body = (request.POST.get("body") or "").strip()

    if not body:
        return JsonResponse({"error": "Message body is required."}, status=400)

    if len(body) > 1500:
        return JsonResponse({"error": "Message is too long."}, status=400)

    if len(title) > 140:
        return JsonResponse({"error": "Title is too long."}, status=400)

    if user.role == "HR":
        if message_type == "ANNOUNCEMENT":
            Communication.objects.create(
                sender=user,
                message_type="ANNOUNCEMENT",
                audience_role="EMPLOYEE",
                title=title,
                body=body,
            )
        elif message_type == "DIRECT":
            recipient_id = request.POST.get("recipient_id")
            recipient = get_object_or_404(get_user_model(), id=recipient_id, role="EMPLOYEE")
            Communication.objects.create(
                sender=user,
                recipient=recipient,
                message_type="DIRECT",
                title=title,
                body=body,
            )
        else:
            return JsonResponse({"error": "Invalid communication type."}, status=400)

    elif user.role == "EMPLOYEE":
        if message_type != "DIRECT":
            return JsonResponse({"error": "Employees can only send direct messages."}, status=403)

        Communication.objects.create(
            sender=user,
            message_type="DIRECT",
            audience_role="HR",
            title=title,
            body=body,
        )
    else:
        return JsonResponse({"error": "Unsupported role."}, status=403)

    queryset = get_communication_queryset(user)
    communications = list(queryset[:8])
    read_ids = get_communication_read_ids_for_user(user, communications)
    seen_ids = get_communication_seen_ids_for_user(user, communications)
    items = build_communication_items(communications, user, read_ids, seen_ids)
    return JsonResponse({
        "success": True,
        "count": get_communication_badge_count(queryset, user),
        "items": items,
    })


@login_required
@never_cache
@require_POST
def communications_mark_seen(request):
    payload = parse_json_request_body(request)
    ids = [str(value) for value in (payload.get("ids") or []) if str(value).strip()]
    queryset = get_communication_queryset(request.user).exclude(sender=request.user)

    if ids:
        queryset = queryset.filter(id__in=ids)

    communication_ids = list(queryset.values_list("id", flat=True))

    if communication_ids:
        try:
            CommunicationSeen.objects.bulk_create(
                [
                    CommunicationSeen(user=request.user, communication_id=communication_id)
                    for communication_id in communication_ids
                ],
                ignore_conflicts=True,
            )
        except (OperationalError, ProgrammingError):
            pass

    full_queryset = get_communication_queryset(request.user)
    communications = list(full_queryset[:8])
    read_ids = get_communication_read_ids_for_user(request.user, communications)
    seen_ids = get_communication_seen_ids_for_user(request.user, communications)
    items = build_communication_items(communications, request.user, read_ids, seen_ids)
    return JsonResponse({
        "count": get_communication_badge_count(full_queryset, request.user),
        "items": items,
    })
