from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from App.utils.logger_utils import log_auth_action

@receiver(user_logged_in)
def on_user_login(sender, request, user, **kwargs):
    log_auth_action(user, "LOGIN", f"IP: {request.META.get('REMOTE_ADDR')}")

@receiver(user_logged_out)
def on_user_logout(sender, request, user, **kwargs):
    if user:
        log_auth_action(user, "LOGOUT")

@receiver(user_login_failed)
def on_user_login_failed(sender, credentials, request, **kwargs):
    # Log the raw credentials as per user request (NO MASKING)
    details = f"Credentials Attempted: {credentials} | IP: {request.META.get('REMOTE_ADDR')}"
    log_auth_action(None, "FAILED_LOGIN", details)
