from django.conf import settings
from django.core.exceptions import ValidationError


def get_password_input_max_length():
    return int(getattr(settings, "PASSWORD_INPUT_MAX_LENGTH", 128) or 128)


def validate_password_input_max_length(password):
    max_length = get_password_input_max_length()
    if password and len(password) > max_length:
        raise ValidationError(f"Password must be {max_length} characters or fewer.")


class MaximumLengthPasswordValidator:
    def __init__(self, max_length=None):
        self.max_length = max_length

    def validate(self, password, user=None):
        max_length = self.max_length or get_password_input_max_length()
        if password and len(password) > max_length:
            raise ValidationError(
                f"Password must be {max_length} characters or fewer.",
                code="password_too_long",
            )

    def get_help_text(self):
        max_length = self.max_length or get_password_input_max_length()
        return f"Your password must be {max_length} characters or fewer."
