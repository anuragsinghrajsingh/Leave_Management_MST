import logging

def get_role(user):
    """
    Safely retrieves the role of a user, defaulting to 'Employee' if undefined.
    """
    if not user or user.is_anonymous:
        return 'Employee'
    
    if hasattr(user, 'role') and user.role:
        return user.role
    
    if user.is_superuser:
        return 'Admin'
        
    return 'Employee'

def get_logger_for_role(base_name, user):
    """
    Returns a logger instance specifically for the user's role.
    Example: lms_auth_hr
    """
    role = get_role(user).lower()
    if role not in ['employee', 'hr', 'admin']:
        role = 'employee'
    
    logger_name = f"{base_name}_{role}"
    return logging.getLogger(logger_name)

def log_auth_action(user, action, details=""):
    """
    Logs login, logout, and failed attempts.
    """
    logger = get_logger_for_role('lms_auth', user)
    username = user.username if user and not user.is_anonymous else "Anonymous"
    logger.info(f"AUTH | User: {username} | Action: {action} | Details: {details}")

def log_leave_action(user, action, leave_id=None, details=""):
    """
    Logs apply, edit, delete, approve, reject.
    """
    logger = get_logger_for_role('lms_leave', user)
    msg = f"LEAVE | User: {user.username} | Action: {action}"
    if leave_id:
        msg += f" | LeaveID: {leave_id}"
    if details:
        msg += f" | Details: {details}"
    logger.info(msg)

def log_profile_update(user, updated_by, field_name, old_val, new_val):
    """
    Logs profile changes with before/after state.
    """
    logger = logging.getLogger('lms_profile')
    logger.info(
        f"PROFILE | Target: {user.username} | Field: {field_name} | "
        f"Old: {old_val} | New: {new_val} | UpdatedBy: {updated_by.username}"
    )

def log_email_sent(recipient_user, subject, success=True, details=""):
    """
    Logs email communication status.
    """
    logger = get_logger_for_role('lms_email', recipient_user)
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        f"EMAIL | To: {recipient_user.username} | Status: {status} | "
        f"Subject: {subject} | Details: {details}"
    )

def log_email_sent_by_email(email_address, subject, success=True, details=""):
    """
    Logs email communication when only the email address is available.
    Attempts to find the user to determine the role.
    """
    from django.contrib.auth import get_user_model
    User = get_user_model()
    user = User.objects.filter(email=email_address).first()
    
    logger = get_logger_for_role('lms_email', user)
    status = "SUCCESS" if success else "FAILED"
    logger.info(
        f"EMAIL | To: {email_address} | Status: {status} | "
        f"Subject: {subject} | Details: {details}"
    )
