import uuid
import time
import logging
import threading
from urllib.parse import urlparse
from django.contrib import messages
from django.contrib.auth import SESSION_KEY, get_user_model
from django.utils.timezone import now
from django.urls import resolve
from django.shortcuts import redirect, render
from django.http import JsonResponse

from App.services.maintenance_mode import is_maintenance_mode_enabled

# Thread-local storage for request IDs
_thread_locals = threading.local()

class SuppressNoiseFilter(logging.Filter):
    """
    Filters out high-frequency polling API calls to keep logs clean.
    """
    def filter(self, record):
        noise_paths = [
            '/api/hr-notifications/', 
            '/api/employee-notifications/',
            '/api/notifications/seen/',
            '/api/notifications/read/',
            '/api/communications/seen/',
            '/api/communications/read/'
        ]
        msg = record.getMessage()
        return not any(path in msg for path in noise_paths)

class CorrelationIDFilter(logging.Filter):
    """
    Filter that injects the current request's Correlation ID into the log record.
    """
    def filter(self, record):
        record.request_id = getattr(_thread_locals, 'request_id', 'N/A')
        return True

class CorrelationMiddleware:
    """
    Middleware that generates a unique Correlation ID for every request.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate or retrieve a request ID
        request_id = str(uuid.uuid4())[:8].upper()
        _thread_locals.request_id = f"LMS-{request_id}"
        request.request_id = _thread_locals.request_id
        
        response = self.get_response(request)

        # 403 Forbidden Security Listener
        if response.status_code == 403:
            import logging
            logger = logging.getLogger('lms_security')
            username = request.user.username if request.user.is_authenticated else "Anonymous"
            logger.info(
                f"UNAUTHORIZED_ACCESS_ATTEMPT | User: {username} | "
                f"Path: {request.path} | Method: {request.method}"
            )
        
        # Cleanup after request
        if hasattr(_thread_locals, 'request_id'):
            del _thread_locals.request_id

        return response


class MaintenanceModeMiddleware:
    """
    Blocks normal app traffic while a controlled database restore is in progress.
    """
    allowed_prefixes = (
        "/admin/",
        "/admin-login/",
        "/admin-logout/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not is_maintenance_mode_enabled():
            return self.get_response(request)

        if request.path.startswith(self.allowed_prefixes):
            return self.get_response(request)

        if getattr(request, "user", None) and request.user.is_authenticated and request.user.is_superuser:
            return self.get_response(request)

        return render(request, "maintenance.html", status=503)


class ForcedPasswordChangeMiddleware:
    """
    Keeps HR/Employee users inside the forced password-change flow until complete.
    """
    allowed_prefixes = (
        "/force-password-change/",
        "/logout/",
        "/logout/loading/",
        "/hr-logout/",
        "/hr-logout/loading/",
        "/employee-logout/loading/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return self.get_response(request)

        if getattr(user, "role", None) not in {"EMPLOYEE", "HR"} or not getattr(user, "must_change_password", False):
            return self.get_response(request)

        if request.path.startswith(self.allowed_prefixes):
            return self.get_response(request)

        return redirect("force_password_change")


class RoleAwareLoginRedirectMiddleware:
    """
    Sends expired/anonymous sessions to the login page that matches the protected area.
    """
    employee_prefixes = (
        "/dashboard/",
        "/apply_leave/",
        "/my_leave/",
        "/profile/",
        "/leave-calendar-data/",
        "/delete-leave/",
        "/edit-leave/",
        "/apply-status-filter/",
        "/clear-status-filter/",
        "/clear-status-filter-field/",
        "/api/employee-notifications/",
    )
    hr_prefixes = (
        "/hr-dashboard/",
        "/manage-all/",
        "/employees/",
        "/reports/",
        "/approve-leave/",
        "/reject-leave/",
        "/edit-employee/",
        "/api/hr-notifications/",
        "/api/manage-all/",
    )
    admin_prefixes = (
        "/admin-dashboard/",
        "/admin-login/dashboard-loading/",
        "/admin-login/workspace/",
    )
    shared_api_prefixes = (
        "/api/communications/",
        "/api/notifications/read/",
        "/api/notifications/seen/",
    )

    public_prefixes = (
        "/",
        "/portal/",
        "/admin-login/",
        "/hr-login/",
        "/employee-login/",
        "/logout/",
        "/admin-logout/",
        "/hr-logout/",
        "/employee-logout/",
        "/force-password-change/",
        "/static/",
        "/media/",
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        expired_user_id = request.session.get(SESSION_KEY)
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            return self.get_response(request)

        redirect_url = self._get_login_url_for_request(request)
        if not redirect_url:
            return self.get_response(request)

        username = self._store_login_prefill_username(request, redirect_url, expired_user_id)
        session_message = self._get_session_expired_message(username)

        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return JsonResponse({
                "success": False,
                "sessionExpired": True,
                "redirectUrl": redirect_url,
                "messages": [{
                    "title": "Logged out for security",
                    "text": session_message,
                    "tags": "warning",
                }],
            }, status=401)

        if expired_user_id:
            messages.warning(request, session_message)

        return redirect(redirect_url)

    def _get_login_url_for_request(self, request):
        path = request.path
        if path == "/":
            return None
        if any(path.startswith(prefix) for prefix in self.shared_api_prefixes):
            referer_path = urlparse(request.META.get("HTTP_REFERER", "")).path
            return self._get_login_url_for_path(referer_path) if referer_path else None
        return self._get_login_url_for_path(path)

    def _get_login_url_for_path(self, path):
        if not path or path == "/":
            return None
        if any(path.startswith(prefix) for prefix in self.employee_prefixes):
            return "/employee-login/form/"
        if any(path.startswith(prefix) for prefix in self.hr_prefixes):
            return "/hr-login/form/"
        if path.startswith("/admin/") or any(path.startswith(prefix) for prefix in self.admin_prefixes):
            return "/admin-login/form/"
        if any(path.startswith(prefix) for prefix in self.public_prefixes if prefix != "/"):
            return None
        return None

    def _store_login_prefill_username(self, request, redirect_url, expired_user_id):
        if not expired_user_id:
            return ""

        session_key = {
            "/employee-login/form/": "employee_login_username",
            "/hr-login/form/": "hr_login_username",
            "/admin-login/form/": "admin_login_username",
        }.get(redirect_url)

        if not session_key:
            return ""

        try:
            username = get_user_model().objects.only("username").get(pk=expired_user_id).username
        except Exception:
            return ""

        request.session[session_key] = username
        return username

    def _get_session_expired_message(self, username):
        prefix = f"{username}, your" if username else "Your"
        return (
            f"{prefix} session ended because your password was changed by an administrator. "
            "Please log in again with the updated password."
        )


class APILoggingMiddleware:
    """
    Middleware that logs all /api/ requests to the specialized lms_api logger.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('lms_api')

    def __call__(self, request):
        response = self.get_response(request)

        # Log only /api/ paths to the dedicated API log
        if request.path.startswith('/api/'):
            status_code = response.status_code
            user = request.user if request.user.is_authenticated else "Anonymous"
            self.logger.info(f"API | {request.method} {request.path} | Status: {status_code} | User: {user}")

        return response

class UserAnalyticsMiddleware:
    """
    Middleware to track page transitions and time spent on each page.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.logger = logging.getLogger('lms_analytics')

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        # 1. Track entry
        start_time = time.time()
        current_path = request.path
        
        # 2. Check previous session data
        prev_path = request.session.get('last_path')
        prev_time = request.session.get('last_time')

        if prev_path and prev_time:
            time_spent = round(start_time - prev_time, 2)
            # Log the transition and time spent on the PREVIOUS page
            self.logger.info(
                f"User: {request.user.username} | Role: {getattr(request.user, 'role', 'N/A')} | "
                f"Exit Page: {prev_path} | Time Spent: {time_spent}s | Navigating To: {current_path}"
            )

        # 3. Update session for next request
        request.session['last_path'] = current_path
        request.session['last_time'] = start_time

        response = self.get_response(request)
        return response
