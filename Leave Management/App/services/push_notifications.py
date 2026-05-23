import json
import logging

from django.conf import settings
from django.utils.timezone import now

from App.models import PushSubscription


logger = logging.getLogger("lms_push")


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
