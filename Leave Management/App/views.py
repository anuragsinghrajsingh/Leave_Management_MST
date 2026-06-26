from datetime import date, datetime, time, timedelta
from django.utils.timezone import localtime, localdate, now
from django.utils import timezone
from calendar import monthrange
import os,json
import hashlib
import logging
import math
import re
import uuid
import secrets
import time as time_module
from django.contrib import messages
from django.contrib.messages import get_messages
from django.shortcuts import render, redirect, get_object_or_404
from App.utils.logger_utils import log_leave_action, log_profile_update
from App.services.public_holidays import get_public_holidays
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from .models import AdminAuditLog, Communication, CommunicationRead, CommunicationSeen, CompanyHoliday, Leave, LeaveBalance, LeaveNotificationRead, LeaveNotificationSeen, Profile, PushSubscription # , CompanyClosure,
from django.views.decorators.cache import never_cache
from django.core.cache import cache
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction, OperationalError, ProgrammingError
from django.db import models
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.html import escape
from django.template.loader import render_to_string
from django.core.exceptions import ValidationError
from django.core.mail import EmailMessage
from django.core.files.base import ContentFile
from django.core.validators import validate_email
from django.conf import settings
from django.contrib.staticfiles import finders
import os
from io import BytesIO
from App.services.employee_welcome_service import send_employee_welcome_package
from App.services.forced_password_service import send_forced_password_email, user_can_be_forced_to_change_password
from App.services.login_lock_service import remember_failed_login_ip
from App.services.login_lock_service import get_login_lock_status as get_combined_login_lock_status
from App.services.push_notifications import send_push_to_user
from App.services.background_tasks import enqueue_background_task

security_logger = logging.getLogger("lms_security")

PROFILE_PHOTO_MAX_UPLOAD_BYTES = 3 * 1024 * 1024
PROFILE_PHOTO_MAX_PIXELS = 16_000_000
PROFILE_PHOTO_MAX_SIDE = 2048
REJECTION_REASON_MAX_LENGTH = 500
LEAVE_REASON_MAX_LENGTH = 1000
EMPLOYEE_ARCHIVE_DOWNLOAD_MAX_AGE_SECONDS = 5 * 60
MAX_READ_SEEN_ACTION_IDS = 5
MAX_NOTIFICATION_FEED_LIMIT = 50
MAX_NOTIFICATION_FEED_OFFSET = 1000
EMPLOYEE_PHONE_MAX_LENGTH = 14
EMPLOYEE_ADDRESS_MAX_LENGTH = 500
EMPLOYEE_LEAVE_TOTAL_MAX = 30
EMPLOYEE_USERNAME_MAX_LENGTH = 150
EMPLOYEE_NAME_MAX_LENGTH = 150
EMPLOYEE_EMAIL_MAX_LENGTH = 254
EMPLOYEE_DEPARTMENT_MAX_LENGTH = 100
PROFILE_BIO_MAX_LENGTH = 250
PROFILE_BIO_MAX_WORDS = 50
EMPLOYEE_PHONE_PATTERN = re.compile(r"^(?:\+91[\s-]?|91)?([6-9]\d{9})$")
EMPLOYEE_USERNAME_PATTERN = re.compile(r"^[\w.@+-]+$")
ALLOWED_LEAVE_TYPES = {choice[0] for choice in Leave.LEAVE_TYPES}
ALLOWED_PROFILE_ID_ROLES = {choice[0] for choice in Profile.ROLE_CHOICES}
ALLOWED_LEAVE_FILTER_STATUSES = {choice[0] for choice in Leave.STATUS}
ALLOWED_LEAVE_FILTER_FIELDS = {"leave_type", "month", "date_range"}


def get_portal_link():
    return f"{settings.PORTAL_BASE_URL}/"


def _leave_push_date_text(leave):
    if leave.from_date == leave.to_date:
        return leave.from_date.strftime("%d %b %Y")
    return f"{leave.from_date.strftime('%d %b %Y')} to {leave.to_date.strftime('%d %b %Y')}"


def _aware_datetime(value):
    return timezone.make_aware(value) if timezone.is_naive(value) else value


def _get_short_half_min_notice_minutes():
    try:
        return max(0, int(getattr(settings, "SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES", 15)))
    except (TypeError, ValueError):
        return 15


def _get_short_half_grace_minutes():
    try:
        return max(0, int(getattr(settings, "SHORT_HALF_LEAVE_GRACE_MINUTES", 0)))
    except (TypeError, ValueError):
        return 0


def _format_minutes_duration(minutes):
    minutes = max(0, int(minutes or 0))
    if minutes and minutes % 60 == 0:
        hours = minutes // 60
        return f"{hours} hour" if hours == 1 else f"{hours} hours"
    if minutes >= 60:
        hours = minutes // 60
        remaining_minutes = minutes % 60
        hour_text = f"{hours} hour" if hours == 1 else f"{hours} hours"
        minute_text = f"{remaining_minutes} minute" if remaining_minutes == 1 else f"{remaining_minutes} minutes"
        return f"{hour_text} {minute_text}" if remaining_minutes else hour_text
    return f"{minutes} minute" if minutes == 1 else f"{minutes} minutes"


def _get_sick_leave_same_day_cutoff_time():
    raw_value = getattr(settings, "SICK_LEAVE_SAME_DAY_CUTOFF_TIME", "11:59")
    if isinstance(raw_value, time):
        return raw_value
    try:
        return datetime.strptime(str(raw_value).strip(), "%H:%M").time()
    except (TypeError, ValueError):
        return time(11, 59)


def _format_clock_time(value):
    return value.strftime("%I:%M %p").lstrip("0")


def _is_after_sick_leave_same_day_cutoff(current_time, cutoff_time):
    return (current_time.hour, current_time.minute) > (cutoff_time.hour, cutoff_time.minute)


def _get_apply_leave_rule_config():
    min_notice_minutes = _get_short_half_min_notice_minutes()
    grace_minutes = _get_short_half_grace_minutes()
    sick_cutoff = _get_sick_leave_same_day_cutoff_time()
    return {
        "shortHalfMinNoticeMinutes": min_notice_minutes,
        "shortHalfGraceMinutes": grace_minutes,
        "shortHalfMinNoticeLabel": _format_minutes_duration(min_notice_minutes),
        "shortHalfGraceLabel": _format_minutes_duration(grace_minutes),
        "sickSameDayCutoffTime": sick_cutoff.strftime("%H:%M"),
        "sickSameDayCutoffLabel": _format_clock_time(sick_cutoff),
    }


def queue_hr_leave_push(leave, action_label):
    User = get_user_model()
    employee_name = leave.user.get_full_name().strip() or leave.user.username
    title = f"{action_label}: {employee_name}"
    body = f"{leave.leave_type} leave for {_leave_push_date_text(leave)}."
    url = reverse("manage_all")
    recipients = list(User.objects.filter(role="HR", is_active=True))

    for recipient in recipients:
        transaction.on_commit(
            lambda recipient=recipient, title=title, body=body, url=url, leave_id=leave.pk: enqueue_background_task(
                send_push_to_user,
                recipient,
                title,
                body,
                url=url,
                tag=f"leave-{leave_id}-hr",
                kind="leave",
                task_name="hr_leave_push",
            )
        )


def queue_employee_leave_push(leave, status_label):
    title = f"Leave {status_label.lower()}"
    body = f"Your {leave.leave_type} leave for {_leave_push_date_text(leave)} was {status_label.lower()}."
    url = reverse("my_leave")
    transaction.on_commit(
        lambda user=leave.user, title=title, body=body, url=url, leave_id=leave.pk, status=status_label.lower(): enqueue_background_task(
            send_push_to_user,
            user,
            title,
            body,
            url=url,
            tag=f"leave-{leave_id}-{status}",
            kind=f"leave_{status}",
            task_name="employee_leave_push",
        )
    )


def queue_communication_push(sender, *, recipient=None, audience_role="", message_type="DIRECT", title="", body=""):
    User = get_user_model()
    sender_name = sender.get_full_name().strip() or sender.username
    clean_title = title or ("Announcement" if message_type == "ANNOUNCEMENT" else "New message")
    clean_body = body[:140] if body else f"From {sender_name}"
    url = reverse("dashboard") if audience_role == "EMPLOYEE" else reverse("manage_all")

    if recipient:
        recipients = [recipient]
        url = reverse("dashboard") if recipient.role == "EMPLOYEE" else reverse("manage_all")
    elif audience_role:
        recipients = list(User.objects.filter(role=audience_role, is_active=True))
    else:
        recipients = []

    for target_user in recipients:
        if target_user.pk == sender.pk:
            continue
        transaction.on_commit(
            lambda target_user=target_user, clean_title=clean_title, clean_body=clean_body, url=url, message_type=message_type: enqueue_background_task(
                send_push_to_user,
                target_user,
                clean_title,
                clean_body,
                url=url,
                tag=f"communication-{message_type.lower()}-{target_user.pk}",
                kind="announcement" if message_type == "ANNOUNCEMENT" else "message",
                task_name="communication_push",
            )
        )


def get_employee_archive_cache_key(token):
    return f"employee_archive_download:{token}"


def service_worker(request):
    service_worker_path = finders.find("js/service-worker.js")
    if not service_worker_path:
        return HttpResponse("", content_type="application/javascript", status=404)
    with open(service_worker_path, "r", encoding="utf-8") as service_worker_file:
        response = HttpResponse(service_worker_file.read(), content_type="application/javascript")
    response["Service-Worker-Allowed"] = "/"
    response["Cache-Control"] = "no-cache"
    return response


def get_leave_alert_recipients():
    recipients = [settings.LEAVE_RECORD_EMAIL] if settings.LEAVE_RECORD_EMAIL else []
    recipients.extend(
        get_user_model().objects
        .filter(role="HR", is_active=True)
        .exclude(email="")
        .values_list("email", flat=True)
    )
    return list(dict.fromkeys(email for email in recipients if email))


def get_leave_decision_email_recipients(employee):
    recipients = [getattr(employee, "email", ""), settings.LEAVE_RECORD_EMAIL]
    return list(dict.fromkeys(email for email in recipients if email))


def normalize_employee_phone(phone):
    phone = (phone or "").strip()
    if len(phone) > 25:
        raise ValueError("Phone number is too long.")

    compact_phone = re.sub(r"[\s-]+", "", phone)
    match = EMPLOYEE_PHONE_PATTERN.fullmatch(compact_phone)
    if not match:
        raise ValueError("Phone must be a valid 10-digit Indian mobile number.")

    return f"+91 {match.group(1)}"


def validate_employee_address(address):
    address = (address or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    if len(address) > EMPLOYEE_ADDRESS_MAX_LENGTH:
        raise ValueError(f"Address must be {EMPLOYEE_ADDRESS_MAX_LENGTH} characters or less.")

    if any(ord(character) < 32 and character not in "\n\t" for character in address):
        raise ValueError("Address contains unsupported characters.")

    return address


def validate_plain_text_field(value, label, max_length):
    value = (value or "").strip()
    if len(value) > max_length:
        raise ValueError(f"{label} must be {max_length} characters or less.")

    if any(ord(character) < 32 for character in value):
        raise ValueError(f"{label} contains unsupported characters.")

    return value


def validate_employee_username(username):
    username = validate_plain_text_field(username, "Username", EMPLOYEE_USERNAME_MAX_LENGTH)
    if username and not EMPLOYEE_USERNAME_PATTERN.fullmatch(username):
        raise ValueError("Username can contain only letters, numbers, and @/./+/-/_ characters.")
    return username


def validate_employee_email(email):
    email = validate_plain_text_field(email, "Work email", EMPLOYEE_EMAIL_MAX_LENGTH)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise ValueError("Please enter a valid work email address.")
    return email


def validate_employee_leave_total(value, label):
    try:
        total = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{label} total must be a valid number.")

    if not math.isfinite(total):
        raise ValueError(f"{label} total must be a normal finite number.")

    if total < 0:
        raise ValueError(f"{label} total cannot be negative.")

    if total > EMPLOYEE_LEAVE_TOTAL_MAX:
        raise ValueError(f"{label} total cannot be more than {EMPLOYEE_LEAVE_TOTAL_MAX}.")

    return total


def validate_profile_bio(bio):
    bio = (bio or "").strip().replace("\r\n", "\n").replace("\r", "\n")
    if len(bio) > PROFILE_BIO_MAX_LENGTH:
        raise ValueError(f"Bio must be {PROFILE_BIO_MAX_LENGTH} characters or less.")

    if len(bio.split()) > PROFILE_BIO_MAX_WORDS:
        raise ValueError(f"Bio must be {PROFILE_BIO_MAX_WORDS} words or fewer.")

    if any(ord(character) < 32 and character not in "\n\t" for character in bio):
        raise ValueError("Bio contains unsupported characters.")

    return bio


def get_valid_leave_type(raw_leave_type):
    leave_type = (raw_leave_type or "").strip()
    return leave_type if leave_type in ALLOWED_LEAVE_TYPES else None


def get_valid_leave_status(raw_status):
    status = (raw_status or "").strip()
    return status if status in ALLOWED_LEAVE_FILTER_STATUSES else None


def get_valid_filter_month(raw_month):
    month = (raw_month or "").strip()
    if not month:
        return None

    if not re.fullmatch(r"\d{4}-\d{2}", month):
        raise ValueError("Invalid month filter.")

    year, month_number = map(int, month.split("-"))
    if year < 2000 or year > 2100 or month_number < 1 or month_number > 12:
        raise ValueError("Invalid month filter.")

    return month


def get_valid_filter_date(raw_date, field_label):
    value = (raw_date or "").strip()
    if not value:
        return None

    try:
        date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid {field_label} filter.")

    return value


def get_capped_positive_int(raw_value, *, default=None, maximum=MAX_NOTIFICATION_FEED_LIMIT):
    value = (raw_value or "").strip()
    if not value:
        return default

    if not value.isdigit():
        return default

    parsed_value = int(value)
    if parsed_value <= 0:
        return default

    return min(parsed_value, maximum)


def get_nonnegative_int(raw_value, *, default=0):
    value = (raw_value or "").strip()
    if not value or not value.isdigit():
        return default

    return int(value)


def get_capped_notification_offset(raw_value):
    offset = get_nonnegative_int(raw_value)
    if offset > MAX_NOTIFICATION_FEED_OFFSET:
        return None
    return offset


def store_apply_leave_form_state(request):
    leave_type = get_valid_leave_type(request.POST.get("leave_type"))
    safe_form_data = {
        "leave_type": leave_type or "",
        "from_date": (request.POST.get("from_date") or "").strip(),
        "to_date": (request.POST.get("to_date") or "").strip(),
        "from_datetime": (request.POST.get("from_datetime") or "").strip(),
        "to_datetime": (request.POST.get("to_datetime") or "").strip(),
        "to_date_hidden": (request.POST.get("to_date_hidden") or "").strip(),
        "reason": (request.POST.get("reason") or "").strip()[:1000],
    }
    request.session["apply_leave_form"] = safe_form_data


def _apply_leave_response(request, status=400):
    if _is_ajax_request(request):
        request.session.pop("apply_leave_form", None)
        return JsonResponse({
            "success": False,
            "redirect_url": reverse("apply_leave"),
            "messages": _serialize_flash_messages(request),
        }, status=status)

    return redirect("apply_leave")


def _profile_photo_filename(profile, extension, update_count=None):
    username = getattr(getattr(profile, "user", None), "username", "") or "employee"
    employee_id = getattr(profile, "employee_id", "") or "profile"
    filename_root = re.sub(r"[^A-Za-z0-9_-]+", "_", f"{username}_{employee_id}").strip("_")
    version_suffix = f"({update_count})" if update_count else ""
    return f"{filename_root or 'employee_profile'}{version_suffix}.{extension}"


def _sanitize_profile_photo_upload(photo, profile=None, update_count=None):
    from PIL import Image, ImageOps

    if photo.size > PROFILE_PHOTO_MAX_UPLOAD_BYTES:
        raise ValueError("Image must be under 3MB.")

    try:
        photo.seek(0)
        with Image.open(photo) as image:
            source_format = image.format

            if source_format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Only JPG, PNG or WEBP images allowed.")

            width, height = image.size
            if width <= 0 or height <= 0 or width * height > PROFILE_PHOTO_MAX_PIXELS:
                raise ValueError("Image dimensions are too large.")

            image.verify()

        photo.seek(0)
        with Image.open(photo) as image:
            image = ImageOps.exif_transpose(image)
            image.thumbnail((PROFILE_PHOTO_MAX_SIDE, PROFILE_PHOTO_MAX_SIDE), Image.Resampling.LANCZOS)

            has_alpha = image.mode in {"RGBA", "LA"} or (
                image.mode == "P" and "transparency" in image.info
            )

            output = BytesIO()
            if has_alpha:
                sanitized = image.convert("RGBA")
                sanitized.save(output, format="PNG", optimize=True)
                extension = "png"
            else:
                sanitized = image.convert("RGB")
                sanitized.save(output, format="JPEG", quality=90, optimize=True)
                extension = "jpg"

    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Invalid image file.") from exc

    output.seek(0)
    filename_root = (
        os.path.splitext(os.path.basename(photo.name or "profile-photo"))[0] or "profile-photo"
    )
    if profile is not None:
        filename_root = os.path.splitext(
            _profile_photo_filename(profile, extension, update_count=update_count)
        )[0]

    return ContentFile(output.read(), name=f"{filename_root}.{extension}")


def _delete_profile_photo_file(profile_photo, keep_name=None):
    if not profile_photo:
        return

    old_name = getattr(profile_photo, "name", "")
    if not old_name or old_name == keep_name:
        return

    try:
        storage = profile_photo.storage
        if storage.exists(old_name):
            storage.delete(old_name)
    except Exception:
        security_logger.exception("Failed to delete old profile photo: %s", old_name)


def _profile_photo_url(profile):
    if profile and getattr(profile, "has_profile_photo_file", False):
        return profile.profile_photo.url
    return None


def send_branded_email(
    subject,
    template_name,
    context,
    to_email,
    reply_to=None,
    from_email=None,
    email_type="branded",
    related_user=None,
    related_leave=None,
    triggered_by=None,
):
    """Helper to send a branded HTML email with an embedded logo."""
    html_content = render_to_string(template_name, context)

    # Ensure to_email is a list
    if isinstance(to_email, str):
        to_email = [to_email]

    sender = f"HR Portal <{from_email or settings.DEFAULT_FROM_EMAIL}>"
    email = EmailMessage(
        subject=subject,
        body=html_content,
        from_email=sender,
        to=to_email,
    )
    if reply_to:
        email.reply_to = [reply_to]

    email.content_subtype = "html"

    # Attach the logo as a CID
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'ms-technology-logo.png')
    if os.path.exists(logo_path):
        with open(logo_path, 'rb') as f:
            from email.mime.image import MIMEImage
            img = MIMEImage(f.read())
            img.add_header('Content-ID', '<logo_image>')
            img.add_header('Content-Disposition', 'inline', filename='logo.png')
            email.attach(img)

    from App.services.email_delivery_log import record_email_delivery
    from App.utils.logger_utils import log_email_sent_by_email
    error_message = ""
    try:
        sent_count = email.send(fail_silently=False)
        send_succeeded = sent_count > 0
    except Exception as exc:
        send_succeeded = False
        error_message = str(exc)
        security_logger.exception("BRANDED_EMAIL_SEND_FAILED | Subject: %s", subject)

    for addr in to_email:
        log_email_sent_by_email(addr, subject, success=send_succeeded)
    record_email_delivery(
        subject=subject,
        recipients=to_email,
        status="sent" if send_succeeded else "failed",
        email_type=email_type,
        from_email=sender,
        error_message=error_message,
        related_user=related_user,
        related_leave=related_leave,
        triggered_by=triggered_by,
        metadata={"template": template_name, "reply_to": reply_to or ""},
    )


def _get_leave_day_display(leave):
    if leave.leave_type == "Short":
        return {
            "days_value": 0.25,
            "days_value_display": "0.25 day",
            "days_target": 0.25,
            "days_suffix": "",
            "days_label": "day",
        }

    if leave.leave_type == "Half":
        return {
            "days_value": 0.5,
            "days_value_display": "0.5 day",
            "days_target": 0.5,
            "days_suffix": "",
            "days_label": "day",
        }

    from App.services.leave_breakdown import calculate_leave_breakdown_for_leave

    working_days = calculate_leave_breakdown_for_leave(leave)["working_days"]
    safe_days = max(int(working_days or 0), 0)
    return {
        "days_value": safe_days,
        "days_value_display": str(safe_days),
        "days_target": safe_days,
        "days_suffix": "",
        "days_label": "day" if safe_days == 1 else "days",
    }




def _get_flash_title(message_tags):
    tags = message_tags or ""

    if "success" in tags:
        return "Success"
    if "error" in tags:
        return "Action needed"
    if "warning" in tags:
        return "Please note"
    return "Update"


def _serialize_flash_messages(request):
    serialized_messages = []

    for message in get_messages(request):
        serialized_messages.append({
            "tags": message.tags,
            "text": str(message),
            "title": _get_flash_title(message.tags),
        })

    return serialized_messages


def _is_ajax_request(request):
    return request.headers.get("x-requested-with") == "XMLHttpRequest"


def _my_leave_response(request, status=200, **extra):
    if _is_ajax_request(request):
        payload = {
            "success": status < 400,
            "messages": _serialize_flash_messages(request),
        }
        payload.update(extra)
        return JsonResponse(payload, status=status)

    return redirect("my_leave")


def _calculate_total_leave_balance(sick_total=0, earned_total=0):
    return max(float(sick_total or 0) + float(earned_total or 0), 0)


def _remaining_from_balance(balance):
    if not balance:
        return 0
    return float(getattr(balance, "total_leave_remaining", 0) or 0)


def _get_company_holiday(target_date):
    if not target_date:
        return None
    return CompanyHoliday.objects.filter(date=target_date).first()


def _get_blocking_company_holiday(target_date):
    holiday = _get_company_holiday(target_date)
    if holiday and not holiday.is_optional:
        return holiday
    return None


def _get_upcoming_company_holiday(today=None):
    today = today or localdate()
    return CompanyHoliday.objects.filter(date__gte=today).order_by("date").first()


def _serialize_leave_for_my_leave(leave):
    leave_type_class = (leave.leave_type or "").lower()

    if leave.leave_type == "Short":
        day_display = {
            "days_value": 2,
            "days_value_display": "2 hour",
            "days_target": 2,
            "days_suffix": " hour",
            "days_label": "of the day",
        }
    elif leave.leave_type == "Half":
        day_display = {
            "days_value": 4,
            "days_value_display": "4 hour",
            "days_target": 4,
            "days_suffix": " hour",
            "days_label": "of the day",
        }
    else:
        from App.services.leave_breakdown import calculate_leave_breakdown_for_leave

        working_days = calculate_leave_breakdown_for_leave(leave)["working_days"]
        safe_days = max(int(working_days or 0), 0)
        day_display = {
            "days_value": safe_days,
            "days_value_display": str(safe_days),
            "days_target": safe_days,
            "days_suffix": "",
            "days_label": "day" if safe_days == 1 else "days",
        }

    if leave.leave_type == "Short":
        leave_code = "S"
    elif leave.leave_type == "Half":
        leave_code = "H"
    else:
        leave_code = (leave.leave_type or "")[:1].upper()

    leave_symbol = {
        "Sick": "✚",
        "Unpaid": "☕",
        "Earned": "★",
        "Short": "◷",
        "Half": "◐",
    }.get(leave.leave_type, "✦")

    updated_count = leave.no_of_times_updated or 0
    reviewed_by = getattr(leave, "reviewed_by", None)
    reviewer_name = ""
    if reviewed_by:
        reviewer_name = reviewed_by.get_full_name().strip() or reviewed_by.username

    return {
        "id": leave.id,
        "leave_type": leave.leave_type,
        "leave_type_class": leave_type_class,
        "leave_code": leave_code,
        "leave_symbol": leave_symbol,
        "from_date": leave.from_date.strftime("%Y-%m-%d"),
        "to_date": leave.to_date.strftime("%Y-%m-%d"),
        "from_date_display": leave.from_date.strftime("%b %d, %Y"),
        "to_date_display": leave.to_date.strftime("%b %d, %Y"),
        "from_datetime_iso": localtime(leave.from_datetime).isoformat() if leave.from_datetime else "",
        "to_datetime_iso": localtime(leave.to_datetime).isoformat() if leave.to_datetime else "",
        "from_time_display": localtime(leave.from_datetime).strftime("%I:%M %p") if leave.from_datetime else "",
        "to_time_display": localtime(leave.to_datetime).strftime("%I:%M %p") if leave.to_datetime else "",
        "is_time_based": leave.leave_type in ["Short", "Half"],
        "reason": leave.reason or "",
        "updated_iso": localtime(leave.updated_at).isoformat() if leave.updated_at else "",
        "updated_date_display": localtime(leave.updated_at).strftime("%b %d, %Y") if leave.updated_at else "-",
        "updated_time_display": localtime(leave.updated_at).strftime("%I:%M %p") if leave.updated_at else "",
        "updated_count": updated_count,
        "reviewed_by_id": reviewed_by.id if reviewed_by else None,
        "reviewed_by_name": reviewer_name,
        "days_value": day_display["days_value"],
        "days_value_display": day_display["days_value_display"],
        "days_target": day_display["days_target"],
        "days_suffix": day_display["days_suffix"],
        "days_label": day_display["days_label"],
        "pending_count": Leave.objects.filter(user=leave.user, status="Pending").count(),
    }

@never_cache
def role_select(request):

    if request.user.is_authenticated:

        if request.user.role == "EMPLOYEE":
            return redirect("dashboard")

        elif request.user.role == "HR":
            return redirect("hr_dashboard")

        elif request.user.role == "Admin":
            return redirect("admin:index")

        elif request.user.is_superuser:
            return redirect("admin:index")

    return render(request, "role_select.html")


def _show_login_failure_message(request, username, expected_role, portal_label):
    _set_login_error_message(request)


LOGIN_RATE_LIMITS = {
    "ADMIN": {"max_attempts": 5, "window": 15 * 60, "lockout": 30 * 60},
    "HR": {"max_attempts": 5, "window": 15 * 60, "lockout": 15 * 60},
    "EMPLOYEE": {"max_attempts": 5, "window": 15 * 60, "lockout": 15 * 60},
}
LOGIN_PROGRESSIVE_DELAYS = {
    3: 5,
    4: 10,
}
LOGIN_BULK_IP_ALERT_ATTEMPTS = 10


def _get_client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def _login_cache_token(value):
    normalized = str(value or "blank").strip().lower()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _login_cache_key(kind, portal, value):
    return f"login_rate:{portal.lower()}:{kind}:{_login_cache_token(value)}"


def _get_login_rate_config(portal):
    return LOGIN_RATE_LIMITS.get(portal, LOGIN_RATE_LIMITS["EMPLOYEE"])


def _safe_login_username(username):
    return (username or "").strip()


def _format_retry_after(seconds):
    seconds = max(int(seconds or 0), 0)
    if seconds <= 0:
        return "later"

    minutes = (seconds + 59) // 60
    if minutes < 60:
        return f"after {minutes} minute{'s' if minutes != 1 else ''}"

    hours = minutes // 60
    remaining_minutes = minutes % 60
    if remaining_minutes:
        return f"after {hours} hour{'s' if hours != 1 else ''} {remaining_minutes} minute{'s' if remaining_minutes != 1 else ''}"
    return f"after {hours} hour{'s' if hours != 1 else ''}"


def _set_login_error_message(request, locked=False, remaining_seconds=None, attempts_remaining=None):
    if locked:
        retry_after = _format_retry_after(remaining_seconds)
        messages.error(request, f"Too many login attempts. Please try again {retry_after}.", extra_tags="clear-password")
    else:
        if attempts_remaining is None:
            messages.error(request, "Invalid username or password.", extra_tags="clear-password")
        else:
            messages.error(
                request,
                f"Invalid username or password.\n{attempts_remaining} attempt{'s' if attempts_remaining != 1 else ''} remaining before temporary lockout.",
                extra_tags="clear-password",
            )


def _get_login_lock_status(portal, username, ip_address):
    status = get_combined_login_lock_status(portal, username, ip_address)
    return status.remaining_seconds


def _clear_login_rate_state(portal, username, ip_address):
    cache.delete_many([
        _login_cache_key("fail_user", portal, username),
        _login_cache_key("fail_ip", portal, ip_address),
        _login_cache_key("lock_user", portal, username),
        _login_cache_key("lock_ip", portal, ip_address),
    ])


def _increment_login_counter(key, timeout):
    current = int(cache.get(key, 0) or 0) + 1
    cache.set(key, current, timeout)
    return current


def _maybe_delay_failed_login(attempt_count):
    delay_seconds = LOGIN_PROGRESSIVE_DELAYS.get(attempt_count, 0)
    if delay_seconds <= 0:
        return
    time_module.sleep(delay_seconds)


def _get_login_alert_account_user(portal, username):
    username = _safe_login_username(username)
    if not username:
        return None

    User = get_user_model()
    queryset = User.objects.filter(username__iexact=username, is_active=True).exclude(email="")

    if portal == "ADMIN":
        return queryset.filter(is_superuser=True).first()
    if portal == "HR":
        return queryset.filter(role="HR").first()
    if portal == "EMPLOYEE":
        return queryset.filter(role="EMPLOYEE").first()
    return None


def _get_login_alert_recipients(portal, username):
    recipients = []

    for _, email_address in getattr(settings, "ADMINS", []):
        if email_address:
            recipients.append(email_address)

    account_user = _get_login_alert_account_user(portal, username)
    if account_user and account_user.email:
        recipients.append(account_user.email)

    unique_recipients = []
    seen = set()
    for email_address in recipients:
        normalized = str(email_address or "").strip()
        key = normalized.lower()
        if normalized and key not in seen:
            unique_recipients.append(normalized)
            seen.add(key)

    return unique_recipients


def _send_login_security_alert(portal, username, ip_address, reason, attempts, lockout_seconds=0):
    alert_key = _login_cache_key("alert", portal, f"{reason}:{username}:{ip_address}")
    if not cache.add(alert_key, "sent", 60 * 30):
        return

    recipients = _get_login_alert_recipients(portal, username)
    if not recipients:
        security_logger.warning(
            "LOGIN_ALERT_EMAIL_SKIPPED | portal=%s | username=%s | ip=%s | reason=%s | details=no_recipients",
            portal,
            username or "(blank)",
            ip_address,
            reason,
        )
        return

    account_user = _get_login_alert_account_user(portal, username)
    subject = f"Login security alert: {portal}"
    lockout_seconds = int(lockout_seconds or 0)
    retry_after = ""
    lock_duration = ""
    if reason == "lockout" and lockout_seconds > 0:
        lock_duration = _format_retry_after(lockout_seconds).replace("after ", "")
        retry_after = localtime(now() + timedelta(seconds=lockout_seconds)).strftime("%d/%m/%Y, %I:%M %p")

    lockout_details = ""
    if retry_after:
        lockout_details = (
            "\nYour login has been temporarily locked.\n\n"
            f"Lock duration: {lock_duration}\n"
            f"You can retry after: {retry_after}\n"
        )

    message = (
        "Login security alert\n\n"
        f"Portal: {portal}\n"
        f"Username: {username or '(blank)'}\n"
        f"IP address: {ip_address}\n"
        f"Reason: {'Too many wrong password attempts' if reason == 'lockout' else reason}\n"
        f"Attempts: {attempts}\n"
        f"{lockout_details}\n"
        f"Time: {localtime(now()).strftime('%d/%m/%Y, %I:%M %p')}\n\n"
        "If this was not you, please contact HR/Admin immediately."
    )
    try:
        EmailMessage(
            subject=subject,
            body=message,
            from_email=getattr(settings, "SERVER_EMAIL", settings.DEFAULT_FROM_EMAIL),
            to=recipients,
        ).send(fail_silently=False)
        from App.services.email_delivery_log import record_email_delivery
        record_email_delivery(
            subject=subject,
            recipients=recipients,
            status="sent",
            email_type="login_security_alert",
            from_email=getattr(settings, "SERVER_EMAIL", settings.DEFAULT_FROM_EMAIL),
            related_user=account_user,
            metadata={"portal": portal, "username": username or "(blank)", "ip_address": ip_address, "reason": reason, "attempts": attempts},
        )
        security_logger.info(
            "LOGIN_ALERT_EMAIL_SENT | portal=%s | username=%s | ip=%s | reason=%s | recipients=%s",
            portal,
            username or "(blank)",
            ip_address,
            reason,
            ",".join(recipients),
        )
    except Exception as exc:
        from App.services.email_delivery_log import record_email_delivery
        record_email_delivery(
            subject=subject,
            recipients=recipients,
            status="failed",
            email_type="login_security_alert",
            from_email=getattr(settings, "SERVER_EMAIL", settings.DEFAULT_FROM_EMAIL),
            error_message=str(exc),
            related_user=account_user,
            metadata={"portal": portal, "username": username or "(blank)", "ip_address": ip_address, "reason": reason, "attempts": attempts},
        )
        security_logger.exception(
            "LOGIN_ALERT_EMAIL_FAILED | portal=%s | username=%s | ip=%s | reason=%s",
            portal,
            username or "(blank)",
            ip_address,
            reason,
        )


def _register_login_failure(request, portal, username):
    config = _get_login_rate_config(portal)
    ip_address = _get_client_ip(request)
    username = _safe_login_username(username)

    user_attempts = _increment_login_counter(
        _login_cache_key("fail_user", portal, username),
        config["window"],
    )
    remember_failed_login_ip(portal, username, ip_address)
    ip_attempts = _increment_login_counter(
        _login_cache_key("fail_ip", portal, ip_address),
        config["window"],
    )
    attempts = max(user_attempts, ip_attempts)

    security_logger.warning(
        "LOGIN_FAILED | portal=%s | username=%s | ip=%s | user_attempts=%s | ip_attempts=%s",
        portal,
        username or "(blank)",
        ip_address,
        user_attempts,
        ip_attempts,
    )

    locked = attempts >= config["max_attempts"]
    if locked:
        lock_until = timezone.now().timestamp() + config["lockout"]
        cache.set(_login_cache_key("lock_user", portal, username), lock_until, config["lockout"])
        cache.set(_login_cache_key("lock_ip", portal, ip_address), lock_until, config["lockout"])
        security_logger.warning(
            "LOGIN_LOCKOUT | portal=%s | username=%s | ip=%s | attempts=%s | lockout_seconds=%s",
            portal,
            username or "(blank)",
            ip_address,
            attempts,
            config["lockout"],
        )
        _send_login_security_alert(portal, username, ip_address, "lockout", attempts, config["lockout"])
    elif ip_attempts >= LOGIN_BULK_IP_ALERT_ATTEMPTS:
        _send_login_security_alert(portal, username, ip_address, "bulk_failed_attempts", ip_attempts)

    attempts_remaining = max(config["max_attempts"] - attempts, 0)

    if not locked:
        _maybe_delay_failed_login(attempts)
    return {
        "lockout_seconds": config["lockout"] if locked else 0,
        "attempts_remaining": attempts_remaining,
    }


def _login_blocked_response(request, portal, username, redirect_name):
    ip_address = _get_client_ip(request)
    remaining = _get_login_lock_status(portal, username, ip_address)
    if remaining <= 0:
        return None

    security_logger.warning(
        "LOGIN_BLOCKED | portal=%s | username=%s | ip=%s | remaining_seconds=%s",
        portal,
        _safe_login_username(username) or "(blank)",
        ip_address,
        remaining,
    )
    _set_login_error_message(request, locked=True, remaining_seconds=remaining)
    request.session[f"{portal.lower()}_login_username"] = username or ""
    return redirect(redirect_name)


def _record_successful_login(request, portal, user, username):
    ip_address = _get_client_ip(request)
    _clear_login_rate_state(portal, username, ip_address)
    security_logger.info(
        "LOGIN_SUCCESS | portal=%s | user_id=%s | username=%s | ip=%s",
        portal,
        user.id,
        user.username,
        ip_address,
    )


def _render_loading_screen(request, *, page_title, theme_class, company_product, subtitle, kicker,
                           headline, description, center_label, duration, target_url, info_items):
    return render(request, "loading_screen.html", {
        "page_title": page_title,
        "theme_class": theme_class,
        "company_product": company_product,
        "subtitle": subtitle,
        "kicker": kicker,
        "headline": headline,
        "description": description,
        "center_label": center_label,
        "duration": duration,
        "target_url": target_url,
        "info_items": info_items,
    })


def _render_portal_login_loading_screen(request, *, template_name, page_title, duration, target_url):
    return render(request, template_name, {
        "page_title": page_title,
        "duration": duration,
        "target_url": target_url,
    })


@never_cache
def app_loading(request):
    if request.user.is_authenticated:
        if getattr(request.user, "is_superuser", False):
            return redirect("admin:index")
        if getattr(request.user, "role", None) == "HR":
            return redirect("hr_dashboard")
        if getattr(request.user, "role", None) == "EMPLOYEE":
            return redirect("dashboard")

    return _render_loading_screen(
        request,
        page_title="MS Technology | Launching Portal",
        theme_class="theme-app",
        company_product="Leave Management",
        subtitle="Smart Leave. Smooth Workflow.",
        kicker="Initializing Workspace",
        headline="Starting Leave Management...",
        description="Loading your workspace and preparing everything you need for a smooth start.",
        center_label="MST",
        duration=10,
        target_url=reverse("role_select"),
        info_items=[
            {"title": "Secure & Reliable", "text": "Your data is safe and protected."},
            {"title": "Easy Approvals", "text": "Faster approvals and notifications."},
            {"title": "Responsive Access", "text": "Built to work cleanly across desktop and mobile devices."},
        ],
    )


@never_cache
def employee_login_loading(request):
    if request.user.is_authenticated and request.user.role == "EMPLOYEE":
        return redirect("dashboard")

    return _render_portal_login_loading_screen(
        request,
        template_name="employee_login_loading.html",
        page_title="Employee Portal | MS Technology",
        duration=5,
        target_url=reverse("employee_login_form"),
    )


@never_cache
def hr_login_loading(request):
    if request.user.is_authenticated and request.user.role == "HR":
        return redirect("hr_dashboard")

    return _render_portal_login_loading_screen(
        request,
        template_name="hr_login_loading.html",
        page_title="HR Portal | MS Technology",
        duration=5,
        target_url=reverse("hr_login_form"),
    )


@never_cache
def admin_login_loading(request):
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("admin:index")

    return _render_portal_login_loading_screen(
        request,
        template_name="admin_login_loading.html",
        page_title="Admin Portal | MS Technology",
        duration=5,
        target_url=reverse("admin_login_form"),
    )


@never_cache
def employee_workspace_loading(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")

    if request.user.role != "EMPLOYEE":
        return redirect("role_select")

    return _render_loading_screen(
        request,
        page_title="MST Employee Workspace",
        theme_class="theme-employee",
        company_product="MST Employee Workspace",
        subtitle="Your leave dashboard is being prepared with account-specific data and controls.",
        kicker="Entering Workspace",
        headline="Signing you into the employee dashboard",
        description="We are loading leave balances, request actions, and your latest status widgets so the dashboard is ready as soon as it opens.",
        center_label="MST",
        duration=5,
        target_url=reverse("dashboard"),
        info_items=[
            {"title": "Dashboard", "text": "Recent leave activity, balances, and request actions are being prepared."},
            {"title": "Personalized", "text": "This screen appears only after a successful employee sign-in."},
            {"title": "Ready Next", "text": "You will land directly inside the employee dashboard."},
        ],
    )


def _render_role_transition_page(request, template_name, page_title, target_url, duration, extra_context=None):
    context = {
        "page_title": page_title,
        "target_url": target_url,
        "duration": duration,
    }
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)


def _get_logout_display_name(user, role=None):
    first_name = (getattr(user, "first_name", "") or "").strip()
    if first_name:
        return first_name

    full_name = (user.get_full_name() or "").strip()
    if full_name:
        return full_name.split()[0]

    username = (getattr(user, "username", "") or "").strip()
    if username:
        return username

    fallback_map = {"EMPLOYEE": "Employee", "HR": "HR", "Admin": "Admin"}
    return fallback_map.get(role, "User")


@never_cache
def employee_dashboard_loading_page(request):
    if not request.user.is_authenticated:
        return redirect("employee_login")

    if request.user.role != "EMPLOYEE":
        return redirect("role_select")

    return _render_role_transition_page(
        request,
        template_name="employee_dashboard_loading.html",
        page_title="Employee Dashboard Loading | MS Technology",
        duration=5,
        target_url=reverse("dashboard"),
        extra_context={"welcome_name": _get_logout_display_name(request.user, request.user.role)},
    )


@never_cache
def hr_dashboard_loading_page(request):
    if not request.user.is_authenticated:
        return redirect("hr_login")

    if request.user.role != "HR":
        return redirect("role_select")

    return _render_role_transition_page(
        request,
        template_name="hr_dashboard_loading.html",
        page_title="HR Dashboard Loading | MS Technology",
        duration=5,
        target_url=reverse("hr_dashboard"),
        extra_context={"welcome_name": _get_logout_display_name(request.user, request.user.role)},
    )


@never_cache
def admin_dashboard_loading_page(request):
    if not request.user.is_authenticated:
        return redirect("admin_login")

    if not request.user.is_superuser:
        return redirect("role_select")

    return _render_role_transition_page(
        request,
        template_name="admin_dashboard_loading.html",
        page_title="Admin Dashboard Loading | MS Technology",
        duration=5,
        target_url=reverse("admin:index"),
        extra_context={"welcome_name": _get_logout_display_name(request.user, "Admin")},
    )


@never_cache
def employee_logout_loading_page(request):
    return _render_role_transition_page(
        request,
        template_name="employee_logout_loading.html",
        page_title="Employee Logout | MS Technology",
        duration=5,
        target_url=reverse("employee_login_form"),
        extra_context={
            "logged_out_at": localtime(now()).strftime("%d %b %Y, %I:%M %p"),
            "logout_name": request.session.pop("employee_logout_name", "Employee"),
        },
    )


@never_cache
def hr_logout_loading_page(request):
    return _render_role_transition_page(
        request,
        template_name="hr_logout_loading.html",
        page_title="HR Logout | MS Technology",
        duration=5,
        target_url=reverse("hr_login_form"),
        extra_context={
            "logged_out_at": localtime(now()).strftime("%d %b %Y, %I:%M %p"),
            "logout_name": request.session.pop("hr_logout_name", "HR"),
        },
    )


@never_cache
def admin_logout_loading_page(request):
    return _render_role_transition_page(
        request,
        template_name="admin_logout_loading.html",
        page_title="Admin Logout | MS Technology",
        duration=5,
        target_url=reverse("admin_login_form"),
        extra_context={
            "logged_out_at": localtime(now()).strftime("%d %b %Y, %I:%M %p"),
            "logout_name": request.session.pop("admin_logout_name", "Admin"),
        },
    )


@never_cache
def hr_workspace_loading(request):
    if not request.user.is_authenticated:
        return redirect("hr_login")

    if request.user.role != "HR":
        return redirect("role_select")

    return _render_loading_screen(
        request,
        page_title="MST HR Workspace",
        theme_class="theme-hr",
        company_product="MST HR Workspace",
        subtitle="Approval tools and leave oversight panels are being initialized for your session.",
        kicker="Entering Workspace",
        headline="Signing you into the HR dashboard",
        description="We are loading employee leave queues, review tools, and approval-ready information so your HR workspace opens prepared.",
        center_label="MST",
        duration=5,
        target_url=reverse("hr_dashboard"),
        info_items=[
            {"title": "Approvals", "text": "Pending requests and employee records are being readied now."},
            {"title": "HR View", "text": "This post-login screen appears only for successful HR sign-in."},
            {"title": "Ready Next", "text": "You will be redirected straight into the HR dashboard."},
        ],
    )


@never_cache
def admin_workspace_loading(request):
    if not request.user.is_authenticated:
        return redirect("admin_login")

    if not request.user.is_superuser:
        return redirect("role_select")

    return _render_loading_screen(
        request,
        page_title="MST Admin Workspace",
        theme_class="theme-admin",
        company_product="MST Admin Workspace",
        subtitle="Administrative tools and system control panels are being prepared for secure access.",
        kicker="Entering Workspace",
        headline="Signing you into the admin control area",
        description="We are loading protected admin controls, elevated settings access, and system management tools for your current session.",
        center_label="MST",
        duration=5,
        target_url=reverse("admin:index"),
        info_items=[
            {"title": "Admin Access", "text": "Privileged controls and management panels are being initialized."},
            {"title": "Secure Session", "text": "This post-login loader appears only after successful administrator authentication."},
            {"title": "Ready Next", "text": "You will move directly into the admin control panel."},
        ],
    )


@never_cache
def logout_loading(request):
    portal = (request.session.pop("logout_portal", "") or "").strip().lower()

    config = {
        "employee": {
            "page_title": "Employee Logout | MS Technology",
            "theme_class": "theme-employee",
            "company_product": "MS Technology Employee Access",
            "subtitle": "Closing your employee session and clearing role-based workspace data.",
            "kicker": "Employee Logout",
            "headline": "Signing you out of the employee workspace",
            "description": "We are ending your employee session securely and preparing the sign-in page for your next access.",
            "center_label": "EMP",
            "duration": 3,
            "target_url": reverse("employee_login_form"),
            "info_items": [
                {"title": "Session Closed", "text": "Your employee session has been ended securely."},
                {"title": "Next Step", "text": "You will return to the employee login screen automatically."},
                {"title": "Safe Exit", "text": "Workspace access is cleared before the portal becomes available again."},
            ],
        },
        "hr": {
            "page_title": "HR Logout | MS Technology",
            "theme_class": "theme-hr",
            "company_product": "MS Technology HR Access",
            "subtitle": "Closing your HR session and protecting approval workspace access.",
            "kicker": "HR Logout",
            "headline": "Signing you out of the HR workspace",
            "description": "We are ending your HR session securely and preparing the approval portal sign-in page.",
            "center_label": "HR",
            "duration": 3,
            "target_url": reverse("hr_login_form"),
            "info_items": [
                {"title": "Session Closed", "text": "Your HR approval session has been ended securely."},
                {"title": "Next Step", "text": "You will return to the HR login screen automatically."},
                {"title": "Safe Exit", "text": "Review tools and protected access are cleared before re-entry."},
            ],
        },
        "admin": {
            "page_title": "Admin Logout | MS Technology",
            "theme_class": "theme-admin",
            "company_product": "MS Technology Admin Access",
            "subtitle": "Closing your admin session and securing elevated control access.",
            "kicker": "Admin Logout",
            "headline": "Signing you out of the admin control area",
            "description": "We are ending your administrative session securely and preparing the admin sign-in page.",
            "center_label": "ADM",
            "duration": 3,
            "target_url": reverse("admin_login_form"),
            "info_items": [
                {"title": "Session Closed", "text": "Your elevated admin session has been ended securely."},
                {"title": "Next Step", "text": "You will return to the admin login screen automatically."},
                {"title": "Safe Exit", "text": "Privileged controls are cleared before the portal is shown again."},
            ],
        },
    }

    selected_config = config.get(portal)

    if not selected_config:
        return redirect("role_select")

    return _render_loading_screen(request, **selected_config)


@never_cache
def hr_login(request):
    # 🔥 If already logged in, don't allow login page

    if request.user.is_authenticated and request.user.role == "HR":
        return redirect("hr_dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        blocked_response = _login_blocked_response(request, "HR", username, "hr_login_form")
        if blocked_response:
            return blocked_response

        user = authenticate(request, username=username, password=password)

        # 🔥 Security Hardening: Check if user exists, is HR, AND is active
        if user is not None and user.role == "HR" and user.is_active:
            _record_successful_login(request, "HR", user, username)
            login(request, user)
            if user.must_change_password:
                return redirect("force_password_change")
            return redirect("hr_dashboard_loading_page")
        else:
            failure_state = _register_login_failure(request, "HR", username)
            _set_login_error_message(
                request,
                locked=bool(failure_state["lockout_seconds"]),
                remaining_seconds=failure_state["lockout_seconds"],
                attempts_remaining=failure_state["attempts_remaining"],
            )
            request.session["hr_login_username"] = username or ""
            return redirect("hr_login_form")

    context = {
        "prefill_username": request.session.pop("hr_login_username", ""),
    }
    return render(request, "hr_login.html", context)



@login_required
@never_cache
def hr_notifications(request):
    if request.user.role != "HR":
        return JsonResponse({"detail": "HR access required."}, status=403)

    limit = get_capped_positive_int(
        request.GET.get("limit"),
        default=MAX_NOTIFICATION_FEED_LIMIT,
    )
    offset = get_capped_notification_offset(request.GET.get("offset"))
    if offset is None:
        return JsonResponse({"detail": "Offset too large."}, status=400)

    pending_leaves = (
        Leave.objects
        .filter(status="Pending")
        .annotate(notification_activity_at=Coalesce("updated_at", "created_at"))
        .select_related("user", "user__profile")
        .order_by("-notification_activity_at", "-id")
    )
    total_available = pending_leaves.count()
    page_leaves = list(pending_leaves[offset:offset + limit])
    payload = build_hr_pending_notifications(page_leaves, request.user)
    notifications = payload["notifications"]

    return JsonResponse({
        "count": get_hr_unread_notification_count(request.user),
        "recent_type_class": payload["recent_type_class"],
        "notifications": notifications,
        "next_offset": offset + len(notifications),
        "has_more": bool(limit and offset + len(notifications) < total_available),
    })


def get_leave_type_class(leave_type):
    return {
        "Sick": "sick",
        "Unpaid": "unpaid",
        "Earned": "earned",
        "Short": "short",
        "Half": "half",
    }.get(leave_type, "default")


def parse_json_request_body(request):
    raw_body = request.body or b""
    if not raw_body.strip():
        return {}

    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        user = getattr(request, "user", None)
        security_logger.warning(
            "INVALID_JSON_REQUEST | path=%s | method=%s | user_id=%s | role=%s | ip=%s | content_type=%s | body_bytes=%s | error=%s",
            request.path,
            request.method,
            getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
            getattr(user, "role", "") if getattr(user, "is_authenticated", False) else "",
            _get_client_ip(request),
            request.META.get("CONTENT_TYPE", ""),
            len(raw_body),
            str(exc),
        )
        return None

    if not isinstance(payload, dict):
        user = getattr(request, "user", None)
        security_logger.warning(
            "INVALID_JSON_REQUEST | path=%s | method=%s | user_id=%s | role=%s | ip=%s | content_type=%s | body_bytes=%s | error=payload_not_object",
            request.path,
            request.method,
            getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
            getattr(user, "role", "") if getattr(user, "is_authenticated", False) else "",
            _get_client_ip(request),
            request.META.get("CONTENT_TYPE", ""),
            len(raw_body),
        )
        return None

    return payload


def normalize_action_id_for_model(value, model):
    raw_value = str(value or "").strip()
    if not raw_value:
        return None

    pk_field = model._meta.pk

    if isinstance(pk_field, (models.AutoField, models.BigAutoField, models.SmallAutoField, models.IntegerField, models.BigIntegerField, models.SmallIntegerField, models.PositiveIntegerField, models.PositiveSmallIntegerField)):
        if not raw_value.isdigit():
            raise ValueError("IDs must be numeric.")
        return raw_value

    if isinstance(pk_field, models.UUIDField):
        try:
            return str(uuid.UUID(raw_value))
        except ValueError:
            raise ValueError("IDs must be valid UUID values.")

    if isinstance(pk_field, (models.CharField, models.SlugField)):
        max_length = pk_field.max_length or 64
        if len(raw_value) > max_length:
            raise ValueError(f"IDs must be {max_length} characters or fewer.")
        if not re.fullmatch(r"[\w.@:+-]+", raw_value):
            raise ValueError("IDs contain unsupported characters.")
        return raw_value

    raise ValueError("Unsupported ID field type.")


def get_limited_action_ids(request, payload, model):
    raw_ids = payload.get("ids") or []
    if raw_ids and not isinstance(raw_ids, (list, tuple)):
        user = getattr(request, "user", None)
        security_logger.warning(
            "INVALID_ACTION_IDS_TYPE | path=%s | method=%s | user_id=%s | role=%s | ip=%s | model=%s | ids_type=%s",
            request.path,
            request.method,
            getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
            getattr(user, "role", "") if getattr(user, "is_authenticated", False) else "",
            _get_client_ip(request),
            model.__name__,
            type(raw_ids).__name__,
        )
        return None, JsonResponse({"error": "IDs must be provided as a list."}, status=400)

    ids = []

    try:
        for value in raw_ids:
            normalized_id = normalize_action_id_for_model(value, model)
            if normalized_id:
                ids.append(normalized_id)
    except ValueError as exc:
        user = getattr(request, "user", None)
        security_logger.warning(
            "INVALID_ACTION_ID | path=%s | method=%s | user_id=%s | role=%s | ip=%s | model=%s | error=%s",
            request.path,
            request.method,
            getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
            getattr(user, "role", "") if getattr(user, "is_authenticated", False) else "",
            _get_client_ip(request),
            model.__name__,
            str(exc),
        )
        return None, JsonResponse({"error": str(exc)}, status=400)

    if len(ids) > MAX_READ_SEEN_ACTION_IDS:
        user = getattr(request, "user", None)
        security_logger.warning(
            "READ_SEEN_ID_LIMIT_EXCEEDED | path=%s | method=%s | user_id=%s | role=%s | ip=%s | ids_count=%s | max_ids=%s",
            request.path,
            request.method,
            getattr(user, "id", None) if getattr(user, "is_authenticated", False) else None,
            getattr(user, "role", "") if getattr(user, "is_authenticated", False) else "",
            _get_client_ip(request),
            len(ids),
            MAX_READ_SEEN_ACTION_IDS,
        )
        return None, JsonResponse(
            {"error": f"Too many IDs in one request. Maximum allowed is {MAX_READ_SEEN_ACTION_IDS}."},
            status=400,
        )

    return ids, None


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
            "photo_url": _profile_photo_url(leave_profile),
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


def get_hr_notification_context(user, limit=MAX_NOTIFICATION_FEED_LIMIT):
    limit = get_capped_positive_int(str(limit), default=MAX_NOTIFICATION_FEED_LIMIT)
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
    notification_retention_cutoff = now() - timedelta(days=30)
    leaves = sorted(
        [
            leave for leave in leaves
            if leave.status in ["Approved", "Rejected"]
            and get_leave_activity_datetime(leave) >= notification_retention_cutoff
        ],
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

        date_range = leave.from_date.strftime("%b %d")
        if leave.to_date and leave.to_date != leave.from_date:
            date_range += f" - {leave.to_date.strftime('%b %d')}"

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
        reviewed_by = getattr(leave, "reviewed_by", None)
        reviewer_name = reviewed_by.get_full_name().strip() or reviewed_by.username if reviewed_by else "HR Team"
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
            "reviewer_name": reviewer_name,
            "status": leave.status,
            "status_class": leave.status.lower(),
            "photo_url": _profile_photo_url(leave_profile),
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


def get_employee_notification_context(user, limit=MAX_NOTIFICATION_FEED_LIMIT):
    limit = get_capped_positive_int(str(limit), default=MAX_NOTIFICATION_FEED_LIMIT)
    leaves = (
        Leave.objects
        .filter(user=user, status__in=["Approved", "Rejected"])
        .select_related("user", "user__profile", "reviewed_by")
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


def get_hr_unread_notification_count(user):
    pending_leave_count = Leave.objects.filter(status="Pending").count()

    try:
        read_count = (
            LeaveNotificationRead.objects
            .filter(user=user, leave__status="Pending")
            .values("leave_id")
            .distinct()
            .count()
        )
    except (OperationalError, ProgrammingError):
        read_count = 0

    return max(pending_leave_count - read_count, 0)


def get_employee_unread_notification_count(user):
    notification_retention_cutoff = now() - timedelta(days=30)
    eligible_leaves = Leave.objects.filter(
        user=user,
        status__in=["Approved", "Rejected"],
        approved_at__gte=notification_retention_cutoff,
    ) | Leave.objects.filter(
        user=user,
        status__in=["Approved", "Rejected"],
        rejected_at__gte=notification_retention_cutoff,
    ) | Leave.objects.filter(
        user=user,
        status__in=["Approved", "Rejected"],
        approved_at__isnull=True,
        rejected_at__isnull=True,
        created_at__gte=notification_retention_cutoff,
    )
    eligible_leaves = eligible_leaves.distinct()
    eligible_count = eligible_leaves.count()

    try:
        read_count = (
            LeaveNotificationRead.objects
            .filter(user=user, leave_id__in=eligible_leaves.values("id"))
            .values("leave_id")
            .distinct()
            .count()
        )
    except (OperationalError, ProgrammingError):
        read_count = 0

    return max(eligible_count - read_count, 0)


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
            "photo_url": _profile_photo_url(sender_profile),
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
    if user.role == "HR":
        allowed_roles = ["EMPLOYEE", "Admin"]
    elif user.role == "EMPLOYEE":
        allowed_roles = ["HR", "Admin"]
    else:
        return []

    users = (
        get_user_model().objects
        .filter(role__in=allowed_roles, is_active=True)
        .exclude(id=user.id)
        .select_related("profile")
        .order_by("role", "first_name", "username")
    )
    recipients = []

    for recipient in users:
        try:
            profile = recipient.profile
        except Profile.DoesNotExist:
            profile = None

        employee_id = getattr(profile, "employee_id", "") if profile else ""
        role_label = "Admin" if recipient.role == "Admin" else ("HR" if recipient.role == "HR" else "Employee")
        name = recipient.get_full_name().strip() or recipient.username
        label_parts = [name, role_label]
        if employee_id:
            label_parts.append(employee_id)
        recipients.append({
            "id": recipient.id,
            "label": " | ".join(label_parts),
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
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    ids, limit_response = get_limited_action_ids(request, payload, Communication)
    if limit_response:
        return limit_response

    mark_all = bool(payload.get("all"))
    if not ids and not mark_all:
        return JsonResponse({"error": "No communication IDs supplied."}, status=400)

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

    try:
        if user.role == "HR":
            if message_type == "ANNOUNCEMENT":
                communication = Communication.objects.create(
                    sender=user,
                    message_type="ANNOUNCEMENT",
                    audience_role="EMPLOYEE",
                    title=title,
                    body=body,
                )
                queue_communication_push(
                    user,
                    audience_role="EMPLOYEE",
                    message_type=communication.message_type,
                    title=title or "Announcement",
                    body=body,
                )
            elif message_type == "DIRECT":
                try:
                    recipient_id = normalize_action_id_for_model(request.POST.get("recipient_id"), User)
                except ValueError:
                    return JsonResponse({"error": "Invalid recipient."}, status=400)

                if not recipient_id:
                    return JsonResponse({"error": "Recipient is required."}, status=400)

                recipient = get_object_or_404(User, id=recipient_id, role__in=["EMPLOYEE", "Admin"], is_active=True)
                communication = Communication.objects.create(
                    sender=user,
                    recipient=recipient,
                    message_type="DIRECT",
                    title=title,
                    body=body,
                )
                queue_communication_push(
                    user,
                    recipient=recipient,
                    message_type=communication.message_type,
                    title=title or "New message",
                    body=body,
                )
            else:
                return JsonResponse({"error": "Invalid communication type."}, status=400)

        elif user.role == "EMPLOYEE":
            if message_type != "DIRECT":
                return JsonResponse({"error": "Employees can only send direct messages."}, status=403)

            try:
                recipient_id = normalize_action_id_for_model(request.POST.get("recipient_id"), User)
            except ValueError:
                return JsonResponse({"error": "Invalid recipient."}, status=400)

            if not recipient_id:
                return JsonResponse({"error": "Recipient is required."}, status=400)

            recipient = get_object_or_404(User, id=recipient_id, role__in=["HR", "Admin"], is_active=True)
            communication = Communication.objects.create(
                sender=user,
                recipient=recipient,
                message_type="DIRECT",
                title=title,
                body=body,
            )
            queue_communication_push(
                user,
                recipient=recipient,
                message_type=communication.message_type,
                title=title or "New message",
                body=body,
            )
        else:
            return JsonResponse({"error": "Unsupported role."}, status=403)
    except ValidationError:
        return JsonResponse({"error": "HTML markup is not allowed in messages."}, status=400)

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
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    ids, limit_response = get_limited_action_ids(request, payload, Communication)
    if limit_response:
        return limit_response

    mark_all = bool(payload.get("all"))
    if not ids and not mark_all:
        return JsonResponse({"error": "No communication IDs supplied."}, status=400)

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


@login_required
@never_cache
def employee_notifications(request):
    if request.user.role != "EMPLOYEE":
        return JsonResponse({"detail": "Employee access required."}, status=403)

    notification_retention_cutoff = now() - timedelta(days=30)
    leaves = (
        Leave.objects
        .filter(
            Q(approved_at__gte=notification_retention_cutoff) |
            Q(rejected_at__gte=notification_retention_cutoff) |
            Q(approved_at__isnull=True, rejected_at__isnull=True, created_at__gte=notification_retention_cutoff),
            user=request.user,
            status__in=["Approved", "Rejected"],
        )
        .annotate(notification_activity_at=Coalesce("approved_at", "rejected_at", "created_at"))
        .select_related("user", "user__profile", "reviewed_by")
        .order_by("-notification_activity_at", "-id")
    )
    limit = get_capped_positive_int(
        request.GET.get("limit"),
        default=MAX_NOTIFICATION_FEED_LIMIT,
    )
    offset = get_capped_notification_offset(request.GET.get("offset"))
    if offset is None:
        return JsonResponse({"detail": "Offset too large."}, status=400)

    total_available = leaves.count()
    page_leaves = list(leaves[offset:offset + limit])
    payload = build_employee_notifications(page_leaves, request.user)
    notifications = payload["notifications"]

    return JsonResponse({
        "count": get_employee_unread_notification_count(request.user),
        "leave_counts": {
            "pending": Leave.objects.filter(user=request.user, status="Pending").count(),
            "approved": Leave.objects.filter(user=request.user, status="Approved").count(),
            "rejected": Leave.objects.filter(user=request.user, status="Rejected").count(),
        },
        "recent_type_class": payload["recent_type_class"],
        "notifications": notifications,
        "next_offset": offset + len(notifications),
        "has_more": bool(limit and offset + len(notifications) < total_available),
    })


@login_required
@never_cache
@require_POST
def notifications_mark_read(request):
    payload = parse_json_request_body(request)
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    ids, limit_response = get_limited_action_ids(request, payload, Leave)
    if limit_response:
        return limit_response

    mark_all = bool(payload.get("all"))
    if not ids and not mark_all:
        return JsonResponse({"error": "No notification IDs supplied."}, status=400)

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
    if payload is None:
        return JsonResponse({"error": "Invalid JSON payload."}, status=400)

    ids, limit_response = get_limited_action_ids(request, payload, Leave)
    if limit_response:
        return limit_response

    mark_all = bool(payload.get("all"))
    if not ids and not mark_all:
        return JsonResponse({"error": "No notification IDs supplied."}, status=400)

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


@login_required
def push_notification_config(request):
    public_key = getattr(settings, "WEB_PUSH_VAPID_PUBLIC_KEY", "")
    return JsonResponse({
        "enabled": bool(public_key),
        "publicKey": public_key,
        "subscribeUrl": reverse("push_subscribe"),
        "unsubscribeUrl": reverse("push_unsubscribe"),
        "testUrl": reverse("push_test"),
    })


@login_required
@require_POST
def push_subscribe(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({"success": False, "error": "Invalid JSON payload."}, status=400)

    endpoint = (payload.get("endpoint") or "").strip()
    keys = payload.get("keys") or {}
    p256dh = (keys.get("p256dh") or "").strip()
    auth = (keys.get("auth") or "").strip()
    browser = (payload.get("browser") or request.META.get("HTTP_USER_AGENT", ""))[:120]
    device_label = (payload.get("deviceLabel") or "")[:120]

    if not endpoint or not p256dh or not auth:
        return JsonResponse({"success": False, "error": "Incomplete push subscription."}, status=400)

    existing_subscription = PushSubscription.objects.filter(endpoint=endpoint).first()
    needs_resubscribe = bool(
        existing_subscription and (
            not existing_subscription.is_active
            or bool(existing_subscription.last_error)
        )
    )

    subscription, created = PushSubscription.objects.update_or_create(
        endpoint=endpoint,
        defaults={
            "user": request.user,
            "p256dh": p256dh,
            "auth": auth,
            "browser": browser,
            "device_label": device_label,
            "is_active": True,
            "last_error": "",
        },
    )

    return JsonResponse({
        "success": True,
        "created": created,
        "subscriptionId": subscription.pk,
        "needsResubscribe": needs_resubscribe,
    })


@login_required
@require_POST
def push_unsubscribe(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except (TypeError, ValueError, json.JSONDecodeError):
        payload = {}

    endpoint = (payload.get("endpoint") or "").strip()
    queryset = PushSubscription.objects.filter(user=request.user)
    if endpoint:
        queryset = queryset.filter(endpoint=endpoint)
    updated = queryset.update(is_active=False)
    return JsonResponse({"success": True, "updated": updated})


@login_required
@require_POST
def push_test(request):
    result = send_push_to_user(
        request.user,
        "Notifications enabled",
        "System notifications are ready on this device.",
        url=request.META.get("HTTP_REFERER") or "/",
        tag=f"push-test-{request.user.pk}",
        kind="test",
    )
    return JsonResponse({"success": bool(result.get("sent")), **result})


from django.db.models import Count

@login_required
@never_cache
def hr_dashboard(request):

    if request.user.role != "HR":
        return redirect("role_select")

    # Filter metrics to only include ACTIVE users
    total = Leave.objects.filter(user__is_active=True).count()
    pending = Leave.objects.filter(status="Pending", user__is_active=True).count()
    approved = Leave.objects.filter(status="Approved", user__is_active=True).count()
    rejected = Leave.objects.filter(status="Rejected", user__is_active=True).count()

    pending_leaves_qs = Leave.objects.filter(status="Pending", user__is_active=True).order_by("-created_at")
    pending_page_number = request.GET.get("queue_page", 1)
    pending_paginator = Paginator(pending_leaves_qs, 7)
    pending_leaves = pending_paginator.get_page(pending_page_number)

    for leave in pending_leaves:
        day_display = _get_leave_day_display(leave)
        leave.days_value = day_display["days_value"]
        leave.days_value_display = day_display["days_value_display"]
        leave.days_target = day_display["days_target"]
        leave.days_suffix = day_display["days_suffix"]
        leave.days_label = day_display["days_label"]

    context = {
        "total": total,
        "pending": pending,
        "approved": approved,
        "rejected": rejected,
        "pending_leaves": pending_leaves,
        "pending_leaves_paginator": pending_paginator,
    }
    context.update(get_hr_notification_context(request.user))
    context.update(get_communication_context(request.user))

    return render(request, "hr_dashboard.html", context)


def build_manage_employee_card(employee, employee_leaves, today=None):
    employee_leaves = sorted(employee_leaves, key=get_leave_activity_datetime, reverse=True)

    display_name = employee.get_full_name().strip() or employee.username

    try:
        profile = employee.profile
    except Profile.DoesNotExist:
        profile = None

    try:
        balance = employee.leavebalance
    except LeaveBalance.DoesNotExist:
        balance = None

    today = today or localdate()
    pending_count = sum(1 for leave in employee_leaves if leave.status == "Pending")
    approved_count = sum(1 for leave in employee_leaves if leave.status == "Approved")
    rejected_count = sum(1 for leave in employee_leaves if leave.status == "Rejected")
    latest_leave = employee_leaves[0] if employee_leaves else None
    latest_pending_leave = next((leave for leave in employee_leaves if leave.status == "Pending"), None)
    latest_decision_leave = next(
        (leave for leave in employee_leaves if leave.status in ["Approved", "Rejected"]),
        None
    )
    latest_status = latest_leave.status if latest_leave else "No requests"
    latest_status_class = latest_status.lower().replace(" ", "-")
    month_short_used = sum(
        1 for leave in employee_leaves
        if leave.leave_type == "Short"
        and leave.from_date.month == today.month
        and leave.from_date.year == today.year
        and leave.status in ["Pending", "Approved"]
    )
    month_half_used = sum(
        1 for leave in employee_leaves
        if leave.leave_type == "Half"
        and leave.from_date.month == today.month
        and leave.from_date.year == today.year
        and leave.status in ["Pending", "Approved"]
    )

    return {
        "id": employee.id,
        "username": employee.username,
        "display_name": display_name,
        "email": employee.email or "No email added",
        "employee_id": getattr(profile, "employee_id", "Not assigned"),
        "department": getattr(profile, "department", "Not assigned"),
        "role": getattr(profile, "role", employee.role),
        "date_of_joining": profile.date_of_joining.strftime("%b %d, %Y") if profile and profile.date_of_joining else "Not added",
        "phone": getattr(profile, "phone", "Not added"),
        "address": getattr(profile, "address", "") or "Address not added yet.",
        "bio": getattr(profile, "bio", "") or "No employee bio available yet.",
        "photo_url": _profile_photo_url(profile),
        "total_requests": len(employee_leaves),
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,
        "latest_status": latest_status,
        "latest_status_class": latest_status_class,
        "latest_leave_type": latest_leave.leave_type if latest_leave else "No leave history",
        "latest_decision_status": latest_decision_leave.status if latest_decision_leave else ("Pending review" if pending_count else "No decision yet"),
        "latest_decision_status_class": latest_decision_leave.status.lower() if latest_decision_leave else ("pending" if pending_count else "no-requests"),
        "latest_decision_type": latest_decision_leave.leave_type if latest_decision_leave else (latest_pending_leave.leave_type if latest_pending_leave else "No leave history"),
        "latest_applied_at": localtime(latest_leave.created_at).strftime("%b %d, %Y %I:%M %p") if latest_leave else "No applications yet",
        "recent_pending_type": latest_pending_leave.leave_type if latest_pending_leave else "",
        "recent_pending_type_class": get_leave_type_class(latest_pending_leave.leave_type) if latest_pending_leave else "",
        "earned_used": balance.earned_used if balance else 0,
        "earned_total": balance.earned_total if balance else 0,
        "earned_remaining": (balance.earned_total - balance.earned_used) if balance else 0,
        "sick_used": balance.sick_used if balance else 0,
        "sick_total": balance.sick_total if balance else 0,
        "sick_remaining": (balance.sick_total - balance.sick_used) if balance else 0,
        "total_leave_balance": balance.total_leave_balance if balance else 0,
        "total_leave_remaining": _remaining_from_balance(balance) if balance else 0,
        "unpaid_taken": balance.unpaid if balance else 0,
        "short_used_month": month_short_used,
        "short_total_month": 2,
        "half_used_month": month_half_used,
        "half_total_month": 1,
        "leaves": [
            {
                **_get_leave_day_display(leave),
                "id": leave.id,
                "type": leave.leave_type,
                "type_class": get_leave_type_class(leave.leave_type),
                "status": leave.status,
                "from_date": leave.from_date.strftime("%b %d, %Y"),
                "to_date": leave.to_date.strftime("%b %d, %Y"),
                "reason": leave.reason,
                "rejection_reason": leave.rejection_reason or "-",
                "reviewed_by": (
                    leave.reviewed_by.get_full_name().strip() or leave.reviewed_by.username
                    if getattr(leave, "reviewed_by", None)
                    else "HR Team"
                ),
                "applied_at": localtime(leave.created_at).strftime("%b %d, %Y %I:%M %p"),
                "applied_at_iso": localtime(leave.created_at).isoformat(),
                "updated_at": localtime(leave.updated_at).strftime("%b %d, %Y %I:%M %p") if getattr(leave, "updated_at", None) else "",
                "updated_at_iso": localtime(leave.updated_at).isoformat() if getattr(leave, "updated_at", None) else "",
                "no_of_times_updated": leave.no_of_times_updated or 0,
                "approved_at": localtime(leave.approved_at).strftime("%b %d, %Y %I:%M %p") if getattr(leave, "approved_at", None) else "",
                "approved_at_iso": localtime(leave.approved_at).isoformat() if getattr(leave, "approved_at", None) else "",
                "rejected_at": localtime(leave.rejected_at).strftime("%b %d, %Y %I:%M %p") if getattr(leave, "rejected_at", None) else "",
                "rejected_at_iso": localtime(leave.rejected_at).isoformat() if getattr(leave, "rejected_at", None) else "",
                "from_time": localtime(leave.from_datetime).strftime("%I:%M %p") if leave.from_datetime else "",
                "to_time": localtime(leave.to_datetime).strftime("%I:%M %p") if leave.to_datetime else "",
                "deducted_from": leave.deducted_from,
            }
            for leave in employee_leaves
        ],
    }


@login_required
@never_cache
def manage_all(request):

    # 🔐 Strict HR-only access
    if request.user.role != "HR":
        return redirect("role_select")

    leaves = Leave.objects.filter(user__is_active=True).select_related("user", "user__profile", "reviewed_by").order_by("-created_at")
    employees = User.objects.filter(role="EMPLOYEE", is_active=True).select_related("profile").order_by("username")

    employee_cards = []
    today = localdate()

    for employee in employees:
        employee_leaves = [leave for leave in leaves if leave.user_id == employee.id]
        employee_cards.append(build_manage_employee_card(employee, employee_leaves, today=today))

    employee_cards.sort(key=lambda employee: (employee["display_name"] or "").strip().lower())

    notification_payload = build_hr_pending_notifications(leaves, request.user)
    pending_notification_total = notification_payload["count"]
    recent_notification_type_class = notification_payload["recent_type_class"]
    pending_notifications = notification_payload["notifications"]

    context = {
        "leaves": leaves,
        "employee_cards": employee_cards,
        "selected_employee": employee_cards[0] if employee_cards else None,
        "pending_notifications": pending_notifications,
        "pending_notification_count": pending_notification_total,
        "pending_leave_total": sum(1 for leave in leaves if leave.status == "Pending"),
        "approved_leave_total": sum(1 for leave in leaves if leave.status == "Approved"),
        "rejected_leave_total": sum(1 for leave in leaves if leave.status == "Rejected"),
        "recent_notification_type_class": recent_notification_type_class,
    }
    context.update(get_communication_context(request.user))

    return render(request, "manage_all.html", context)


@login_required
@never_cache
def manage_all_employee_detail(request, user_id):

    if request.user.role != "HR":
        return JsonResponse({"detail": "HR access required."}, status=403)

    employee = get_object_or_404(
        User.objects.filter(role="EMPLOYEE", is_active=True).select_related("profile"),
        id=user_id,
    )
    employee_leaves = list(
        Leave.objects
        .filter(user_id=employee.id)
        .select_related("user", "user__profile", "reviewed_by")
        .order_by("-created_at")
    )

    return JsonResponse(build_manage_employee_card(employee, employee_leaves))


@login_required
@never_cache
def manage_all_summary(request):
    if request.user.role != "HR":
        return JsonResponse({"detail": "HR access required."}, status=403)

    active_leaves = Leave.objects.filter(user__is_active=True)
    return JsonResponse({
        "pending": active_leaves.filter(status="Pending").count(),
        "approved": active_leaves.filter(status="Approved").count(),
        "rejected": active_leaves.filter(status="Rejected").count(),
    })


from django.contrib.auth import get_user_model
User = get_user_model()


def _pdf_escape(value):
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_simple_employee_pdf(lines):
    content_lines = ["BT", "/F1 12 Tf", "50 790 Td", "16 TL"]

    for index, line in enumerate(lines):
        prefix = "" if index == 0 else "T* "
        content_lines.append(f"{prefix}({_pdf_escape(line)}) Tj")

    content_lines.append("ET")
    content = "\n".join(content_lines).encode("latin-1", "replace")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n".encode("latin-1") + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = []

    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("latin-1"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
    pdf.extend(b"0000000000 65535 f \n")

    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF".encode("latin-1")
    )
    return bytes(pdf)


def build_employee_pdf_payload(employee, profile, balance):
    lines = [
        "Employee Archive",
        "",
        f"Name: {employee.get_full_name().strip() or employee.username}",
        f"Username: {employee.username}",
        f"Email: {employee.email or '-'}",
        f"Role: {getattr(profile, 'role', employee.role)}",
        f"Employee ID: {getattr(profile, 'employee_id', '-')}",
        f"Department: {getattr(profile, 'department', '-')}",
        f"Date of Joining: {profile.date_of_joining.strftime('%d %b %Y') if profile and profile.date_of_joining else '-'}",
        f"Phone: {getattr(profile, 'phone', '-')}",
        "",
        f"Total Leave Balance: {balance.total_leave_balance if balance else 0}",
        f"Total Leave Remaining: {balance.total_leave_remaining if balance else 0}",
        f"Sick Balance: {balance.sick_used if balance else 0}/{balance.sick_total if balance else 0}",
        f"Earned Balance: {balance.earned_used if balance else 0}/{balance.earned_total if balance else 0}",
        f"Unpaid: {balance.unpaid if balance else 0}",
        "",
        f"Exported On: {localtime(now()).strftime('%d %b %Y %I:%M %p')}",
    ]
    return build_simple_employee_pdf(lines)

@login_required
@never_cache
def employee_details(request):

    if request.user.role != "HR":
        return redirect("role_select")

    next_employee_id_preview = Profile.generate_next_id("EMPLOYEE")

    form_values = {
        "username": "",
        "first_name": "",
        "last_name": "",
        "email": "",
        "department": "",
        "date_of_joining": "",
        "phone": "",
        "address": "",
        "sick_total": "12",
        "earned_total": "15",
        "total_leave_balance": "27",
        "total_leave_remaining": "27",
    }
    field_errors = {}

    def add_field_error(field_name, message_text):
        field_errors.setdefault(field_name, []).append(message_text)

    if request.method == "POST":
        form_values.update({
            "username": request.POST.get("username", "").strip(),
            "first_name": request.POST.get("first_name", "").strip(),
            "last_name": request.POST.get("last_name", "").strip(),
            "email": request.POST.get("email", "").strip(),
            "department": request.POST.get("department", "").strip(),
            "date_of_joining": request.POST.get("date_of_joining", "").strip(),
            "phone": request.POST.get("phone", "").strip(),
            "address": request.POST.get("address", "").strip(),
            "sick_total": request.POST.get("sick_total", "12").strip() or "12",
            "earned_total": request.POST.get("earned_total", "15").strip() or "15",
        })

        password = request.POST.get("password", "")
        confirm_password = request.POST.get("confirm_password", "")
        if not form_values["username"]:
            add_field_error("username", "Username is required.")
        if not form_values["first_name"]:
            add_field_error("first_name", "First name is required.")
        if not form_values["last_name"]:
            add_field_error("last_name", "Last name is required.")
        if not form_values["email"]:
            add_field_error("email", "Work email is required.")
        if not password:
            add_field_error("password", "Temporary password is required.")
        if not confirm_password:
            add_field_error("confirm_password", "Please confirm the password.")
        if not form_values["department"]:
            add_field_error("department", "Department is required.")
        if not form_values["date_of_joining"]:
            add_field_error("date_of_joining", "Joining date is required.")
        if not form_values["phone"]:
            add_field_error("phone", "Phone number is required.")

        try:
            form_values["username"] = validate_employee_username(form_values["username"])
        except ValueError as exc:
            add_field_error("username", str(exc))

        try:
            form_values["first_name"] = validate_plain_text_field(
                form_values["first_name"],
                "First name",
                EMPLOYEE_NAME_MAX_LENGTH,
            )
        except ValueError as exc:
            add_field_error("first_name", str(exc))

        try:
            form_values["last_name"] = validate_plain_text_field(
                form_values["last_name"],
                "Last name",
                EMPLOYEE_NAME_MAX_LENGTH,
            )
        except ValueError as exc:
            add_field_error("last_name", str(exc))

        try:
            form_values["email"] = validate_employee_email(form_values["email"])
        except ValueError as exc:
            add_field_error("email", str(exc))

        try:
            form_values["department"] = validate_plain_text_field(
                form_values["department"],
                "Department",
                EMPLOYEE_DEPARTMENT_MAX_LENGTH,
            )
        except ValueError as exc:
            add_field_error("department", str(exc))

        try:
            if form_values["phone"]:
                form_values["phone"] = normalize_employee_phone(form_values["phone"])
        except ValueError as exc:
            add_field_error("phone", str(exc))

        try:
            form_values["address"] = validate_employee_address(form_values["address"])
        except ValueError as exc:
            add_field_error("address", str(exc))

        if form_values["username"] and User.objects.filter(username__iexact=form_values["username"]).exists():
            add_field_error("username", "This username is already in use.")

        if form_values["email"] and User.objects.filter(email__iexact=form_values["email"]).exists():
            add_field_error("email", "This email is already linked to another user.")

        if form_values["phone"] and Profile.objects.filter(phone=form_values["phone"]).exists():
            add_field_error("phone", "This phone number is already linked to another employee.")

        if password and confirm_password and password != confirm_password:
            add_field_error("confirm_password", "Password confirmation does not match.")

        joining_date = None
        try:
            if form_values["date_of_joining"]:
                joining_date = date.fromisoformat(form_values["date_of_joining"])
                if joining_date < localdate():
                    add_field_error("date_of_joining", "Joining date cannot be in the past.")
        except ValueError:
            add_field_error("date_of_joining", "Please enter a valid joining date.")

        sick_total = None
        earned_total = None
        try:
            sick_total = validate_employee_leave_total(form_values["sick_total"], "Sick")
        except ValueError as exc:
            add_field_error("sick_total", str(exc))

        try:
            earned_total = validate_employee_leave_total(form_values["earned_total"], "Earned")
        except ValueError as exc:
            add_field_error("earned_total", str(exc))

        if sick_total is not None and earned_total is not None:
            calculated_total = _calculate_total_leave_balance(sick_total, earned_total)
            form_values["total_leave_balance"] = f"{calculated_total:g}"
            form_values["total_leave_remaining"] = f"{calculated_total:g}"

        if not field_errors:
            with transaction.atomic():
                new_user = User.objects.create_user(
                    username=form_values["username"],
                    email=form_values["email"],
                    password=password,
                    first_name=form_values["first_name"],
                    last_name=form_values["last_name"],
                )

                new_user.role = "EMPLOYEE"
                new_user.must_change_password = True
                new_user.save(update_fields=["role", "must_change_password"])

                profile = new_user.profile
                profile.department = form_values["department"]
                profile.date_of_joining = joining_date
                profile.phone = form_values["phone"]
                profile.address = form_values["address"]
                profile.role = "EMPLOYEE"
                profile.save()

                balance = new_user.leavebalance
                balance.sick_total = sick_total
                balance.sick_used = 0
                balance.earned_total = earned_total
                balance.earned_used = 0
                balance.unpaid = 0
                balance.total_leave_balance = _calculate_total_leave_balance(sick_total, earned_total)
                balance.total_leave_remaining = balance.total_leave_balance
                balance.save()

            welcome_result = send_employee_welcome_package(new_user, triggered_by=request.user)
            if welcome_result.get("email_sent"):
                messages.success(
                    request,
                    f"Employee '{new_user.get_full_name() or new_user.username}' created successfully. Welcome notification and email sent.",
                )
            elif welcome_result.get("sent"):
                messages.warning(
                    request,
                    f"Employee '{new_user.get_full_name() or new_user.username}' created successfully. Welcome notification sent, but welcome email could not be sent.",
                )
            else:
                messages.success(request, f"Employee '{new_user.get_full_name() or new_user.username}' created successfully.")
            return redirect("employee_details")

    employees = User.objects.filter(role="EMPLOYEE", is_active=True).select_related("profile", "leavebalance").order_by("-date_joined", "-id")

    employee_cards = []

    for employee in employees:
        try:
            profile = employee.profile
        except Profile.DoesNotExist:
            profile = None

        try:
            balance = employee.leavebalance
        except LeaveBalance.DoesNotExist:
            balance = None

        full_name = employee.get_full_name().strip()
        display_name = full_name or employee.username

        employee_cards.append({
            "id": employee.id,
            "display_name": display_name,
            # "display_name_short": shorten_display_name(display_name),
            # "avatar_initials": build_initials(full_name, employee.username),
            "username": employee.username,
            "first_name": employee.first_name or "-",
            "last_name": employee.last_name or "-",
            "email": employee.email or "Not added",
            "role": getattr(profile, "role", employee.role),
            "employee_id": getattr(profile, "employee_id", "Not assigned"),
            "department": getattr(profile, "department", "Not assigned"),
            "date_of_joining": profile.date_of_joining.strftime("%b %d, %Y") if profile and profile.date_of_joining else "Not added",
            "phone": getattr(profile, "phone", "Not added"),
            "address": getattr(profile, "address", "") or "Address not added yet.",
            "photo_url": _profile_photo_url(profile),
            "total_leave_balance": balance.total_leave_balance if balance else 0,
            "total_leave_remaining": _remaining_from_balance(balance) if balance else 0,
            "sick_total": balance.sick_total if balance else 0,
            "sick_used": balance.sick_used if balance else 0,
            "earned_total": balance.earned_total if balance else 0,
            "earned_used": balance.earned_used if balance else 0,
            "unpaid": balance.unpaid if balance else 0,
        })

    context = {
        "employee_cards": employee_cards,
        "employee_total": User.objects.filter(role="EMPLOYEE").count(),
        "joined_this_month_total": User.objects.filter(
            role="EMPLOYEE",
            date_joined__month=now().month,
            date_joined__year=now().year
        ).count(),
        "joined_this_year_total": User.objects.filter(
            role="EMPLOYEE",
            date_joined__year=now().year
        ).count(),
        "form_values": form_values,
        "field_errors": field_errors,
        "employee_id_preview": next_employee_id_preview,
    }
    context.update(get_hr_notification_context(request.user))
    context.update(get_communication_context(request.user))

    return render(request, "employee_details.html", context)


@login_required
@never_cache
@require_POST
def delete_employee(request, user_id):

    if request.user.role != "HR":
        return JsonResponse({"detail": "HR access required."}, status=403)

    employee = get_object_or_404(User, id=user_id, role="EMPLOYEE")

    try:
        profile = employee.profile
    except Profile.DoesNotExist:
        profile = None

    try:
        balance = employee.leavebalance
    except LeaveBalance.DoesNotExist:
        balance = None

    filename = f"employee-archive-{employee.username}.pdf"
    archive_token = secrets.token_urlsafe(32)
    cache.set(
        get_employee_archive_cache_key(archive_token),
        {
            "hr_user_id": request.user.id,
            "user_id": employee.id,
            "username": employee.username,
        },
        EMPLOYEE_ARCHIVE_DOWNLOAD_MAX_AGE_SECONDS,
    )

    # Soft Delete: Inactivate user instead of physical deletion
    log_profile_update(employee, request.user, "is_active", employee.is_active, False)
    security_logger.info(
        "EMPLOYEE_SOFT_DELETE | actor_id=%s | actor_username=%s | employee_id=%s | employee_username=%s",
        request.user.id,
        request.user.username,
        employee.id,
        employee.username,
    )
    employee.is_active = False
    employee.save()

    return JsonResponse({
        "status": "success",
        "message": f"Employee '{employee.username}' deleted successfully.",
        "employee_id": user_id,
        "filename": filename,
        "download_url": reverse("download_employee_archive", args=[user_id]),
        "download_token": archive_token,
    })


@login_required
@never_cache
@require_POST
def download_employee_archive(request, user_id):
    if request.user.role != "HR":
        return HttpResponseForbidden("HR access required.")

    token = (request.POST.get("token") or "").strip()
    if not token:
        return HttpResponseForbidden("Invalid or expired archive link.")

    cache_key = get_employee_archive_cache_key(token)
    token_payload = cache.get(cache_key)
    if not token_payload:
        return HttpResponseForbidden("Invalid or expired archive link.")

    if token_payload.get("hr_user_id") != request.user.id:
        return HttpResponseForbidden("Invalid archive link.")

    if token_payload.get("user_id") != user_id:
        return HttpResponseForbidden("Invalid archive link.")

    employee = get_object_or_404(User, id=user_id, role="EMPLOYEE")
    if token_payload.get("username") != employee.username:
        return HttpResponseForbidden("Invalid archive link.")

    cache.delete(cache_key)

    try:
        profile = employee.profile
    except Profile.DoesNotExist:
        profile = None

    try:
        balance = employee.leavebalance
    except LeaveBalance.DoesNotExist:
        balance = None

    filename = f"employee-archive-{employee.username}.pdf"
    response = HttpResponse(
        build_employee_pdf_payload(employee, profile, balance),
        content_type="application/pdf",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    return response


@login_required
@never_cache
@require_POST
def update_employee_contact_field(request, user_id):

    if request.user.role != "HR":
        return JsonResponse({"detail": "HR access required."}, status=403)

    employee = get_object_or_404(User, id=user_id, role="EMPLOYEE")

    try:
        profile = employee.profile
    except Profile.DoesNotExist:
        return JsonResponse({"detail": "Employee profile not found."}, status=404)

    field_name = (request.POST.get("field") or "").strip().lower()
    field_value = (request.POST.get("value") or "").strip()

    if field_name not in {"phone", "address"}:
        return JsonResponse({"detail": "Unsupported field."}, status=400)

    if field_name == "phone":
        if not field_value:
            return JsonResponse({"detail": "Phone number is required."}, status=400)

        try:
            normalized_phone = normalize_employee_phone(field_value)
        except ValueError as exc:
            return JsonResponse({"detail": str(exc)}, status=400)

        if Profile.objects.filter(phone=normalized_phone).exclude(user=employee).exists():
            return JsonResponse({"detail": "This phone number is already linked to another employee."}, status=400)

        old_phone = profile.phone
        profile.phone = normalized_phone
        profile.save(update_fields=["phone"])
        log_profile_update(profile.user, request.user, "phone", old_phone, normalized_phone)
        return JsonResponse({
            "status": "success",
            "field": "phone",
            "value": profile.phone,
        })

    try:
        normalized_address = validate_employee_address(field_value)
    except ValueError as exc:
        return JsonResponse({"detail": str(exc)}, status=400)

    old_address = profile.address
    profile.address = normalized_address
    profile.save(update_fields=["address"])
    log_profile_update(profile.user, request.user, "address", old_address, normalized_address)
    return JsonResponse({
        "status": "success",
        "field": "address",
        "value": profile.address or "Address not added yet.",
    })




from django.db.models import Count, Q
from django.contrib.auth import get_user_model
User = get_user_model()


@login_required
@never_cache
def reports(request):

    if request.user.role != "HR":
        return redirect("role_select")

    employees = User.objects.filter(role="EMPLOYEE", is_active=True)
    employee_id = (request.GET.get("employee") or "").strip()
    selected_employee_user = None

    if employee_id:
        if not employee_id.isdigit():
            return JsonResponse({"detail": "Invalid employee filter."}, status=400)

        selected_employee_user = employees.filter(id=int(employee_id)).first()
        if not selected_employee_user:
            return JsonResponse({"detail": "Invalid employee filter."}, status=404)

    leave_queryset = Leave.objects.filter(user__role="EMPLOYEE", user__is_active=True)

    if selected_employee_user:
        leave_queryset = leave_queryset.filter(user=selected_employee_user)

    report_data = leave_queryset.values("user__username", "user").annotate(
        total=Count("id"),
        approved=Count("id", filter=Q(status="Approved")),
        pending=Count("id", filter=Q(status="Pending")),
        rejected=Count("id", filter=Q(status="Rejected")),
    )

    selected_employee_name = ""

    if selected_employee_user:
        profile = getattr(selected_employee_user, "profile", None)
        emp_id = getattr(profile, "employee_id", "N/A")
        dept = getattr(profile, "department", "N/A")
        full_name = selected_employee_user.get_full_name().strip() or selected_employee_user.username
        selected_employee_name = f"{full_name} ({emp_id}) - {dept}"
        selected_employee_name_simple = full_name
    else:
        selected_employee_name_simple = ""

    # Convert to usable format
    reports = []
    for item in report_data:
        report_user = User.objects.get(id=item["user"])
        report_profile = getattr(report_user, "profile", None)
        report_display_name = report_user.get_full_name().strip() or report_user.username
        report_first_name = report_user.first_name or report_display_name.split()[0]
        reports.append({
            "user": report_user,
            "display_name": report_display_name,
            "first_name": report_first_name,
            "employee_id": getattr(report_profile, "employee_id", "Not assigned"),
            "department": getattr(report_profile, "department", "Not assigned"),
            "phone": getattr(report_profile, "phone", "Not added"),
            "photo_url": _profile_photo_url(report_profile),
            "total": item["total"],
            "approved": item["approved"],
            "pending": item["pending"],
            "rejected": item["rejected"],
            "approval_rate": round((item["approved"] / item["total"]) * 100) if item["total"] else 0,
            "pending_rate": round((item["pending"] / item["total"]) * 100) if item["total"] else 0,
            "rejected_rate": round((item["rejected"] / item["total"]) * 100) if item["total"] else 0,
        })

    total_requests = sum(item["total"] for item in reports)
    approved_total = sum(item["approved"] for item in reports)
    pending_total = sum(item["pending"] for item in reports)
    rejected_total = sum(item["rejected"] for item in reports)
    approval_rate_overall = round((approved_total / total_requests) * 100) if total_requests else 0
    top_employee = max(reports, key=lambda item: item["total"], default=None)

    context = {
        "employees": employees,
        "reports": reports,
        "selected_employee": employee_id,
        "selected_employee_name": selected_employee_name,
        "selected_employee_name_simple": selected_employee_name_simple,
        "report_employee_count": len(reports),
        "total_requests": total_requests,
        "approved_total": approved_total,
        "pending_total": pending_total,
        "rejected_total": rejected_total,
        "approval_rate_overall": approval_rate_overall,
        "top_employee": top_employee,
    }
    context.update(get_hr_notification_context(request.user))
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        from django.template.loader import render_to_string
        table_html = render_to_string("partials/reports_table_rows.html", context)
        return JsonResponse({
            "table_html": table_html,
            "selected_employee_name": selected_employee_name or "All Employees",
            "selected_employee_name_simple": selected_employee_name_simple or "All Employees",
            "metrics": {
                "total_requests": total_requests,
                "approved_total": approved_total,
                "pending_total": pending_total,
                "rejected_total": rejected_total,
                "approval_rate_overall": approval_rate_overall,
                "report_employee_count": len(reports),
            }
        })

    return render(request, "reports.html", context)


def _get_weekly_report_context_from_request(request):
    from App.services.weekly_report_service import build_weekly_hr_report_context

    week = (request.GET.get("week") or request.POST.get("week") or "current").strip().lower()
    employee_id = (request.GET.get("employee") or request.POST.get("employee") or "").strip()
    selected_employee_ids = [
        int(part)
        for part in employee_id.split(",")
        if part.strip().isdigit()
    ]
    selected_employee_id = selected_employee_ids[0] if len(selected_employee_ids) == 1 else None
    if week not in {"current", "previous", "custom"}:
        week = "current"

    if week == "custom":
        start_raw = (request.GET.get("start") or request.POST.get("start") or "").strip()
        end_raw = (request.GET.get("end") or request.POST.get("end") or "").strip()
        try:
            start_day = datetime.strptime(start_raw, "%Y-%m-%d").date()
            end_day = datetime.strptime(end_raw, "%Y-%m-%d").date()
        except ValueError:
            raise ValueError("Choose both valid from and to dates for the custom report.")

        if end_day < start_day:
            raise ValueError("To date cannot be earlier than from date.")

        return build_weekly_hr_report_context(
            week=week,
            start_day=start_day,
            end_day=end_day,
            employee_id=selected_employee_id,
            employee_ids=selected_employee_ids if len(selected_employee_ids) > 1 else None,
            include_system_health=False,
        ), week

    return build_weekly_hr_report_context(
        week=week,
        employee_id=selected_employee_id,
        employee_ids=selected_employee_ids if len(selected_employee_ids) > 1 else None,
        include_system_health=False,
    ), week


@login_required
@never_cache
def weekly_report_preview(request):
    if request.user.role != "HR":
        return JsonResponse({"detail": "HR access required."}, status=403)

    from App.services.weekly_report_service import render_weekly_hr_report_html

    try:
        context, week = _get_weekly_report_context_from_request(request)
    except ValueError as exc:
        return JsonResponse({"success": False, "detail": str(exc)}, status=400)
    context["limit_activity_scroll"] = True
    html = render_weekly_hr_report_html(context)
    return JsonResponse({
        "success": True,
        "week": week,
        "period_start": context["period_start"],
        "period_end": context["period_end"],
        "html": html,
    })


@login_required
@never_cache
def weekly_report_download(request):
    if request.user.role != "HR":
        return HttpResponseForbidden("HR access required.")

    from App.services.weekly_report_service import generate_weekly_hr_report_pdf_bytes

    try:
        context, _week = _get_weekly_report_context_from_request(request)
    except ValueError as exc:
        return HttpResponse(str(exc), status=400)
    pdf_bytes = generate_weekly_hr_report_pdf_bytes(context=context)
    filename = f"weekly_hr_report_{context['period_start_iso']}_to_{context['period_end_iso']}.pdf"
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "no-store"
    return response


@login_required
@never_cache
@require_POST
def weekly_report_email(request):
    if request.user.role != "HR":
        return JsonResponse({"success": False, "detail": "HR access required."}, status=403)

    from App.services.weekly_report_service import send_weekly_hr_report

    try:
        context, week = _get_weekly_report_context_from_request(request)
    except ValueError as exc:
        return JsonResponse({"success": False, "message": str(exc), "detail": str(exc)}, status=400)
    sent = send_weekly_hr_report(context=context, week=week)
    if sent:
        return JsonResponse({
            "success": True,
            "message": f"Weekly report emailed for {context['period_start']} - {context['period_end']}.",
        })

    return JsonResponse({
        "success": False,
        "message": "Weekly report email could not be sent. Please check email settings/logs.",
    }, status=500)




@login_required
@never_cache
@require_POST
def approve_leave(request, leave_id):
    is_ajax_request = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.user.role != "HR":
        if is_ajax_request:
            return JsonResponse({"detail": "HR access required."}, status=403)
        return redirect("role_selection")

    from App.services.leave_breakdown import calculate_leave_breakdown_for_leave

    with transaction.atomic():
        leave = get_object_or_404(
            Leave.objects.select_for_update(of=("self",)).select_related("user", "user__profile"),
            id=leave_id,
        )

        # Only pending can be approved
        if leave.status != "Pending":
            if is_ajax_request:
                return JsonResponse({"detail": "Leave is not pending anymore."}, status=409)
            messages.warning(request, "Leave is not pending anymore.")
            return redirect("hr_dashboard")

        # Just change status (balance already deducted at apply time)
        leave.status = "Approved"
        leave.approved_at = timezone.now()
        leave.rejected_at = None
        leave.reviewed_by = request.user
        leave.save(update_fields=["status", "approved_at", "rejected_at", "reviewed_by"])
        log_leave_action(
            request.user,
            "APPROVE",
            leave.id,
            f"Employee: {leave.user.username} | Type: {leave.leave_type} | Date: {leave.from_date} | Time: {localtime(leave.from_datetime).strftime('%H:%M')} to {localtime(leave.to_datetime).strftime('%H:%M')}",
        )
        queue_employee_leave_push(leave, "Approved")

    # --- Notify Employee (Approved) ---
    subject = f"Leave Request APPROVED: {leave.leave_type}"
    portal_link = get_portal_link()
    context = {
        'title': 'Leave Approved',
        'intro_text': f"Hello {leave.user.first_name or leave.user.username}, your leave request has been approved.",
        'employee_name': leave.user.get_full_name() or leave.user.username,
        'leave_type': leave.leave_type,
        'date_range': f"{leave.from_date.strftime('%d %b %Y')}",
        'reviewed_by': request.user.get_full_name().strip() or request.user.username,
        'status_label': 'Approved',
        'status_class': 'approved',
        'portal_link': portal_link
    }
    enqueue_background_task(
        send_branded_email,
        subject,
        'emails/notification.html',
        context,
        get_leave_decision_email_recipients(leave.user),
        reply_to=request.user.email,
        from_email=settings.LEAVE_DESK_FROM_EMAIL,
        email_type="leave_approved",
        related_user=leave.user,
        related_leave=leave,
        triggered_by=request.user,
        task_name="leave_approved_email",
    )

    # =====================================
    # MESSAGE LOGIC
    # =====================================

    if leave.leave_type in ["Short", "Half"]:
        leave_value = 0.25 if leave.leave_type == "Short" else 0.5

        messages.success( request, f"✔ Approved {leave.leave_type} Leave " f"({leave_value} day equivalent)")
        messages.info( request, f"Employee: {leave.user.username}")
        messages.info( request, f"Date: {leave.from_date.strftime('%d %b %Y')}")
        messages.info( request, f"Deducted From: {leave.deducted_from}")

    else:
        days = calculate_leave_breakdown_for_leave(leave)["working_days"]

        messages.success( request, f"✔ Approved '{leave.leave_type}' Leave " f"for {days} day(s)")
        messages.info( request, f"Employee: {leave.user.username}")
        messages.info( request, f"From {leave.from_date.strftime('%d %b %Y')} " f"→ To {leave.to_date.strftime('%d %b %Y')}")
        messages.info( request, f"Deducted From: {leave.deducted_from}")

    if is_ajax_request:
        employee_leaves = list(
            Leave.objects
            .filter(user_id=leave.user_id)
            .select_related("user", "user__profile")
            .order_by("-created_at")
        )
        return JsonResponse({
            "success": True,
            "status": leave.status,
            "leave_id": leave.id,
            "employee_detail": build_manage_employee_card(leave.user, employee_leaves),
            "messages": _serialize_flash_messages(request),
        })

    return redirect("hr_dashboard")



@login_required
@never_cache
@require_POST
def reject_leave(request, leave_id):
    is_ajax_request = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    if request.user.role != "HR" or request.method != "POST":
        if is_ajax_request:
            return JsonResponse({"detail": "HR access required."}, status=403)
        return redirect("role_selection")

    from App.services.leave_breakdown import calculate_leave_breakdown_for_leave, reconcile_user_full_day_leave_bridges

    rejection_reason = (request.POST.get("rejection_reason") or "").strip()
    if not rejection_reason:
        if is_ajax_request:
            return JsonResponse({"detail": "Rejection reason is required."}, status=400)
        messages.error(request, "Rejection reason is required.")
        return redirect("hr_dashboard")

    if len(rejection_reason) > REJECTION_REASON_MAX_LENGTH:
        if is_ajax_request:
            return JsonResponse({"detail": "Rejection reason must be 500 characters or fewer."}, status=400)
        messages.error(request, "Rejection reason must be 500 characters or fewer.")
        return redirect("hr_dashboard")

    with transaction.atomic():
        leave = get_object_or_404(
            Leave.objects.select_for_update(of=("self",)).select_related("user", "user__profile"),
            id=leave_id,
        )

        # Only pending leaves can be rejected
        if leave.status != "Pending":
            if is_ajax_request:
                return JsonResponse({"detail": "Only pending leave can be rejected."}, status=409)
            messages.warning(request, "Leave is not pending anymore.")
            messages.warning(request, "Only pending leave can be rejected.")
            return redirect("hr_dashboard")

        balance = LeaveBalance.objects.select_for_update().get(user=leave.user)

        # =====================================
        # DETERMINE LEAVE VALUE
        # =====================================

        if leave.leave_type in ["Short", "Half"]:
            leave_value = 0.25 if leave.leave_type == "Short" else 0.5

        elif leave.leave_type in ["Sick", "Earned", "Unpaid"]:
            leave_value = calculate_leave_breakdown_for_leave(leave)["working_days"]

        else:
            if is_ajax_request:
                return JsonResponse({"detail": "Invalid leave type."}, status=400)
            messages.error(request, "Invalid leave type.")
            return redirect("hr_dashboard")

        # =====================================
        # RESTORE BALANCE BASED ON deducted_from
        # =====================================

        if leave.leave_type in ["Short", "Half"]:

            if leave.deducted_from == "Earned":
                balance.earned_used = max(balance.earned_used - leave_value, 0)
                balance.total_leave_remaining += leave_value

            elif leave.deducted_from == "Sick":
                balance.sick_used = max(balance.sick_used - leave_value, 0)
                balance.total_leave_remaining += leave_value

        elif leave.leave_type == "Sick":
            balance.sick_used = max(balance.sick_used - leave_value, 0)
            balance.total_leave_remaining += leave_value

        elif leave.leave_type == "Earned":
            balance.earned_used = max(balance.earned_used - leave_value, 0)
            balance.total_leave_remaining += leave_value

        elif leave.leave_type == "Unpaid":
            balance.unpaid = max(balance.unpaid - leave_value, 0)

        balance.save()

        # =====================================
        # MARK AS REJECTED
        # =====================================

        leave.status = "Rejected"
        leave.rejection_reason = rejection_reason
        leave.rejected_at = timezone.now()
        leave.approved_at = None
        leave.reviewed_by = request.user
        leave.save(update_fields=["status", "rejection_reason", "rejected_at", "approved_at", "reviewed_by"])
        log_leave_action(
            request.user,
            "REJECT",
            leave.id,
            f"Employee: {leave.user.username} | Type: {leave.leave_type} | Date: {leave.from_date} | Time: {localtime(leave.from_datetime).strftime('%H:%M')} to {localtime(leave.to_datetime).strftime('%H:%M')} | Reason: {leave.rejection_reason}",
        )
        queue_employee_leave_push(leave, "Rejected")

        if leave.leave_type in ["Sick", "Earned", "Unpaid"]:
            reconcile_user_full_day_leave_bridges(leave.user)

    # --- Notify Employee (Rejected) ---
    subject = f"Leave Request REJECTED: {leave.leave_type}"
    rejection_reason = leave.rejection_reason or "No specific reason provided."
    portal_link = get_portal_link()
    context = {
        'title': 'Leave Rejected',
        'intro_text': f"Hello {leave.user.first_name or leave.user.username}, your leave request has been rejected.",
        'employee_name': leave.user.get_full_name() or leave.user.username,
        'leave_type': leave.leave_type,
        'date_range': f"{leave.from_date.strftime('%d %b %Y')}",
        'reviewed_by': request.user.get_full_name().strip() or request.user.username,
        'reason': rejection_reason,
        'status_label': 'Rejected',
        'status_class': 'rejected',
        'portal_link': portal_link
    }
    enqueue_background_task(
        send_branded_email,
        subject,
        'emails/notification.html',
        context,
        get_leave_decision_email_recipients(leave.user),
        reply_to=request.user.email,
        from_email=settings.LEAVE_DESK_FROM_EMAIL,
        email_type="leave_rejected",
        related_user=leave.user,
        related_leave=leave,
        triggered_by=request.user,
        task_name="leave_rejected_email",
    )

    # =====================================
    # SUCCESS MESSAGE
    # =====================================

    if leave.leave_type in ["Short", "Half"]:
        messages.warning( request, f"✖ Rejected {leave.leave_type} Leave " f"({leave_value} day equivalent)")
    else:
        messages.warning( request, f"✖ Rejected '{leave.leave_type}' Leave " f"for {leave_value} day(s)")

    messages.info(request, f"Employee: {leave.user.username}")
    messages.info(request, f"Deducted From: {leave.deducted_from}")

    if is_ajax_request:
        employee_leaves = list(
            Leave.objects
            .filter(user_id=leave.user_id)
            .select_related("user", "user__profile")
            .order_by("-created_at")
        )
        return JsonResponse({
            "success": True,
            "status": leave.status,
            "leave_id": leave.id,
            "employee_detail": build_manage_employee_card(leave.user, employee_leaves),
            "messages": _serialize_flash_messages(request),
        })

    return redirect("hr_dashboard")

# Here is the end of reject leave view

def admin_required(view_func):
    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect("admin_login")

        if not request.user.is_superuser:
            return redirect("role_select")

        return view_func(request, *args, **kwargs)

    return wrapper


@login_required
@admin_required
def edit_employee_profile(request, user_id):

    profile = get_object_or_404(Profile, user__id=user_id)

    if request.method == "POST":

        employee_id = (request.POST.get("employee_id") or "").strip()
        department = (request.POST.get("department") or "").strip()
        joining_date_raw = (request.POST.get("date_of_joining") or "").strip()

        if not employee_id:
            messages.error(request, "Employee ID is required.")
            return redirect(request.path)

        if len(employee_id) > 20:
            messages.error(request, "Employee ID must be 20 characters or fewer.")
            return redirect(request.path)

        if Profile.objects.filter(employee_id__iexact=employee_id).exclude(pk=profile.pk).exists():
            messages.error(request, "This employee ID is already assigned to another user.")
            return redirect(request.path)

        if not department:
            messages.error(request, "Department is required.")
            return redirect(request.path)

        if len(department) > 100:
            messages.error(request, "Department must be 100 characters or fewer.")
            return redirect(request.path)

        try:
            joining_date = date.fromisoformat(joining_date_raw)
        except ValueError:
            messages.error(request, "Please enter a valid joining date.")
            return redirect(request.path)

        profile.employee_id = employee_id
        profile.department = department
        profile.date_of_joining = joining_date

        profile.save()
        log_profile_update(profile.user, request.user, "Multiple Fields (HR Edit)", "N/A", "Updated")
        messages.success(request, "Employee profile updated.")
        return redirect("manage_employees")

    return render(request, "edit_employee_profile.html", {
        "profile": profile
    })



@never_cache
def admin_login(request):

    # 🔥 If already logged in → go to Django Admin
    if request.user.is_authenticated and request.user.is_superuser:
        return redirect("admin:index")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        blocked_response = _login_blocked_response(request, "ADMIN", username, "admin_login_form")
        if blocked_response:
            return blocked_response

        user = authenticate(request, username=username, password=password)

        if user and user.is_superuser:
            _record_successful_login(request, "ADMIN", user, username)
            login(request, user)

            # 🔥 Redirect to Django Admin
            return redirect("admin_dashboard_loading_page")

        else:
            failure_state = _register_login_failure(request, "ADMIN", username)
            _set_login_error_message(
                request,
                locked=bool(failure_state["lockout_seconds"]),
                remaining_seconds=failure_state["lockout_seconds"],
                attempts_remaining=failure_state["attempts_remaining"],
            )
            request.session["admin_login_username"] = username or ""
            return redirect("admin_login_form")

    response = render(
        request,
        "admin_login.html",
        {"prefill_username": request.session.pop("admin_login_username", "")},
    )

    # 🔥 Prevent caching login page
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    return response

@login_required
@admin_required
@never_cache
def admin_dashboard(request):

    response = render(request, "admin_dashboard.html")

    # 🔥 Prevent caching dashboard
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    return response


# Admin Panel End from here


from django.contrib.auth import update_session_auth_hash
from .forms import CustomPasswordChangeForm, UserProfileForm

def _forced_password_success_redirect(user):
    if getattr(user, "role", None) == "HR":
        return "hr_dashboard_loading_page"
    return "employee_dashboard_loading_page"


@login_required
@never_cache
def force_password_change(request):
    if not user_can_be_forced_to_change_password(request.user):
        return redirect("role_select")

    if not request.user.must_change_password:
        return redirect(_forced_password_success_redirect(request.user))

    password_form = CustomPasswordChangeForm(request.user)

    if request.method == "POST":
        password_form = CustomPasswordChangeForm(request.user, request.POST)
        if password_form.is_valid():
            user = password_form.save()
            user.must_change_password = False
            user.save(update_fields=["must_change_password"])
            update_session_auth_hash(request, user)
            AdminAuditLog.objects.create(
                model_label="App.CustomUser",
                object_id=str(user.pk),
                object_repr=str(user),
                action="FORCED_PASSWORD_COMPLETED",
                updated_by=user,
                reason="User completed forced password change.",
                changes={"must_change_password": {"old": True, "new": False}},
            )
            send_forced_password_email(user, "completed", triggered_by=user)
            messages.success(request, "Password changed successfully.")
            return redirect(_forced_password_success_redirect(user))

        request.session["forced_password_errors"] = {
            field: [str(error) for error in errors]
            for field, errors in password_form.errors.items()
        }
        request.session["forced_password_warning"] = "Please correct the password details."
        return redirect("force_password_change")

    password_errors = request.session.pop("forced_password_errors", {})
    password_warning = request.session.pop("forced_password_warning", None)

    return render(
        request,
        "auth/force_password_change.html",
        {
            "password_form": password_form,
            "password_errors": password_errors,
            "password_warning": password_warning,
            "portal_role": request.user.role,
        },
    )


@login_required
@never_cache
def profile_view(request):

    profile = request.user.profile
    balance = LeaveBalance.objects.get(user=request.user)

    profile_form = UserProfileForm(instance=profile)
    password_form = CustomPasswordChangeForm(request.user)

    sick_remaining = balance.sick_total - balance.sick_used
    earned_remaining = balance.earned_total - balance.earned_used
    total_remaining = sick_remaining + earned_remaining
    total_used = balance.sick_used + balance.earned_used


    current_date = now()
    current_month = current_date.month
    current_year = current_date.year
    active_leave_statuses = ["Pending", "Approved"]

    short_taken = Leave.objects.filter(
        user=request.user,
        leave_type="Short",
        from_date__month=current_month,
        from_date__year=current_year,
        status__in=active_leave_statuses,
    ).count()
    half_taken = Leave.objects.filter(
        user=request.user,
        leave_type="Half",
        from_date__month=current_month,
        from_date__year=current_year,
        status__in=active_leave_statuses,
    ).count()

    short_remaining = max(0, 2 - short_taken)
    half_remaining = max(0, 1 - half_taken)

    short_hours_used = short_taken * 2
    half_hours_used = half_taken * 4


    fields = [ profile.phone, profile.address, profile.profile_photo, profile.department, profile.bio ]

    filled = sum(bool(field) for field in fields)
    completion_percentage = int((filled / len(fields)) * 100)

    if request.method == "POST":

        if (request.content_type or "").startswith("application/json"):

            data = parse_json_request_body(request)
            if data is None:
                return JsonResponse({"error": "Invalid JSON payload."}, status=400)

            if data.get("update_inline"):

                field = (data.get("field") or "").strip()
                value = data.get("value")

                if field not in {"address", "bio"}:
                    return JsonResponse({"error": "Unsupported profile field."}, status=400)

                if not isinstance(value, str):
                    return JsonResponse({"error": "Invalid profile value."}, status=400)

                if field == "address":

                    try:
                        value = validate_employee_address(value)
                    except ValueError as exc:
                        return JsonResponse({"error": str(exc)}, status=400)

                    if value and len(value) < 5:
                        return JsonResponse({"error":"Address too short"}, status=400)

                    old_address = profile.address
                    profile.address = value
                    profile.save(update_fields=["address"])
                    log_profile_update(profile.user, request.user, "address", old_address, value)

                elif field == "bio":

                    try:
                        value = validate_profile_bio(value)
                    except ValueError as exc:
                        return JsonResponse({"error": str(exc)}, status=400)

                    old_bio = profile.bio
                    profile.bio = value
                    profile.save(update_fields=["bio"])
                    log_profile_update(profile.user, request.user, "bio", old_bio, value)

                fields = [ profile.phone, profile.address, profile.profile_photo, profile.department, profile.bio]

                filled = sum(bool(f) for f in fields)
                completion_percentage = int((filled / len(fields)) * 100)

                return JsonResponse({ "success": True, "completion": completion_percentage})


        elif "update_photo" in request.POST:

            photo = request.FILES.get("profile_photo")

            if not photo:
                return JsonResponse({"error": "No photo uploaded"}, status=400)

            next_photo_update_count = profile.profile_photo_update_count + 1

            try:
                sanitized_photo = _sanitize_profile_photo_upload(
                    photo,
                    profile=profile,
                    update_count=next_photo_update_count,
                )
            except ValueError as exc:
                return JsonResponse({"error": str(exc)}, status=400)

            old_profile_photo = profile.profile_photo
            target_name = profile._meta.get_field("profile_photo").generate_filename(profile, sanitized_photo.name)
            _delete_profile_photo_file(old_profile_photo, keep_name=None if old_profile_photo.name == target_name else old_profile_photo.name)

            try:
                storage = profile._meta.get_field("profile_photo").storage
                if target_name != old_profile_photo.name and storage.exists(target_name):
                    storage.delete(target_name)
            except Exception:
                security_logger.exception("Failed to delete existing profile photo target: %s", target_name)

            profile.profile_photo = sanitized_photo
            profile.profile_photo_update_count = next_photo_update_count
            profile.save(update_fields=["profile_photo", "profile_photo_update_count"])
            _delete_profile_photo_file(old_profile_photo, keep_name=profile.profile_photo.name)

            fields = [profile.phone, profile.address, profile.profile_photo, profile.department, profile.bio]
            filled = sum(bool(field) for field in fields)
            completion_percentage = int((filled / len(fields)) * 100)

            return JsonResponse({
                "success": True,
                "photo_url": profile.profile_photo.url,
                "completion": completion_percentage,
            })

            # ✅ SIZE VALIDATION
                # ✅ FORMAT CHECK (DO THIS BEFORE VERIFY)
                # ✅ VERIFY IMAGE
            # 🔥 RESET POINTER (VERY IMPORTANT)
            # ✅ SAVE
        # -------- PASSWORD CHANGE --------
        elif "change_password" in request.POST:

            password_form = CustomPasswordChangeForm(request.user, request.POST)

            if password_form.is_valid():

                user = password_form.save()
                update_session_auth_hash(request, user)

                messages.success(request, "Password changed successfully.")
                return redirect("profile")

            else:
                # store errors in session
                request.session["password_errors"] = password_form.errors
                messages.warning(request, "Please! enter the correct info.")
                return redirect("profile")

    # restore password errors
    if "password_errors" in request.session:
        password_form = CustomPasswordChangeForm(request.user)
        password_form._errors = request.session.pop("password_errors")

    context = {
        "profile": profile,
        "balance": balance,
        "profile_form": profile_form,
        "password_form": password_form,
        "completion_percentage": completion_percentage,

        "short_taken": short_taken,
        "short_remaining": short_remaining,
        "short_hours_used": short_hours_used,

        "earned_remaining" : earned_remaining,
        "sick_remaining" : sick_remaining,
        "total_leave": balance.total_leave_balance,
        "total_leave_balance": balance.total_leave_balance,
        "total_leave_remaining": _remaining_from_balance(balance),
        "total_used" : total_used,


        "half_taken": half_taken,
        "half_remaining": half_remaining,
        "half_hours_used": half_hours_used,

        "total_remaining" : total_remaining
    }
    context.update(get_employee_notification_context(request.user))
    context.update(get_communication_context(request.user))

    return render(request, "profile.html", context)







@never_cache
def employee_login(request):
    # 🔥 If already logged in, don't allow login page
    if request.user.is_authenticated and request.user.role == "EMPLOYEE":
        return redirect("dashboard")

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        blocked_response = _login_blocked_response(request, "EMPLOYEE", username, "employee_login_form")
        if blocked_response:
            return blocked_response

        user = authenticate(request, username=username, password=password)

        # 🔥 Security Hardening: Check if user exists, is EMPLOYEE, AND is active
        if user is not None and user.role == "EMPLOYEE" and user.is_active:
            _record_successful_login(request, "EMPLOYEE", user, username)
            login(request, user)
            if user.must_change_password:
                return redirect("force_password_change")
            return redirect("employee_dashboard_loading_page")

        else:
            failure_state = _register_login_failure(request, "EMPLOYEE", username)
            _set_login_error_message(
                request,
                locked=bool(failure_state["lockout_seconds"]),
                remaining_seconds=failure_state["lockout_seconds"],
                attempts_remaining=failure_state["attempts_remaining"],
            )
            request.session["employee_login_username"] = username or ""
            return redirect("employee_login_form")

    return render(
        request,
        "employee_login.html",
        {"prefill_username": request.session.pop("employee_login_username", "")},
    )



from django.core.paginator import Paginator
from django.http import JsonResponse
from datetime import date
from django.utils.formats import date_format

@login_required
@never_cache
def dashboard(request):

    if request.user.role != "EMPLOYEE":
        return redirect("role_selection")

    def get_days_left(leave, today_value):
        if not leave:
            return None
        return max(0, (leave.from_date - today_value).days)

    def is_today_leave(leave, today_value):
        if not leave:
            return False
        return leave.from_date == today_value

    def serialize_dashboard_leave_card(leave, today_value, card_kind):
        if not leave:
            return None

        is_time_based = leave.leave_type in ["Short", "Half"]
        duration = (leave.to_date - leave.from_date).days + 1

        return {
            "id": leave.id,
            "leave_type": leave.leave_type,
            "card_kind": card_kind,
            "is_time_based": is_time_based,
            "is_half": leave.leave_type == "Half",
            "from_date": date_format(leave.from_date, format="DATE_FORMAT"),
            "to_date": date_format(leave.to_date, format="DATE_FORMAT"),
            "from_time": localtime(leave.from_datetime).strftime("%I:%M %p") if leave.from_datetime else "",
            "to_time": localtime(leave.to_datetime).strftime("%I:%M %p") if leave.to_datetime else "",
            "created_at": localtime(leave.created_at).isoformat(),
            "updated_at": localtime(leave.updated_at).isoformat() if leave.updated_at else "",
            "progress_from": localtime(leave.from_datetime).strftime("%Y-%m-%d %H:%M:%S") if is_time_based and leave.from_datetime else leave.from_date.strftime("%Y-%m-%d"),
            "timeline_start": localtime(leave.from_datetime).isoformat() if is_time_based and leave.from_datetime else leave.from_date.strftime("%Y-%m-%d"),
            "timeline_end": localtime(leave.to_datetime).isoformat() if is_time_based and leave.to_datetime else leave.to_date.strftime("%Y-%m-%d"),
            "countdown_start": localtime(leave.from_datetime).isoformat() if leave.from_datetime else "",
            "countdown_end": localtime(leave.to_datetime).isoformat() if leave.to_datetime else "",
            "days_left": get_days_left(leave, today_value),
            "is_today": is_today_leave(leave, today_value),
            "duration": duration,
        }

    # 🔥 BASE QUERY
    recent_cutoff = now() - timedelta(days=30)
    leaves_qs = (
        Leave.objects
        .filter(user=request.user, created_at__gte=recent_cutoff)
        .select_related("reviewed_by")
        .order_by("-created_at")
    )

    # 🔥 PAGINATION
    page_number = request.GET.get("page", 1)
    paginator = Paginator(leaves_qs, 3)
    page_obj = paginator.get_page(page_number)

    today = date.today()

    upcoming_leaves = Leave.objects.filter(
        user=request.user,
        to_date__gte=today,
        status="Approved",
    ).order_by("from_date", "from_datetime")

    next_short_leave = upcoming_leaves.filter(leave_type__in=["Short", "Half"]).first()
    next_full_leave = upcoming_leaves.exclude(leave_type__in=["Short", "Half"]).first()
    upcoming_company_holiday = _get_upcoming_company_holiday(today)

    past_leaves = Leave.objects.filter(
        user=request.user,
        to_date__lt=today,
        status="Approved",
    ).order_by("-to_date")

    last_short_leave = past_leaves.filter(leave_type__in=["Short", "Half"]).first()
    last_full_leave = past_leaves.exclude(leave_type__in=["Short", "Half"]).first()

    balance = LeaveBalance.objects.get(user=request.user)
    pending_count = Leave.objects.filter(user=request.user, status="Pending").count()
    approved_count = Leave.objects.filter(user=request.user, status="Approved").count()
    rejected_count = Leave.objects.filter(user=request.user, status="Rejected").count()

    # ================= AJAX =================
    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        if request.GET.get("section") == "cards":
            return JsonResponse({
                "summary": {
                    "leaves_remaining": float(_remaining_from_balance(balance)),
                    "leave_total_value": float(balance.total_leave_balance),
                    "earned_total": float(balance.earned_total),
                    "earned_used": float(balance.earned_used),
                    "earned_remaining": float(max(balance.earned_total - balance.earned_used, 0)),
                    "sick_total": float(balance.sick_total),
                    "sick_used": float(balance.sick_used),
                    "sick_remaining": float(max(balance.sick_total - balance.sick_used, 0)),
                    "unpaid_used": float(balance.unpaid),
                    "approved_count": approved_count,
                    "pending_count": pending_count,
                    "rejected_count": rejected_count,
                },
                "upcoming": {
                    "short": serialize_dashboard_leave_card(next_short_leave, today, "upcoming"),
                    "full": serialize_dashboard_leave_card(next_full_leave, today, "upcoming"),
                },
                "last": {
                    "short": serialize_dashboard_leave_card(last_short_leave, today, "last"),
                    "full": serialize_dashboard_leave_card(last_full_leave, today, "last"),
                },
            })

        data = []

        for leave in page_obj:
            duration = (leave.to_date - leave.from_date).days + 1

            data.append({
                "type": leave.leave_type,

                # ✅ FULL MONTH
                "from_date": date_format(leave.from_date, format="DATE_FORMAT"),
                "to_date": date_format(leave.to_date, format="DATE_FORMAT"),

                # ✅ LOCAL TIME + FULL MONTH
                "from_datetime": localtime(leave.from_datetime).strftime("%B %d, %Y %I:%M %p"),
                "to_datetime": localtime(leave.to_datetime).strftime("%I:%M %p"),
                "from_time": localtime(leave.from_datetime).strftime("%I:%M %p") if leave.from_datetime else "",
                "to_time": localtime(leave.to_datetime).strftime("%I:%M %p") if leave.to_datetime else "",

                "status": leave.status,

                # ✅ FULL MONTH
                "created": localtime(leave.created_at).isoformat(),
                "updated": localtime(leave.updated_at).isoformat() if leave.updated_at else "",
                "approved": localtime(leave.approved_at).isoformat() if leave.approved_at else "",
                "rejected": localtime(leave.rejected_at).isoformat() if leave.rejected_at else "",
                "reviewed_by": (
                    leave.reviewed_by.get_full_name().strip() or leave.reviewed_by.username
                    if getattr(leave, "reviewed_by", None)
                    else "HR Team"
                ),

                "duration": duration,
                "reason": leave.reason or "",
                "rejection_reason": leave.rejection_reason or "",
            })

        return JsonResponse({
            "leaves": data,
            "has_next": page_obj.has_next(),
            "has_prev": page_obj.has_previous(),
            "current_page": page_obj.number,
            "total_pages": paginator.num_pages,
        })

    # ================= NORMAL LOAD =================

    for leave in page_obj:
        leave.duration = (leave.to_date - leave.from_date).days + 1

    low_balance = _remaining_from_balance(balance) <= 32

    context = {
        "recent_leaves": page_obj,
        "has_next": page_obj.has_next(),
        "has_prev": page_obj.has_previous(),
        "context_total_pages": paginator.num_pages,
        "context_current_page": 1,

        "balance": balance,
        "total_leaves": balance.total_leave_balance,
        "total_leave_balance": balance.total_leave_balance,
        "total_leave_remaining": _remaining_from_balance(balance),
        "leaves_used": balance.sick_used + balance.earned_used,
        "leaves_remaining": _remaining_from_balance(balance),
        "earned_total": balance.earned_total,
        "earned_used": balance.earned_used,
        "earned_remaining": max(balance.earned_total - balance.earned_used, 0),
        "sick_total": balance.sick_total,
        "sick_used": balance.sick_used,
        "sick_remaining": max(balance.sick_total - balance.sick_used, 0),
        "unpaid_used": balance.unpaid,
        "pending_count": pending_count,
        "approved_count": approved_count,
        "rejected_count": rejected_count,

        "upcoming_leaves": upcoming_leaves,
        "next_short_leave": next_short_leave,
        "next_full_leave": next_full_leave,
        "next_short_days": get_days_left(next_short_leave, today),
        "next_full_days": get_days_left(next_full_leave, today),
        "context_next_short_today": is_today_leave(next_short_leave, today),

        "past_leaves": past_leaves,
        "last_short_leave": last_short_leave,
        "last_full_leave": last_full_leave,

        "low_balance": low_balance,
    }
    context.update(get_employee_notification_context(request.user))
    context.update(get_communication_context(request.user))

    return render(request, "dashboard.html", context)


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def apply_leave(request):

    if request.method == "POST":

        leave_type = get_valid_leave_type(request.POST.get("leave_type"))
        if not leave_type:
            security_logger.warning(
                "INVALID_LEAVE_TYPE | action=apply | user_id=%s | ip=%s | submitted=%s",
                request.user.id,
                _get_client_ip(request),
                (request.POST.get("leave_type") or "").strip()[:80],
            )
            messages.error(request, "Invalid leave type.")
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        reason = request.POST.get("reason", "").strip()
        if len(reason) > LEAVE_REASON_MAX_LENGTH:
            messages.error(request, f"Leave reason must be {LEAVE_REASON_MAX_LENGTH} characters or fewer.")
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        user = request.user
        balance = LeaveBalance.objects.select_for_update().get(user=user)

        # =====================================================
        # 🔵 SHORT / HALF LEAVE BLOCK (Standalone)
        # =====================================================
        if leave_type in ["Short", "Half"]:

            # ===== DAILY SHORT LIMIT =====
            if leave_type == "Short":

                startdate = request.POST.get("from_date")

                existing_same_day = Leave.objects.filter( user=user, leave_type="Short", from_date=startdate, status__in=["Pending", "Approved"]).exists()
                short_half_same_day_check = Leave.objects.filter( user=user, leave_type="Half", from_date=startdate, status__in=["Pending", "Approved"]).exists()

                if existing_same_day:
                    messages.error(request, "Only one Short leave allowed per day.")

                    # ✅ STORE FORM DATA TEMPORARILY
                    store_apply_leave_form_state(request)
                    return _apply_leave_response(request)

                if short_half_same_day_check:
                    messages.error(request, "Only one either Short or Half leave allowed per day.")

                    # ✅ STORE FORM DATA TEMPORARILY
                    store_apply_leave_form_state(request)
                    return _apply_leave_response(request)

            if leave_type == "Half":

                startdate = request.POST.get("from_date")

                existing_same_day = Leave.objects.filter( user=user, leave_type="Half", from_date=startdate, status__in=["Pending", "Approved"]).exists()
                short_half_same_day_check = Leave.objects.filter( user=user, leave_type="Short", from_date=startdate, status__in=["Pending", "Approved"]).exists()

                if existing_same_day:
                    messages.error(request, "Only one Half leave allowed per day.")

                    # ✅ STORE FORM DATA TEMPORARILY
                    store_apply_leave_form_state(request)
                    return _apply_leave_response(request)

                if short_half_same_day_check:
                    messages.error(request, "Only one either Short or Half leave allowed per day.")

                    # ✅ STORE FORM DATA TEMPORARILY
                    store_apply_leave_form_state(request)
                    return _apply_leave_response(request)


            from_raw = request.POST.get("from_date")
            to_raw = request.POST.get("to_date_hidden")  # Hidden field to store the same date for validation
            reason = request.POST.get("reason", "").strip()

            try:
                from_date = date.fromisoformat(from_raw)
                to_date = date.fromisoformat(to_raw)
            except (TypeError, ValueError):
                messages.error(request, "Invalid date format.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            today = localdate()

            if to_date < from_date:
                messages.error(request, "Invalid date range: 'To date' cannot be earlier than 'From date'.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            if from_date < today or to_date < today:
                messages.error(request, "Leave date cannot be in the past.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            company_holiday = _get_blocking_company_holiday(from_date)
            if company_holiday:
                messages.error(request, f"Leave cannot be applied only on company holiday: {company_holiday.name}.")
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            if to_date != from_date:
                messages.error(request, "Invalid date range: Short/Half Day Leave should be on same date.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)


            from_datetime_raw = request.POST.get("from_datetime")
            to_datetime_raw = request.POST.get("to_datetime")

            if not from_datetime_raw or not to_datetime_raw:
                messages.error(request, "Invalid time selection.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            try:
                start = _aware_datetime(datetime.fromisoformat(from_datetime_raw))
                end = _aware_datetime(datetime.fromisoformat(to_datetime_raw))
            except ValueError:
                messages.error(request, "Invalid datetime format.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            # STRICT BUSINESS HOURS
            start_hour = 10
            end_hour = 17 if leave_type == "Short" else 14

            # print(start)

            # Convert UTC to Django project timezone (IST)
            startt = timezone.localtime(start)
            endd = timezone.localtime(end)

            # print(start)

            if startt.hour < start_hour or startt.hour > end_hour:
                messages.error(request, "Invalid start time.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)


            # Same-day Short/Half leave must respect the configured notice window.
            now = localtime()
            min_notice_minutes = _get_short_half_min_notice_minutes()
            grace_minutes = _get_short_half_grace_minutes()
            min_allowed = now + timedelta(minutes=min_notice_minutes)
            relaxed_min = min_allowed - timedelta(minutes=grace_minutes)

            if start.date() == today:
                if start < relaxed_min:
                    messages.error(request, f"Must apply at least {_format_minutes_duration(min_notice_minutes)} before.")
                    if grace_minutes:
                        messages.error(request, f"{_format_minutes_duration(grace_minutes)} of grace period is also passed.")

                    # ✅ STORE FORM DATA TEMPORARILY
                    store_apply_leave_form_state(request)
                    return _apply_leave_response(request)


            # DURATION CHECK
            duration = 2 if leave_type == "Short" else 4
            expected_end = start + timedelta(hours=duration)

            if end != expected_end:
                messages.error(request, "Invalid leave duration.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            if end <= start:
                messages.error(request, "Invalid time range.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)


            from_date = start.date()

            # ===== Monthly Limit =====
            # month_leaves = Leave.objects.filter(
            #     user=user,
            #     leave_type__in=["Short", "Half"],
            #     from_date__month=from_date.month,
            #     from_date__year=from_date.year
            # )

            month_leaves = Leave.objects.filter(
                user=user,
                leave_type__in=["Short", "Half"],
                from_date__month=start.month,
                from_date__year=start.year,
                status__in=["Pending", "Approved"]   # 🔥 Check for Only in Pending and Approved Leaves.
            )

            short_count = month_leaves.filter(leave_type="Short").count()
            half_count = month_leaves.filter(leave_type="Half").count()

            if leave_type == "Short" and short_count >= 2:
                messages.error(request, "Maximum 2 short leaves allowed per month.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            if leave_type == "Half" and half_count >= 1:
                messages.error(request, "Only 1 half-day allowed per month.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            # Checking working days in the selected range
            from App.services.leave_breakdown import calculate_leave_breakdown

            breakdown = calculate_leave_breakdown(from_date, from_date)
            days = breakdown["working_days"]

            if days == 0:
                messages.error(request, "Selected range contains only weekends/holidays. No working days to apply.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            if days < 0:
                messages.error(request, " ℹInvalid leave duration.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            # ===== Overlap Check (Datetime) =====
            overlapping = Leave.objects.filter(
                user=user,
                leave_type__in = ["Short", "Half"],
                from_datetime__lt=end,
                to_datetime__gt=start,
                status__in=["Pending", "Approved"]
            )

            if overlapping.exists():
                messages.error(request, "Overlaps with existing leave.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)


            leave_value = 0.25 if leave_type == "Short" else 0.5

            earned_remaining = balance.earned_total - balance.earned_used
            sick_remaining = balance.sick_total - balance.sick_used

            deducted_from = None

            if earned_remaining >= leave_value:
                balance.earned_used += leave_value
                deducted_from = "Earned"

            elif sick_remaining >= leave_value:
                balance.sick_used += leave_value
                deducted_from = "Sick"

            else:
                messages.error(request, "Not enough leave balance.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            balance.total_leave_remaining -= leave_value

            with transaction.atomic():
                balance.save()

                leave_obj = Leave.objects.create(
                    user=user,
                    leave_type=leave_type,
                    from_date=from_date,
                    to_date=from_date,
                    from_datetime=start,
                    to_datetime=end,
                    reason=reason,
                    status="Pending",
                    deducted_from=deducted_from
                )
                log_leave_action(
                    request.user,
                    "APPLY",
                    leave_obj.id,
                    f"Type: {leave_type} | Date: {from_date} | Time: {localtime(leave_obj.from_datetime).strftime('%H:%M')} to {localtime(leave_obj.to_datetime).strftime('%H:%M')} | Deducted From: {deducted_from}",
                )
                queue_hr_leave_push(leave_obj, "New leave request")

                # --- Notify Managers (New Request) ---
                hr_emails = get_leave_alert_recipients()
                if hr_emails:
                    subject = f"New Leave Request: {user.get_full_name() or user.username}"
                    portal_link = get_portal_link()
                    context = {
                        'title': 'New Leave Request',
                        'intro_text': f"A new leave request has been submitted by {user.get_full_name() or user.username}.",
                        'employee_name': user.get_full_name() or user.username,
                        'leave_type': leave_type,
                        'date_range': f"{from_date.strftime('%d %b %Y')}",
                        'reason': reason,
                        'status_label': 'Pending Action',
                        'status_class': 'pending',
                        'portal_link': portal_link
                    }
                    transaction.on_commit(
                        lambda subject=subject, context=context, hr_emails=hr_emails, reply_to=user.email, leave_obj=leave_obj, user=user: enqueue_background_task(
                            send_branded_email,
                            subject,
                            'emails/notification.html',
                            context,
                            hr_emails,
                            reply_to=reply_to,
                            from_email=settings.LEAVE_DESK_FROM_EMAIL,
                            email_type="leave_applied",
                            related_user=user,
                            related_leave=leave_obj,
                            triggered_by=user,
                            task_name="leave_applied_email",
                        )
                    )

            messages.success(request, f"{leave_type} Leave applied successfully.")
            messages.info(request, f"Applied for {from_date.strftime('%d %b %Y')} ({start.strftime('%H:%M')} → {end.strftime('%H:%M')})")
            messages.info(request, f"Deducted from: {deducted_from}")
            messages.info(request, f"Leave value: {leave_value} day(s)")

            request.session.pop("apply_leave_form", None)

            return _my_leave_response(request, redirect_url=reverse("my_leave"))

        # =====================================================
        # 🔵 FULL DAY LEAVE BLOCK
        # =====================================================

        # -------- STEP 1: READ & VALIDATE INPUT SAFELY --------
        from_raw = request.POST.get("from_date")
        to_raw = request.POST.get("to_date")

        try:
            from_date = date.fromisoformat(from_raw)
            to_date = date.fromisoformat(to_raw)
        except (TypeError, ValueError):
            messages.error(request, "Invalid date format.")

            # ✅ STORE FORM DATA TEMPORARILY
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        today = localdate()

        # -------- STEP 2: BASIC DATE VALIDATION --------

        # ❌ Reverse Date Range check
        if from_date > to_date:
            messages.error(request, "From date cannot be after To date.")
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        # ❌ Backward date range check
        if from_date < today or to_date < today:
            messages.error(request, "Leave date cannot be in the past.")

            # ✅ STORE FORM DATA TEMPORARILY
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        single_day_company_holiday = from_date == to_date and _get_blocking_company_holiday(from_date)
        if single_day_company_holiday:
            messages.error(request, f"Leave cannot be applied only on company holiday: {single_day_company_holiday.name}.")
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        from App.services.leave_breakdown import calculate_leave_breakdown, expand_full_day_leave_range

        requested_from_date = from_date
        requested_to_date = to_date
        expanded_range = expand_full_day_leave_range(user=user, start_date=from_date, end_date=to_date)
        from_date = expanded_range["start_date"]
        to_date = expanded_range["end_date"]
        auto_added_dates = expanded_range["auto_added_dates"]
        requested_new_from = requested_from_date
        requested_new_to = requested_to_date
        new_from = from_date
        new_to = to_date

        # Default time for full day
        start_datetime = timezone.make_aware(datetime.combine(from_date, time(10, 0)))
        end_datetime = timezone.make_aware(datetime.combine(to_date, time(19, 0)))

        # Checking working days in the selected range
        breakdown = calculate_leave_breakdown(
            from_date,
            to_date,
            requested_start_date=requested_from_date,
            requested_end_date=requested_to_date,
        )
        days = breakdown["working_days"]

        if days == 0:
            messages.error(request, "Selected range contains only weekends/holidays. No working days to apply.")

            # ✅ STORE FORM DATA TEMPORARILY
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        if days < 0:
            messages.error(request, " ℹInvalid leave duration.")

            # ✅ STORE FORM DATA TEMPORARILY
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)


        # Overlap check
        from App.services.overlap_service import get_overlap_details

        overlaps = get_overlap_details(user=request.user, start_date=from_date, end_date=to_date)

        if overlaps:
            messages.error(request, "ℹ Leave overlaps with existing leave(s):")

            for o in overlaps:
                messages.error(
                    request,
                    f"{o['leave_type']} Leave ({o['status']}) | "
                    f"{o['existing_from'].strftime('%d %b')} → "
                    f"{o['existing_to'].strftime('%d %b')} | "
                    f"Overlapping: {o['overlap_from'].strftime('%d %b')} → "
                    f"{o['overlap_to'].strftime('%d %b')} "
                    f"({o['overlap_days']} day(s))"
                )

            # ✅ STORE FORM DATA TEMPORARILY
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)


        # -------- STEP 4: LOAD BALANCE --------

        deducted_from = None

        # -------- STEP 5: VALIDATE & SIMULATE BALANCE --------
        sick_used = balance.sick_used
        earned_used = balance.earned_used
        unpaid = balance.unpaid
        total_leaves = balance.total_leave_remaining

        days_before = (requested_from_date - today).days

        if leave_type == "Sick":

            remaining = balance.sick_total - sick_used

            current_time = localtime().time()
            sick_cutoff = _get_sick_leave_same_day_cutoff_time()

            # If applying sick leave for today
            if requested_from_date == today:
                if _is_after_sick_leave_same_day_cutoff(current_time, sick_cutoff):
                    messages.error(request, f"Sick leave cannot be applied after {_format_clock_time(sick_cutoff)} for the same day.")

                    store_apply_leave_form_state(request)
                    return _apply_leave_response(request)

            # 🔒 BALANCE CHECK
            if days > remaining:
                messages.error(request, "ℹ Insufficient 'Sick' Leave balance.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            sick_used += days
            total_leaves -= days
            deducted_from = "Sick"

        elif leave_type == "Earned":

            remaining = balance.earned_total - earned_used

            # 🔒 BALANCE CHECK
            if days > remaining:
                messages.error(request, "ℹ Insufficient earned leave balance.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            elif days_before < 15:
                messages.error(request, f"ℹ The '{leave_type} Leave' cannot be applied for less than 15 days in advance.")
                messages.error(request, "ℹ Minimum advance period is 15 days.")
                messages.error(request, "ℹ Admissible advance period is 21 days.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            elif days_before >= 15 and days_before < 21:
                messages.warning( request, f"ℹ ⚠ Early application: ")
                messages.warning( request, f"ℹ You are applying '{leave_type} Leave' only {days_before} day(s) in advance." )
                messages.warning( request, "ℹ Admissible advance period is 21 days.")

            elif days_before >= 21:
                messages.warning( request, f"ℹ You are applying '{leave_type} Leave' {days_before} day(s) in advance." )

            earned_used += days
            total_leaves -= days
            deducted_from = "Earned"

        elif leave_type == "Unpaid":

            if days_before < 15:
                messages.error(request, f"ℹ The '{leave_type} Leave' cannot be applied for less than 15 days in advance.")
                messages.error(request, "ℹ Minimum advance period is 15 days.")
                messages.error(request, "ℹ Admissible advance period is 21 days.")

                # ✅ STORE FORM DATA TEMPORARILY
                store_apply_leave_form_state(request)
                return _apply_leave_response(request)

            elif days_before >= 15 and days_before < 21:
                messages.warning( request, f"ℹ⚠ Early application: ")
                messages.warning( request, f"ℹYou are applying '{leave_type} Leave' only {days_before} day(s) in advance." )
                messages.warning( request, "ℹ Admissible advance period is 21 days.")

            elif days_before >= 21:
                messages.warning( request, f"ℹ You are applying '{leave_type} Leave' {days_before} day(s) in advance." )


            # 🚫 NO LIMIT, NO DEDUCTION
            unpaid += days  # No limit
            deducted_from = "Unpaid"

        else:
            messages.error(request, "Invalid leave type.")

            # ✅ STORE FORM DATA TEMPORARILY
            store_apply_leave_form_state(request)
            return _apply_leave_response(request)

        # -------- STEP 6: ATOMIC SAVE --------
        with transaction.atomic():

            balance.sick_used = max(0, sick_used)
            balance.earned_used = max(0, earned_used)
            balance.unpaid = max(0, unpaid)
            balance.total_leave_remaining = max(0, total_leaves)
            balance.save()

            leave_obj = Leave.objects.create(
                user=user,
                leave_type=leave_type,
                from_date=from_date,
                to_date=to_date,
                requested_from_date=requested_from_date,
                requested_to_date=requested_to_date,
                from_datetime=start_datetime,
                to_datetime=end_datetime,
                reason=reason,
                status="Pending",
                deducted_from=deducted_from
            )
            log_leave_action(request.user, "APPLY", leave_obj.id, f"Type: {leave_type} | Dates: {from_date} to {to_date}")
            queue_hr_leave_push(leave_obj, "New leave request")

            # --- Notify Managers (New Full-Day Request) ---
            hr_emails = get_leave_alert_recipients()
            if hr_emails:
                subject = f"New Leave Request: {user.get_full_name() or user.username}"
                portal_link = get_portal_link()
                context = {
                    'title': 'New Leave Request',
                    'intro_text': f"A new leave request has been submitted by {user.get_full_name() or user.username}.",
                    'employee_name': user.get_full_name() or user.username,
                    'leave_type': leave_type,
                    'date_range': f"{from_date.strftime('%d %b %Y')} to {to_date.strftime('%d %b %Y')}",
                    'reason': reason,
                    'status_label': 'Pending Action',
                    'status_class': 'pending',
                    'portal_link': portal_link
                }
                transaction.on_commit(
                    lambda subject=subject, context=context, hr_emails=hr_emails, reply_to=user.email, leave_obj=leave_obj, user=user: enqueue_background_task(
                        send_branded_email,
                        subject,
                        'emails/notification.html',
                        context,
                        hr_emails,
                        reply_to=reply_to,
                        from_email=settings.LEAVE_DESK_FROM_EMAIL,
                        email_type="leave_applied",
                        related_user=user,
                        related_leave=leave_obj,
                        triggered_by=user,
                        task_name="leave_applied_email",
                    )
                )

        # -------- SUCCESS --------
        messages.success(request, f"'{leave_type}' Leave applied Successfully.")

        messages.info(request, f"Total days: {breakdown['total_days']}")

        if auto_added_dates:
            messages.info(request, "Auto-added bridge dates: " + ", ".join(current.strftime("%d %b %Y") for current in auto_added_dates))
            messages.info(request, f"Requested range {requested_from_date.strftime('%d %b')} â†’ {requested_to_date.strftime('%d %b')} was expanded and saved as {from_date.strftime('%d %b')} â†’ {to_date.strftime('%d %b')}.")

        messages.success(request, f"Applied range: {from_date.strftime('%d %b')} → {to_date.strftime('%d %b')}")

        if False and auto_added_dates:
            messages.info(request, "Auto-added bridge dates: " + ", ".join(current.strftime("%d %b %Y") for current in auto_added_dates))
            messages.info(request, f"Requested range {requested_new_from.strftime('%d %b')} â†’ {requested_new_to.strftime('%d %b')} was expanded and saved as {new_from.strftime('%d %b')} â†’ {new_to.strftime('%d %b')}.")

        if False and auto_added_dates:
            messages.info(request, "Auto-added bridge dates: " + ", ".join(current.strftime("%d %b %Y") for current in auto_added_dates))

        if breakdown["included_weekend_days"] > 0:
            messages.info(request, f"Sandwich rule applied: {breakdown['included_weekend_days']} weekend day(s) counted as leave.")
        elif breakdown["weekend_days"] > 0:
            messages.info(request, f"Excluded weekend days: {breakdown['weekend_days']}")

        if breakdown["included_wfh_days"] > 0:
            messages.info(request, f"WFH rule applied: {breakdown['included_wfh_days']} {breakdown['work_from_home_weekday_label']} day(s) were automatically counted as leave.")

        if breakdown["company_holiday_days"] > 0:
            messages.info(request, f"Company holiday day(s) counted in this leave: {breakdown['company_holiday_days']}")

        messages.success(request, f"Working leave days : {breakdown['working_days']}")


        # ✅ DELETE THE TEMPORARILY STORED FORM DATA FROM SESSION
        request.session.pop("apply_leave_form", None)
        return _my_leave_response(request, redirect_url=reverse("my_leave"))

    # =====================================================
    # 🔵 GET REQUEST
    # =====================================================

    form_data = request.session.pop("apply_leave_form", {})

    balance = LeaveBalance.objects.get(user=request.user)
    today = date.today()

    upcoming_leaves = Leave.objects.filter(
        user=request.user,
        from_date__gte=today,
        status="Approved",
    ).order_by("from_date")

    next_short_leave = upcoming_leaves.filter(leave_type__in=["Short", "Half"]).first()
    next_full_leave = upcoming_leaves.exclude(leave_type__in=["Short", "Half"]).first()
    upcoming_company_holiday = _get_upcoming_company_holiday(today)

    def get_days_left(leave):
        if not leave:
            return None
        return max(0, (leave.from_date - today).days)

    def is_today_leave(leave):
        if not leave:
            return False
        return leave.from_date == today

    def get_days_until_date(target_date):
        if not target_date:
            return None
        return max(0, (target_date - today).days)

    context = {
        "form_data": form_data,
        "balance": balance,
        "total_leaves": balance.total_leave_balance,
        "total_leave_balance": balance.total_leave_balance,
        "total_leave_remaining": _remaining_from_balance(balance),
        "leaves_used": balance.sick_used + balance.earned_used,
        "leaves_remaining": _remaining_from_balance(balance),
        "next_short_leave": next_short_leave,
        "next_full_leave": next_full_leave,
        "next_short_days": get_days_left(next_short_leave),
        "next_full_days": get_days_left(next_full_leave),
        "context_next_short_today": is_today_leave(next_short_leave),
        "upcoming_company_holiday": upcoming_company_holiday,
        "upcoming_company_holiday_days": get_days_until_date(
            upcoming_company_holiday.date if upcoming_company_holiday else None
        ),
        "company_holidays_json": json.dumps([
            {
                "date": holiday.date.strftime("%Y-%m-%d"),
                "name": holiday.name,
                "is_optional": holiday.is_optional,
            }
            for holiday in CompanyHoliday.objects.all().order_by("date")
        ]),
        "public_holidays_json": json.dumps(cache.get("public_holidays_india") or []),
        "existing_leaves_json": json.dumps([
            {
                "id": leave.id,
                "from": leave.from_date.strftime("%Y-%m-%d"),
                "to": leave.to_date.strftime("%Y-%m-%d"),
                "type": leave.leave_type,
                "status": leave.status,
                "created_at": leave.created_at.isoformat() if leave.created_at else "",
            }
            for leave in Leave.objects.filter(
                user=request.user,
                status__in=["Pending", "Approved", "Rejected"],
            ).order_by("from_date", "created_at", "id")
        ]),
        "apply_leave_rule_config": _get_apply_leave_rule_config(),
    }
    context.update(get_employee_notification_context(request.user))
    context.update(get_communication_context(request.user))

    return render(request, "apply_leave.html", context)



@login_required
@never_cache
def leave_calendar_data(request):

    # 1️⃣ USER LEAVES
    leaves = Leave.objects.filter(user=request.user).select_related("reviewed_by")
    leave_data = [
        {
            "id": l.id,
            "from": l.from_date.strftime("%Y-%m-%d"),
            "to": l.to_date.strftime("%Y-%m-%d"),
            "type": l.leave_type,
            "status": l.status,
            "reason": l.reason,
            "reviewed_by": (
                l.reviewed_by.get_full_name().strip() or l.reviewed_by.username
                if l.reviewed_by
                else ""
            ),
            "from_datetime": localtime(l.from_datetime).isoformat() if l.from_datetime else "",
            "to_datetime": localtime(l.to_datetime).isoformat() if l.to_datetime else "",
            "created_at": l.created_at.isoformat() if l.created_at else "",
            "updated_at": l.updated_at.isoformat() if l.updated_at else "",
            "approved_at": l.approved_at.isoformat() if l.approved_at else "",
            "rejected_at": l.rejected_at.isoformat() if l.rejected_at else "",
        }
        for l in leaves
    ]

    company_holidays = CompanyHoliday.objects.all().order_by("date")
    company_holiday_data = [
        {
            "date": holiday.date.strftime("%Y-%m-%d"),
            "name": holiday.name,
            "is_optional": holiday.is_optional,
        }
        for holiday in company_holidays
    ]
    holidays = get_public_holidays()

    # 2️⃣ COMPANY CLOSURES (MANUAL)
    # company_closures = CompanyClosure.objects.all()
    # closure_data = [
    #     {
    #         "date": c.date.strftime("%Y-%m-%d"),
    #         "name": c.name,
    #     }
    #     for c in company_closures
    # ]

    # 3️⃣ AUTO HOLIDAYS (INDIA + INTERNATIONAL)
    # holidays = []
    # year = date.today().year
    # try:
    #     res = requests.get(
    #         f"https://date.nager.at/api/v3/PublicHolidays/{year}/IN",
    #         timeout=5
    #     )
    #     if res.status_code == 200:
    #         for h in res.json():
    #             holidays.append({
    #                 "date": h["date"],
    #                 "name": h["localName"],
    #                 "type": "National" if h["global"] else "Festival"
    #             })
    # except Exception:
    #     pass  # fail silently (calendar still works)

    # ===== GOOGLE PUBLIC HOLIDAYS (INDIA) =====
    # holidays = []
    # try:
    #     res = requests.get(
    #         "https://calendar.google.com/calendar/ical/en.indian%23holiday%40group.v.calendar.google.com/public/basic.ics",
    #          timeout=10)

    #     calendar = Calendar(res.text)
    #     current_year = date.today().year

    #     for event in calendar.events:
    #         if event.begin.year == current_year:
    #             holidays.append({
    #                 "date": event.begin.format("YYYY-MM-DD"),
    #                 "name": event.name,
    #                 "type": "Public"
    #             })

    # except Exception as e:
    #     print("Holiday fetch failed:", e)


    return JsonResponse({
        "leaves": leave_data,
        "company_holidays": company_holiday_data,
        "holidays": holidays
    })


def _build_my_leave_context(request):
    filters = request.session.get("filters", {})

    def apply_filters(qs, status):

        f = filters.get(status, {})

        leave_type = get_valid_leave_type(f.get("leave_type"))
        try:
            month = get_valid_filter_month(f.get("month"))
            from_date = get_valid_filter_date(f.get("from_date"), "from date")
            to_date = get_valid_filter_date(f.get("to_date"), "to date")
        except ValueError:
            filters.pop(status, None)
            request.session["filters"] = filters
            return qs

        if leave_type:
            qs = qs.filter(leave_type=leave_type)

        if month:
            year, m = map(int, month.split("-"))
            qs = qs.filter(from_date__year=year, from_date__month=m)

        else:
            if from_date:
                qs = qs.filter(from_date__gte=from_date)
            if to_date:
                qs = qs.filter(to_date__lte=to_date)

        return qs


    balance = get_object_or_404(LeaveBalance, user=request.user)

    pending_leaves = apply_filters(Leave.objects.filter(user=request.user, status="Pending"),"Pending").order_by("-created_at")

    approved_leaves = apply_filters(
        Leave.objects.filter(user=request.user, status="Approved").select_related("reviewed_by"),
        "Approved",
    ).order_by("-created_at")

    rejected_leaves = apply_filters(
        Leave.objects.filter(user=request.user, status="Rejected").select_related("reviewed_by"),
        "Rejected",
    ).order_by("-created_at")

    from App.services.leave_breakdown import calculate_leave_breakdown_for_leave

    def attach_my_leave_days(leaves):
        for leave in leaves:
            if leave.leave_type == "Short":
                leave.days_value = 2
                leave.days_value_display = "2 hour"
                leave.days_target = 2
                leave.days_suffix = " hour"
                leave.days_label = "of the day"
            elif leave.leave_type == "Half":
                leave.days_value = 4
                leave.days_value_display = "4 hour"
                leave.days_target = 4
                leave.days_suffix = " hour"
                leave.days_label = "of the day"
            else:
                working_days = calculate_leave_breakdown_for_leave(leave)["working_days"]
                safe_days = max(int(working_days or 0), 0)
                leave.days_value = safe_days
                leave.days_value_display = str(safe_days)
                leave.days_target = safe_days
                leave.days_suffix = ""
                leave.days_label = "day" if safe_days == 1 else "days"

    attach_my_leave_days(pending_leaves)
    attach_my_leave_days(approved_leaves)
    attach_my_leave_days(rejected_leaves)

    current_date = now()
    short_taken = Leave.objects.filter(
        user=request.user,
        leave_type="Short",
        status__in=["Pending", "Approved"],
        from_date__month=current_date.month,
        from_date__year=current_date.year,
    ).count()
    half_taken = Leave.objects.filter(
        user=request.user,
        leave_type="Half",
        status__in=["Pending", "Approved"],
        from_date__month=current_date.month,
        from_date__year=current_date.year,
    ).count()
    calendar_blocking_leaves = Leave.objects.filter(
        user=request.user,
        status__in=["Pending", "Approved", "Rejected"],
    ).order_by("from_date")

    sick_remaining = balance.sick_total - balance.sick_used
    earned_remaining = balance.earned_total - balance.earned_used

    context = {
        'balance': balance,

        "sick_remaining": sick_remaining,
        "earned_remaining": earned_remaining,
        "short_taken_month": short_taken,
        "half_taken_month": half_taken,

        'pending_leaves': pending_leaves,
        'approved_leaves': approved_leaves,
        'rejected_leaves': rejected_leaves,

        # 🔹 Send back selected filters (for UI state)
        # "selected_leave_type": leave_type,
        # "selected_month": month,
        # "selected_from_date": from_date,
        # "selected_to_date": to_date,

        # ✅ For Django template (badges)
        "filters": filters,

        # ✅ For JavaScript (modal)
        "filters_json": json.dumps(filters),
        "upcoming_company_holiday": _get_upcoming_company_holiday(),
        "company_holidays_json": json.dumps([
            {
                "date": holiday.date.strftime("%Y-%m-%d"),
                "name": holiday.name,
                "is_optional": holiday.is_optional,
            }
            for holiday in CompanyHoliday.objects.all().order_by("date")
        ]),
        "existing_leaves_json": json.dumps([
            {
                "id": leave.id,
                "from": leave.from_date.strftime("%Y-%m-%d"),
                "to": leave.to_date.strftime("%Y-%m-%d"),
                "type": leave.leave_type,
                "status": leave.status,
                "created_at": leave.created_at.isoformat() if leave.created_at else "",
                "updated_at": leave.updated_at.isoformat() if leave.updated_at else "",
                "approved_at": leave.approved_at.isoformat() if leave.approved_at else "",
                "rejected_at": leave.rejected_at.isoformat() if leave.rejected_at else "",
            }
            for leave in calendar_blocking_leaves
        ]),
    }
    context.update(get_employee_notification_context(request.user))
    context.update(get_communication_context(request.user))

    return context


@login_required
@never_cache
def my_leave(request):
    context = _build_my_leave_context(request)

    if _is_ajax_request(request) and request.GET.get("section") == "live_data":
        live_counts = {
            "pending": Leave.objects.filter(user=request.user, status="Pending").count(),
            "approved": Leave.objects.filter(user=request.user, status="Approved").count(),
            "rejected": Leave.objects.filter(user=request.user, status="Rejected").count(),
        }
        return JsonResponse({
            "summary_html": render_to_string(
                "includes/my_leave_summary_panels.html",
                context,
                request=request,
            ),
            "stats_html": render_to_string(
                "includes/my_leave_stat_cards.html",
                context,
                request=request,
            ),
            "pending_rows_html": render_to_string(
                "includes/my_leave_pending_rows.html",
                context,
                request=request,
            ),
            "approved_rows_html": render_to_string(
                "includes/my_leave_approved_rows.html",
                context,
                request=request,
            ),
            "rejected_rows_html": render_to_string(
                "includes/my_leave_rejected_rows.html",
                context,
                request=request,
            ),
            "counts": {
                "pending": context["pending_leaves"].count(),
                "approved": context["approved_leaves"].count(),
                "rejected": context["rejected_leaves"].count(),
            },
            "live_counts": live_counts,
            "existing_leaves_json": context["existing_leaves_json"],
        })

    messages.success(request, "Updated latest leave information.")

    return render(request, 'my_leave.html', context)


@login_required
@never_cache
@require_POST
def apply_status_filter(request, status):
    if request.user.role != "EMPLOYEE":
        return redirect("role_select")

    status = get_valid_leave_status(status)
    if not status:
        messages.error(request, "Invalid filter section.")
        return _my_leave_response(request, status=400)

    filters = request.session.get("filters", {})

    try:
        leave_type_raw = (request.POST.get("leave_type") or "").strip()
        leave_type = get_valid_leave_type(leave_type_raw) if leave_type_raw else None
        if leave_type_raw and not leave_type:
            raise ValueError("Invalid leave type filter.")

        month = get_valid_filter_month(request.POST.get("month"))
        from_date = get_valid_filter_date(request.POST.get("from_date"), "from date")
        to_date = get_valid_filter_date(request.POST.get("to_date"), "to date")
    except ValueError as exc:
        messages.error(request, str(exc))
        return _my_leave_response(request, filter_status=status, status=400)

    if from_date and to_date and from_date > to_date:
        messages.error(request, "From date filter cannot be after To date filter.")
        return _my_leave_response(request, filter_status=status, status=400)

    # mutual exclusivity
    if month:
        from_date = None
        to_date = None
    elif from_date or to_date:
        month = None

    filters[status] = {
        "leave_type": leave_type,
        "month": month,
        "from_date": from_date,
        "to_date": to_date,
    }

    request.session["filters"] = filters

    messages.success(request, "Filter has been applied !")

    return _my_leave_response(request, filter_status=status)

@login_required
@never_cache
@require_POST
def clear_status_filter(request, status):
    if request.user.role != "EMPLOYEE":
        return redirect("role_select")

    status = get_valid_leave_status(status)
    if not status:
        messages.error(request, "Invalid filter section.")
        return _my_leave_response(request, status=400)

    filters = request.session.get("filters", {})
    filters.pop(status, None)
    request.session["filters"] = filters

    messages.success(request, "All Filter has been cleared !")
    return _my_leave_response(request, filter_status=status)


@login_required
@never_cache
@require_POST
def clear_status_filter_field(request, status, field):
    if request.user.role != "EMPLOYEE":
        return redirect("role_select")

    status = get_valid_leave_status(status)
    field = (field or "").strip()
    if not status or field not in ALLOWED_LEAVE_FILTER_FIELDS:
        messages.error(request, "Invalid filter field.")
        return _my_leave_response(request, status=400)

    filters = request.session.get("filters", {})

    if status in filters:
        if field == "date_range":
            filters[status].pop("from_date", None)
            filters[status].pop("to_date", None)
        else:
            filters[status].pop(field, None)

        # Clean empty filter block
        if not any(filters[status].values()):
            filters.pop(status)

    messages.success(request, "Particular Filter has been clear !")
    request.session["filters"] = filters
    return _my_leave_response(request, filter_status=status)


@login_required
@never_cache
@require_POST
@transaction.atomic
def delete_leave(request, leave_id):

    leave = get_object_or_404(Leave.objects.select_for_update(), id=leave_id, user=request.user)
    balance = get_object_or_404(LeaveBalance.objects.select_for_update(), user=leave.user)

    if leave.status == "Pending":

        from App.services.leave_breakdown import calculate_leave_breakdown_for_leave, reconcile_user_full_day_leave_bridges

        # =====================================================
        # 🔵 SHORT / HALF LOGIC
        # =====================================================
        if leave.leave_type in ["Short", "Half"]:

            leave_value = 0.25 if leave.leave_type == "Short" else 0.5

            # Restore EXACT bucket
            if leave.deducted_from == "Earned":
                balance.earned_used = max(balance.earned_used - leave_value, 0)

            elif leave.deducted_from == "Sick":
                balance.sick_used = max(balance.sick_used - leave_value, 0)

            balance.total_leave_remaining += leave_value

            balance.save()

            messages.success( request, f"Deleted {leave.leave_type} Leave Successfully" )
            messages.info( request, f"Restored {leave_value} day(s) to {leave.deducted_from} balance." )
            messages.info( request, f"Date: {leave.from_date.strftime('%d %b')} ({leave.from_datetime.strftime('%H:%M')} → {leave.to_datetime.strftime('%H:%M')})" )

            deleted_leave_id = leave.id
            log_leave_action(
                request.user,
                "DELETE",
                leave.id,
                f"Type: {leave.leave_type} | Date: {leave.from_date} | Time: {localtime(leave.from_datetime).strftime('%H:%M')} to {localtime(leave.to_datetime).strftime('%H:%M')} | Deducted From: {leave.deducted_from}",
            )
            queue_hr_leave_push(leave, "Leave deleted")
            leave.delete()
            pending_count = Leave.objects.filter(user=request.user, status="Pending").count()
            return _my_leave_response(request, deleted_id=deleted_leave_id, pending_count=pending_count)

        # =====================================================
        # 🔵 FULL DAY LEAVE LOGIC
        # =====================================================

        breakdown = calculate_leave_breakdown_for_leave(leave)

        days = breakdown["working_days"]
        weekend_days = breakdown["weekend_days"]
        company_holiday_days = breakdown["company_holiday_days"]

        # 🔄 Restore using deducted_from (more accurate)
        if leave.deducted_from == "Sick":
            balance.sick_used = max(balance.sick_used - days, 0)
            balance.total_leave_remaining += days

        elif leave.deducted_from == "Earned":
            balance.earned_used = max(balance.earned_used - days, 0)
            balance.total_leave_remaining += days

        elif leave.deducted_from == "Unpaid":
            balance.unpaid = max(balance.unpaid - days, 0)

        balance.save()

        # 🧾 Proper messages
        messages.success( request, f"Deleted {leave.leave_type} Leave Successfully")
        messages.success( request, f"({days} working day(s))")
        messages.success( request, f"From {leave.from_date.strftime('%d %b')} → " f"To {leave.to_date.strftime('%d %b')}.")
        if breakdown["included_weekend_days"] > 0:
            messages.info(request, f"Sandwich-counted weekend days restored: {breakdown['included_weekend_days']}")
        elif weekend_days > 0:
            messages.info(request, f"Excluded weekend days: {weekend_days}")

        if breakdown["included_wfh_days"] > 0:
            messages.info(request, f"WFH-counted leave days restored: {breakdown['included_wfh_days']}")

        if company_holiday_days > 0:
            messages.info(request, f"Company holiday day(s) restored in balance: {company_holiday_days}")

        deleted_leave_id = leave.id
        log_leave_action(request.user, "DELETE", leave.id, f"Type: {leave.leave_type}")
        queue_hr_leave_push(leave, "Leave deleted")
        leave.delete()
        reconcile_user_full_day_leave_bridges(request.user)

        live_counts = {
            "pending": Leave.objects.filter(user=request.user, status="Pending").count(),
            "approved": Leave.objects.filter(user=request.user, status="Approved").count(),
            "rejected": Leave.objects.filter(user=request.user, status="Rejected").count(),
        }

        return _my_leave_response(request, deleted_id=deleted_leave_id, live_counts=live_counts, pending_count=live_counts["pending"])

    return _my_leave_response(request, status=400)




@login_required
@never_cache
@require_http_methods(["POST"])
@transaction.atomic
def edit_leave(request, leave_id):

    leave = get_object_or_404(Leave.objects.select_for_update(), id=leave_id)

    # 🔐 SECURITY
    if leave.user != request.user:
        if _is_ajax_request(request):
            return JsonResponse({"success": False, "messages": [{"tags": "error", "text": "Not allowed", "title": "Action needed"}]}, status=403)
        return HttpResponseForbidden("Not allowed")

    if leave.status != "Pending":
        if _is_ajax_request(request):
            return JsonResponse({"success": False, "messages": [{"tags": "error", "text": "Only pending leaves can be edited", "title": "Action needed"}]}, status=403)
        return HttpResponseForbidden("Only pending leaves can be edited")

    today = localdate()

    # ===============================
    # READ INPUT ONCE
    # ===============================
    new_type = get_valid_leave_type(request.POST.get("edit_leave_type"))
    if not new_type:
        security_logger.warning(
            "INVALID_LEAVE_TYPE | action=edit | user_id=%s | leave_id=%s | ip=%s | submitted=%s",
            request.user.id,
            leave.id,
            _get_client_ip(request),
            (request.POST.get("edit_leave_type") or "").strip()[:80],
        )
        messages.error(request, "Invalid leave type.")
        return _my_leave_response(request, status=400)

    from_date_raw = (request.POST.get("from_date") or "").strip()
    to_date_raw = (request.POST.get("to_date") or "").strip()

    if not from_date_raw or not to_date_raw:
        messages.error(request, "From date and to date are required.")
        return _my_leave_response(request, status=400)

    try:
        new_from = date.fromisoformat(from_date_raw)
        new_to = date.fromisoformat(to_date_raw)
        new_reason = request.POST.get("reason", "").strip()
        if len(new_reason) > LEAVE_REASON_MAX_LENGTH:
            messages.error(request, f"Leave reason must be {LEAVE_REASON_MAX_LENGTH} characters or fewer.")
            return _my_leave_response(request, status=400)

        old_from = leave.from_date
        old_to = leave.to_date

    except Exception:
        messages.error(request, "Invalid input.")
        return _my_leave_response(request, status=400)

    # if not new_type:
    #     messages.error(request, "Leave type missing.")
    #     return redirect("my_leave")

    # ===============================
    # BASIC DATE VALIDATION
    # ===============================
    if new_from > new_to:
        messages.error(request, "Invalid date range.")
        return _my_leave_response(request, status=400)

    if new_from < today or new_to < today:
        messages.error(request, "You cannot edit leave to past dates.")
        return _my_leave_response(request, status=400)

    single_day_company_holiday = new_from == new_to and _get_blocking_company_holiday(new_from)
    if single_day_company_holiday:
        messages.error(request, f"Leave cannot be applied only on company holiday: {single_day_company_holiday.name}.")
        return _my_leave_response(request, status=400)

    balance = LeaveBalance.objects.select_for_update().get(user=request.user)

    # ===============================
    # PREPARE SIMULATED BALANCE
    # ===============================
    sick_used = balance.sick_used
    earned_used = balance.earned_used
    unpaid = balance.unpaid
    total_leaves = balance.total_leave_remaining

    # ===============================
    # REFUND OLD LEAVE (SIMULATED)
    # ===============================
    old_type = leave.leave_type
    old_value = 0.25 if old_type == "Short" else 0.5
    old_days = (leave.to_date - leave.from_date).days + 1

    if old_type in ["Short", "Half"]:

        if leave.deducted_from == "Earned":
            earned_used -= old_value
            total_leaves += old_value
        elif leave.deducted_from == "Sick":
            sick_used -= old_value
            total_leaves += old_value

    else:
        old_days = __import__(
            "App.services.leave_breakdown",
            fromlist=["calculate_leave_breakdown_for_leave"],
        ).calculate_leave_breakdown_for_leave(leave)["working_days"]

        if old_type == "Sick":
            sick_used -= old_days
            total_leaves += old_days

        elif old_type == "Earned":
            earned_used -= old_days
            total_leaves += old_days

        elif old_type == "Unpaid":
            unpaid -= old_days

    # =========================================================
    # 🔥 SHORT / HALF EDIT LOGIC
    # =========================================================
    if new_type in ["Short", "Half"]:

        if new_from != new_to:
            messages.error(request, "Short/Half leave must be for single day.")
            return _my_leave_response(request, status=400)

        company_holiday = _get_blocking_company_holiday(new_from)
        if company_holiday:
            messages.error(request, f"Leave cannot be applied only on company holiday: {company_holiday.name}.")
            return _my_leave_response(request, status=400)



        from_datetime = request.POST.get("from_datetime")
        to_datetime = request.POST.get("to_datetime")

        if not from_datetime or not to_datetime:
            messages.error(request, "Invalid time selection.")
            return _my_leave_response(request, status=400)

        try:
            start = _aware_datetime(datetime.fromisoformat(from_datetime))
            end = _aware_datetime(datetime.fromisoformat(to_datetime))
        except:
            messages.error(request, "Invalid datetime format.")
            return _my_leave_response(request, status=400)

        # STRICT BUSINESS HOURS
        start_hour = 10
        end_hour = 17 if new_type == "Short" else 15

        # print(start)

        # Convert UTC to Django project timezone (IST)
        startt = timezone.localtime(start)
        endd = timezone.localtime(end)

        if startt.hour < start_hour or startt.hour > end_hour:
            messages.error(request, "Invalid start time.")
            return _my_leave_response(request, status=400)

        # Same-day Short/Half leave edits must respect the configured notice window.
        now = localtime()
        min_notice_minutes = _get_short_half_min_notice_minutes()
        grace_minutes = _get_short_half_grace_minutes()
        min_allowed = now + timedelta(minutes=min_notice_minutes)
        relaxed_min = min_allowed - timedelta(minutes=grace_minutes)

        if start.date() == today:
            if start < relaxed_min:
                messages.error(request, f"Must apply at least {_format_minutes_duration(min_notice_minutes)} before.")
                if grace_minutes:
                    messages.error(request, f"{_format_minutes_duration(grace_minutes)} of grace period is also passed.")
                return _my_leave_response(request, status=400)

        # DURATION CHECK
        duration = 2 if new_type == "Short" else 4
        expected_end = start + timedelta(hours=duration)

        if end != expected_end:
            messages.error(request, "Invalid leave duration.")
            return _my_leave_response(request, status=400)

        if end <= start:
            messages.error(request, "Invalid time range.")
            return _my_leave_response(request, status=400)


        # DAILY LIMIT
        if new_type == "Short":

            exists_same_day = Leave.objects.filter( user=request.user, leave_type="Short", from_date=new_from, status__in=["Pending", "Approved"] ).exclude(id=leave.id).exists()
            short_half_same_day_check = Leave.objects.filter( user=request.user, leave_type="Half", from_date=new_from, status__in=["Pending", "Approved"] ).exclude(id=leave.id).exists()

            if exists_same_day:
                messages.error(request, "Only one Short leave allowed per day.")
                return _my_leave_response(request, status=400)

            if short_half_same_day_check:
                messages.error(request, "Only one either Short or Half leave allowed per day.")
                return _my_leave_response(request, status=400)

        if new_type == "Half":

            existing_same_day = Leave.objects.filter( user=request.user, leave_type="Half", from_date=new_from, status__in=["Pending", "Approved"]).exclude(id=leave.id).exists()
            short_half_same_day_check = Leave.objects.filter( user=request.user, leave_type="Short", from_date=new_from, status__in=["Pending", "Approved"]).exclude(id=leave.id).exists()

            if existing_same_day:
                messages.error(request, "Only one Half leave allowed per day.")

                return _my_leave_response(request, status=400)

            if short_half_same_day_check:
                messages.error(request, "Only one either Short or Half leave allowed per day.")

                return _my_leave_response(request, status=400)


        # MONTHLY LIMIT
        month_leaves = Leave.objects.filter(
            user=request.user,
            leave_type__in=["Short", "Half"],
            from_date__month=new_from.month,
            from_date__year=new_from.year,
            status__in=["Pending", "Approved"]
        ).exclude(id=leave.id)

        if new_type == "Short" and month_leaves.filter(leave_type="Short").count() >= 2:
            messages.error(request, "Maximum 2 Short leaves per month.")
            return _my_leave_response(request, status=400)

        if new_type == "Half" and month_leaves.filter(leave_type="Half").count() >= 1:
            messages.error(request, "Only 1 Half-day allowed per month.")
            return _my_leave_response(request, status=400)




        # Checking working days in the selected range
        from App.services.leave_breakdown import calculate_leave_breakdown

        breakdown = calculate_leave_breakdown(new_from, new_to)
        days = breakdown["working_days"]

        if days == 0:
            messages.error(request, "Selected range contains only weekends/holidays. No working days to apply.")
            return _my_leave_response(request, status=400)

        if days < 0:
            messages.error(request, " ℹInvalid leave duration.")
            return _my_leave_response(request, status=400)


        # ===== Overlap Check (Datetime) =====
        overlapping = Leave.objects.filter(
            user=request.user,
            leave_type__in = ["Short", "Half"],
            from_datetime__lt=end,
            to_datetime__gt=start,
            status__in=["Pending", "Approved"]
        ).exclude(id=leave.id)

        if overlapping.exists():
            messages.error(request, "Date/Time Overlaps with existing leave.")
            return _my_leave_response(request, status=409)


        leave_value = 0.25 if new_type == "Short" else 0.5

        # BALANCE CHECK
        deducted_from = None

        if balance.earned_total - earned_used >= leave_value:
            earned_used += leave_value
            deducted_from = "Earned"

        elif balance.sick_total - sick_used >= leave_value:
            sick_used += leave_value
            deducted_from = "Sick"

        else:
            messages.error(request, "Not enough leave balance.")
            return _my_leave_response(request, status=400)

        total_leaves -= leave_value

        # SAVE ATOMICALLY
        with transaction.atomic():
            balance.sick_used = max(sick_used, 0)
            balance.earned_used = max(earned_used, 0)
            balance.total_leave_remaining = max(total_leaves, 0)
            balance.unpaid = max(unpaid, 0)
            balance.save()
            leave.leave_type = new_type
            leave.from_date = new_from
            leave.to_date = new_to
            leave.reason = new_reason
            leave.from_datetime = start
            leave.to_datetime = end
            leave.deducted_from = deducted_from
            leave.updated_at = timezone.now()
            leave.no_of_times_updated = (leave.no_of_times_updated or 0) + 1
            refresh_pending_leave_notification(leave)
            leave.save()
            log_leave_action(
                request.user,
                "EDIT",
                leave.id,
                f"Changes: {old_type} to {new_type} | Date: {new_from} | Time: {localtime(leave.from_datetime).strftime('%H:%M')} to {localtime(leave.to_datetime).strftime('%H:%M')} | Deducted From: {deducted_from}",
            )

            # --- Notify Managers (Updated Request) ---
            hr_emails = get_leave_alert_recipients()
            if hr_emails:
                subject = f"Leave Request UPDATED: {request.user.get_full_name() or request.user.username}"
                portal_link = get_portal_link()
                context = {
                    'title': 'Leave Request Updated',
                    'intro_text': f"{request.user.get_full_name() or request.user.username} has updated their pending {new_type} leave request.",
                    'employee_name': request.user.get_full_name() or request.user.username,
                    'leave_type': new_type,
                    'date_range': f"{new_from.strftime('%d %b %Y')} ({start.strftime('%I:%M %p')} → {end.strftime('%I:%M %p')})",
                    'reason': new_reason,
                    'status_label': 'Updated',
                    'status_class': 'updated',
                    'portal_link': portal_link
                }
                transaction.on_commit(
                    lambda subject=subject, context=context, hr_emails=hr_emails, reply_to=request.user.email, leave=leave, actor=request.user: enqueue_background_task(
                        send_branded_email,
                        subject,
                        'emails/notification.html',
                        context,
                        hr_emails,
                        reply_to=reply_to,
                        from_email=settings.LEAVE_DESK_FROM_EMAIL,
                        email_type="leave_updated",
                        related_user=actor,
                        related_leave=leave,
                        triggered_by=actor,
                        task_name="leave_updated_email",
                    )
                )

        messages.success(request, f"Successfully updated leave from {old_type} → {new_type}")
        messages.success(request, f"Leave date: From {new_from.strftime('%d %b %Y')} → {new_to.strftime('%d %b %Y')} ({start.strftime('%H:%M')} → {end.strftime('%H:%M')})")

        queue_hr_leave_push(leave, "Leave updated")
        return _my_leave_response(request, leave=_serialize_leave_for_my_leave(leave))

    # =========================================================
    # 🔥 NORMAL LEAVE LOGIC
    # =========================================================

    from App.services.leave_breakdown import calculate_leave_breakdown, expand_full_day_leave_range, reconcile_user_full_day_leave_bridges
    from App.services.overlap_service import get_overlap_details

    single_day_company_holiday = new_from == new_to and _get_blocking_company_holiday(new_from)
    if single_day_company_holiday:
        messages.error(request, f"Leave cannot be applied only on company holiday: {single_day_company_holiday.name}.")
        return _my_leave_response(request, status=400)

    requested_new_from = new_from
    requested_new_to = new_to
    expanded_range = expand_full_day_leave_range(
        user=request.user,
        start_date=new_from,
        end_date=new_to,
        exclude_id=leave.id,
    )
    new_from = expanded_range["start_date"]
    new_to = expanded_range["end_date"]
    auto_added_dates = expanded_range["auto_added_dates"]

    breakdown = calculate_leave_breakdown(
        new_from,
        new_to,
        requested_start_date=requested_new_from,
        requested_end_date=requested_new_to,
    )
    new_days = breakdown["working_days"]

    if new_days <= 0:
        messages.error(request, "Invalid leave duration.")
        return _my_leave_response(request, status=400)

    overlaps = get_overlap_details(user=request.user, start_date=new_from, end_date=new_to, exclude_id=leave.id )

    if overlaps:
        messages.error(request, "ℹ Leave overlaps with existing leave(s):")

        for o in overlaps:
            messages.error(
                request,
                f"{o['leave_type']} Leave ({o['status']}) | "
                f"{o['existing_from'].strftime('%d %b')} → " f"{o['existing_to'].strftime('%d %b')} | "
                f"Overlapping: {o['overlap_from'].strftime('%d %b')} → " f"{o['overlap_to'].strftime('%d %b')} "
                f"({o['overlap_days']} day(s))"
            )

        return _my_leave_response(request, status=409)

    deducted_from = None

    # -------- SICK --------
    if new_type == "Sick":

        sick_cutoff = _get_sick_leave_same_day_cutoff_time()
        if requested_new_from == today and _is_after_sick_leave_same_day_cutoff(localtime().time(), sick_cutoff):
            messages.error(request, f"Sick leave cannot be applied after {_format_clock_time(sick_cutoff)}.")
            return _my_leave_response(request, status=400)

        remaining = balance.sick_total - sick_used

        # 🔒 BALANCE CHECK
        if new_days > remaining:
            messages.error(request, "Insufficient Sick leave balance.")
            return _my_leave_response(request, status=400)

        sick_used += new_days
        total_leaves -= new_days
        deducted_from = "Sick"

    # -------- EARNED --------
    elif new_type == "Earned":

        remaining = balance.earned_total - earned_used
        days_before = (requested_new_from - today).days

        # 🔒 BALANCE CHECK
        if new_days > remaining:
            messages.error(request, "ℹ Insufficient earned leave balance.")
            return _my_leave_response(request, status=400)

        if days_before < 15:
            messages.error(request, f"The '{new_type} Leave' cannot be applied for less than 15 days in advance.")
            messages.error(request, "ℹ Minimum advance period is 15 days.")
            messages.error(request, "ℹ Admissible advance period is 21 days.")
            return _my_leave_response(request, status=400)

        elif days_before >= 15 and days_before < 21:
            messages.warning( request, "ℹ ⚠ Early application")
            messages.warning( request, f"ℹ You are applying '{new_type} Leave' only {days_before} day(s) in advance." )
            messages.warning( request, "ℹ Admissible advance period is 21 days.")

        elif days_before >= 21:
            messages.warning( request, f"ℹ You are applying '{new_type} Leave' {days_before} day(s) in advance." )

        earned_used += new_days
        total_leaves -= new_days
        deducted_from = "Earned"

    # -------- UNPAID --------
    elif new_type == "Unpaid":

        days_before = (requested_new_from - today).days

        if days_before < 15:
            messages.error(request, f"ℹ The '{new_type} Leave' cannot be applied for less than 15 days in advance.")
            messages.error(request, "ℹ Minimum advance period is 15 days.")
            messages.error(request, "ℹ Admissible advance period is 21 days.")
            return _my_leave_response(request, status=400)

        elif days_before >= 15 and days_before < 21:
            messages.warning( request, "⚠ Early application")
            messages.warning( request, f"ℹ You are applying '{new_type} Leave' only {days_before} day(s) in advance." )
            messages.warning( request, "ℹ Admissible advance period is 21 days.")

        elif days_before >= 21:
            messages.warning( request, f"ℹ You are applying '{new_type} Leave' {days_before} day(s) in advance." )

        # 🚫 NO LIMIT, NO DEDUCTION
        unpaid += new_days
        deducted_from = "Unpaid"

    else:
        messages.error(request, "Invalid leave type.")
        return _my_leave_response(request, status=400)

    # ===============================
    # SAVE EVERYTHING ATOMICALLY
    # ===============================
    with transaction.atomic():
        balance.sick_used = max(sick_used, 0)
        balance.earned_used = max(earned_used, 0)
        balance.unpaid = max(unpaid, 0)
        balance.total_leave_remaining = max(total_leaves, 0)
        balance.save()

        leave.leave_type = new_type
        leave.from_date = new_from
        leave.to_date = new_to
        leave.requested_from_date = requested_new_from
        leave.requested_to_date = requested_new_to
        leave.reason = new_reason
        leave.deducted_from = deducted_from
        leave.from_datetime = timezone.make_aware(datetime.combine(new_from, time(10, 0)))
        leave.to_datetime = timezone.make_aware(datetime.combine(new_to, time(19, 0)))
        leave.updated_at = timezone.now()
        leave.no_of_times_updated = (leave.no_of_times_updated or 0) + 1
        refresh_pending_leave_notification(leave)
        leave.save()
        log_leave_action(request.user, "EDIT", leave.id, f"Changes: {old_type} to {new_type}")
        reconcile_user_full_day_leave_bridges(request.user)

        # --- Notify Managers (Updated Request) ---
        hr_emails = get_leave_alert_recipients()
        if hr_emails:
            subject = f"Leave Request UPDATED: {request.user.get_full_name() or request.user.username}"
            portal_link = get_portal_link()
            context = {
                'title': 'Leave Request Updated',
                'intro_text': f"{request.user.get_full_name() or request.user.username} has updated their pending leave request.",
                'employee_name': request.user.get_full_name() or request.user.username,
                'leave_type': new_type,
                'date_range': f"{new_from.strftime('%d %b %Y')} to {new_to.strftime('%d %b %Y')}",
                'reason': new_reason,
                'status_label': 'Updated',
                'status_class': 'updated',
                'portal_link': portal_link
            }
            transaction.on_commit(
                lambda subject=subject, context=context, hr_emails=hr_emails, reply_to=request.user.email, leave=leave, actor=request.user: enqueue_background_task(
                    send_branded_email,
                    subject,
                    'emails/notification.html',
                    context,
                    hr_emails,
                    reply_to=reply_to,
                    from_email=settings.LEAVE_DESK_FROM_EMAIL,
                    email_type="leave_updated",
                    related_user=actor,
                    related_leave=leave,
                    triggered_by=actor,
                    task_name="leave_updated_email",
                )
            )

    messages.success(request, "ℹ Leave updated successfully.")

    queue_hr_leave_push(leave, "Leave updated")

    if(new_type == "Sick" or new_type == "Earned" or new_type == "Unpaid"):
        messages.success(
            request,
            f"Updated leave: {old_type} → {new_type}, "
            f"{old_days} → {new_days} day(s) "
            f"({old_from.strftime('%d %b')} → {old_to.strftime('%d %b')} "
            f"changed to {new_from.strftime('%d %b')} → {new_to.strftime('%d %b')})"
        )

        if breakdown["included_weekend_days"] > 0:
            messages.info(request, f"Sandwich rule applied: {breakdown['included_weekend_days']} weekend day(s) counted as leave.")
        elif breakdown["weekend_days"] > 0:
            messages.info(request, f"Excluded new weekend days: {breakdown['weekend_days']}")

        if breakdown["included_wfh_days"] > 0:
            messages.info(request, f"WFH rule applied: {breakdown['included_wfh_days']} {breakdown['work_from_home_weekday_label']} day(s) were automatically counted as leave.")

        if breakdown["company_holiday_days"] > 0:
            messages.info(request, f"Company holiday day(s) counted in this leave: {breakdown['company_holiday_days']}")

        messages.success(request, f"Working leave days: {breakdown['working_days']}, Full Day (10:00 am to 7:00 pm)")

    return _my_leave_response(request, leave=_serialize_leave_for_my_leave(leave))



@login_required
@never_cache
@require_POST
def logout_view(request):

    # 🔹 Store role before logout
    # 🔹 Detect BEFORE logout
    is_admin = request.user.is_authenticated and request.user.is_superuser
    role = request.user.role if request.user.is_authenticated else None
    logout_name = _get_logout_display_name(request.user, role)
    logout_username = (getattr(request.user, "username", "") or "").strip()

    # 🔥 Logout user
    logout(request)

    # 🔥 Clear full session (extra safety)
    request.session.flush()

    # print("ROLE:", role)
    # print("IS ADMIN:", is_admin)

    print(role, " - Logged out Successfully")

    if is_admin or role == "Admin":
        request.session["admin_login_username"] = logout_username
        request.session["admin_logout_name"] = logout_name
        return redirect("admin_logout_loading_page")

    elif role == "HR":
        request.session["hr_login_username"] = logout_username
        request.session["hr_logout_name"] = logout_name
        return redirect("hr_logout_loading_page")

    elif role == "EMPLOYEE":
        request.session["employee_login_username"] = logout_username
        request.session["employee_logout_name"] = logout_name
        return redirect("employee_logout_loading_page")

    else:
        return redirect("role_select")


@login_required
@never_cache
def get_next_id_api(request, role):
    """
    AJAX endpoint for getting the next available Employee ID for a given role.
    Used in the Django Admin for dynamic pre-filling.
    """
    if not request.user.is_staff:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    normalized_role = (role or "").strip()
    if normalized_role not in ALLOWED_PROFILE_ID_ROLES:
        security_logger.warning(
            "INVALID_NEXT_ID_ROLE | user_id=%s | ip=%s | submitted=%s",
            request.user.id,
            _get_client_ip(request),
            normalized_role[:80],
        )
        return JsonResponse({"error": "Invalid role."}, status=400)

    next_id = Profile.generate_next_id(normalized_role)
    return JsonResponse({"next_id": next_id})
