import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils.timezone import localtime, now

from App.models import AdminEmailJob, AdminEmailJobItem
from App.services.background_tasks import enqueue_background_task
from App.services.email_delivery_log import record_email_delivery
from App.services.employee_welcome_service import send_employee_welcome_package
from App.services.forced_password_service import send_forced_password_email


logger = logging.getLogger("lms_background")


def create_admin_email_job(*, job_type, user_ids, created_by, subject="", message="", reason="", metadata=None, item_metadata_by_user_id=None):
    user_ids = list(dict.fromkeys(user_ids))
    users = list(
        get_user_model()
        .objects.filter(id__in=user_ids)
        .order_by("username", "id")
    )
    user_by_id = {user.id: user for user in users}

    with transaction.atomic():
        job = AdminEmailJob.objects.create(
            job_type=job_type,
            subject=subject or "",
            message=message or "",
            reason=reason or "",
            total_count=len(user_ids),
            queued_count=len(user_ids),
            created_by=created_by if getattr(created_by, "is_authenticated", False) else None,
            metadata=metadata or {},
        )
        items = []
        item_metadata_by_user_id = item_metadata_by_user_id or {}
        for user_id in user_ids:
            user = user_by_id.get(user_id)
            item_metadata = {"user_id": user_id}
            item_metadata.update(item_metadata_by_user_id.get(user_id, {}))
            items.append(
                AdminEmailJobItem(
                    job=job,
                    user=user,
                    recipient_email=getattr(user, "email", "") or "",
                    status="queued",
                    status_message="Queued for sending.",
                    metadata=item_metadata,
                )
            )
        AdminEmailJobItem.objects.bulk_create(items)
        job.refresh_counts()

    enqueue_background_task(process_admin_email_job, job.id, task_name=f"admin_email_job_{job_type}")
    return job


def process_admin_email_job(job_id):
    job = AdminEmailJob.objects.select_related("created_by").filter(id=job_id).first()
    if not job:
        return False

    if job.status not in {"queued", "running"}:
        return True

    job.status = "running"
    job.started_at = job.started_at or now()
    job.save(update_fields=["status", "started_at"])
    job.refresh_counts()

    try:
        for item in job.items.select_related("user").order_by("id"):
            if item.status != "queued":
                continue
            _process_job_item(job, item)
            job.refresh_counts()
    except Exception:
        logger.exception("ADMIN_EMAIL_JOB_FAILED | job_id=%s", job_id)
        job.status = "failed"
        job.finished_at = now()
        job.save(update_fields=["status", "finished_at"])
        return False

    job.refresh_counts(save=False)
    if job.failed_count:
        job.status = "completed_with_failures"
    else:
        job.status = "completed"
    job.finished_at = now()
    job.save(update_fields=[
        "total_count",
        "queued_count",
        "running_count",
        "sent_count",
        "failed_count",
        "skipped_count",
        "status",
        "finished_at",
    ])
    return True


def _process_job_item(job, item):
    item.status = "running"
    item.started_at = now()
    item.status_message = "Sending."
    item.save(update_fields=["status", "started_at", "status_message"])

    user = item.user
    if not user:
        _finish_item(item, "skipped", "User no longer exists.")
        return

    if job.job_type == "onboarding":
        _send_onboarding_item(job, item, user)
    elif job.job_type == "force_password":
        _send_force_password_item(job, item, user)
    elif job.job_type == "reminder":
        _send_reminder_item(job, item, user)
    elif job.job_type == "login_lock":
        _send_login_lock_item(job, item, user)
    elif job.job_type == "login_unlock":
        _send_login_unlock_item(job, item, user)
    else:
        _finish_item(item, "failed", "Unsupported job type.", error_message=job.job_type)


def _send_onboarding_item(job, item, user):
    result = send_employee_welcome_package(user, triggered_by=job.created_by, force_resend=True)
    if result.get("email_sent"):
        _finish_item(item, "sent", "Welcome email sent.")
    elif result.get("sent"):
        message = result.get("email_error") or "Welcome communication created, but email was not sent."
        status = "skipped" if not getattr(user, "email", "") else "failed"
        _finish_item(item, status, message, error_message="" if status == "skipped" else message)
    else:
        _finish_item(item, "skipped", result.get("reason") or "Skipped.")


def _send_force_password_item(job, item, user):
    if not getattr(user, "email", ""):
        _finish_item(item, "skipped", "No email address.")
        return

    event = (job.metadata or {}).get("event") or "forced"
    if send_forced_password_email(user, event, triggered_by=job.created_by):
        _finish_item(item, "sent", "Force password email sent.")
    else:
        _finish_item(item, "failed", "Force password email failed.", error_message="Send function returned false.")


def _send_reminder_item(job, item, user):
    if not getattr(user, "email", ""):
        _finish_item(item, "skipped", "No email address.")
        return

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    try:
        email = EmailMessage(
            subject=job.subject,
            body=job.message,
            from_email=from_email or None,
            to=[user.email],
        )
        email.send(fail_silently=False)
        record_email_delivery(
            subject=job.subject,
            recipients=[user.email],
            status="sent",
            email_type="admin_bulk_reminder",
            from_email=from_email,
            related_user=user,
            triggered_by=job.created_by,
        )
        _finish_item(item, "sent", "Reminder email sent.")
    except Exception as exc:
        logger.exception("ADMIN_REMINDER_EMAIL_FAILED | user_id=%s | job_id=%s", user.pk, job.pk)
        record_email_delivery(
            subject=job.subject,
            recipients=[user.email],
            status="failed",
            email_type="admin_bulk_reminder",
            from_email=from_email,
            error_message=str(exc),
            related_user=user,
            triggered_by=job.created_by,
        )
        _finish_item(item, "failed", "Reminder email failed.", error_message=str(exc))


def _send_login_lock_item(job, item, user):
    if not getattr(user, "email", ""):
        _finish_item(item, "skipped", "No email address.")
        return

    metadata = item.metadata or {}
    actor_name = _actor_name(job.created_by)
    subject = "Your portal login has been locked"
    body = (
        "Login locked by administrator\n\n"
        f"Hello {_display_name(user)},\n\n"
        "Your portal login has been locked by an administrator.\n\n"
        f"Portal: {metadata.get('portal') or getattr(user, 'role', 'Portal')}\n"
        f"Locked by: {actor_name}\n"
        f"Lock duration: {metadata.get('duration_text') or '-'}\n"
        f"You can retry after: {metadata.get('expires_at') or '-'}\n"
        f"Reason: {job.reason or '-'}\n\n"
        "If you believe this is a mistake, contact HR/Admin."
    )
    _send_plain_job_email(job, item, user, subject, body, "admin_login_lock", "Login lock email sent.", "Login lock email failed.")


def _send_login_unlock_item(job, item, user):
    if not getattr(user, "email", ""):
        _finish_item(item, "skipped", "No email address.")
        return

    metadata = item.metadata or {}
    actor_name = _actor_name(job.created_by)
    subject = "Your portal login has been unlocked"
    body = (
        "Login unlocked by administrator\n\n"
        f"Hello {_display_name(user)},\n\n"
        "Your portal login has been unlocked by an administrator.\n\n"
        f"Portal: {metadata.get('portal') or getattr(user, 'role', 'Portal')}\n"
        f"Unlocked by: {actor_name}\n"
        f"Time: {metadata.get('unlocked_at') or localtime(now()).strftime('%d/%m/%Y, %I:%M %p')}\n"
        f"Reason: {job.reason or '-'}\n\n"
        "You can now try logging in again."
    )
    _send_plain_job_email(job, item, user, subject, body, "admin_login_unlock", "Login unlock email sent.", "Login unlock email failed.")


def _send_plain_job_email(job, item, user, subject, body, email_type, success_message, failure_message):
    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "") or getattr(settings, "EMAIL_HOST_USER", "")
    try:
        EmailMessage(
            subject=subject,
            body=body,
            from_email=from_email or None,
            to=[user.email],
        ).send(fail_silently=False)
        record_email_delivery(
            subject=subject,
            recipients=[user.email],
            status="sent",
            email_type=email_type,
            from_email=from_email,
            related_user=user,
            triggered_by=job.created_by,
            metadata={"job_id": job.pk, **(item.metadata or {})},
        )
        _finish_item(item, "sent", success_message)
    except Exception as exc:
        logger.exception("%s | user_id=%s | job_id=%s", email_type.upper(), user.pk, job.pk)
        record_email_delivery(
            subject=subject,
            recipients=[user.email],
            status="failed",
            email_type=email_type,
            from_email=from_email,
            error_message=str(exc),
            related_user=user,
            triggered_by=job.created_by,
            metadata={"job_id": job.pk, **(item.metadata or {})},
        )
        _finish_item(item, "failed", failure_message, error_message=str(exc))


def _display_name(user):
    return user.get_full_name().strip() or user.username


def _actor_name(user):
    if not user:
        return "Administrator"
    return user.get_full_name().strip() or user.username


def _finish_item(item, status, message, *, error_message=""):
    item.status = status
    item.status_message = message or ""
    item.error_message = error_message or ""
    item.finished_at = now()
    item.save(update_fields=["status", "status_message", "error_message", "finished_at"])
