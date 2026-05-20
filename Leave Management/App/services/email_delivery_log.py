import logging

from App.models import EmailDeliveryLog


logger = logging.getLogger("lms_email")


def normalize_recipients(recipients):
    if not recipients:
        return []
    if isinstance(recipients, str):
        return [recipients]
    return [recipient for recipient in recipients if recipient]


def record_email_delivery(
    *,
    subject,
    recipients,
    status,
    email_type="general",
    from_email="",
    error_message="",
    related_user=None,
    related_leave=None,
    triggered_by=None,
    metadata=None,
):
    rows = []
    metadata = metadata or {}
    for recipient in normalize_recipients(recipients):
        rows.append(
            EmailDeliveryLog(
                email_type=email_type[:80],
                subject=(subject or "")[:255],
                from_email=(from_email or "")[:255],
                recipient=recipient,
                status=status,
                error_message=error_message or "",
                related_user=related_user,
                related_leave=related_leave,
                triggered_by=triggered_by,
                metadata=metadata,
            )
        )

    if not rows:
        return 0

    try:
        EmailDeliveryLog.objects.bulk_create(rows)
        return len(rows)
    except Exception:
        logger.exception("EMAIL_DELIVERY_LOG_WRITE_FAILED | subject=%s | status=%s", subject, status)
        return 0
