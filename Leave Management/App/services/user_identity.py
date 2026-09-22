import re

def normalize_login_identifier(value):
    return re.sub(r"\s+", "", (value or "").strip()).casefold()


def normalize_username_value(value):
    return normalize_login_identifier(value)


def normalize_email_value(value):
    return normalize_login_identifier(value)


def get_user_by_login_identifier(portal, identifier, *, active_only=True):
    identifier = normalize_login_identifier(identifier)
    if not identifier:
        return None

    from django.contrib.auth import get_user_model
    from django.db.models import Q

    User = get_user_model()
    queryset = User.objects.filter( Q(username__iexact=identifier) | Q(email__iexact=identifier))

    if active_only:
        queryset = queryset.filter(is_active=True)

    if portal == "ADMIN":
        queryset = queryset.filter(is_superuser=True)
    elif portal == "HR":
        queryset = queryset.filter(role="HR")
    elif portal == "EMPLOYEE":
        queryset = queryset.filter(role="EMPLOYEE")

    return queryset.first()


def get_canonical_login_username(portal, identifier):
    identifier = normalize_login_identifier(identifier)
    if not identifier:
        return ""

    user = get_user_by_login_identifier(portal, identifier)
    return user.username if user else identifier


class UsernameOrEmailBackend:
    def authenticate(self, request, username=None, password=None, **kwargs):
        identifier = normalize_login_identifier(username or kwargs.get("username"))
        if not identifier or password is None:
            return None

        from django.contrib.auth import get_user_model

        User = get_user_model()
        lookup = {"email__iexact": identifier} if "@" in identifier else {"username__iexact": identifier}

        try:
            user = User.objects.get(**lookup)
        except (User.DoesNotExist, User.MultipleObjectsReturned):
            return None

        if user.check_password(password) and self.user_can_authenticate(user):
            return user

        return None

    def get_user(self, user_id):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User._default_manager.get(pk=user_id)
        except User.DoesNotExist:
            return None

        return user if self.user_can_authenticate(user) else None

    def user_can_authenticate(self, user):
        is_active = getattr(user, "is_active", None)
        return is_active or is_active is None