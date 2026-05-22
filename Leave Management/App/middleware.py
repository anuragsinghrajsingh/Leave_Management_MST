import uuid
import time
import logging
import threading
from django.utils.timezone import now
from django.urls import resolve
from django.shortcuts import redirect, render

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
