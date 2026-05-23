import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from _env_utils import ask_yes_no, print_header
from generate_database_password import run as run_database_password
from generate_django_secret_key import run as run_django_secret_key
from generate_webpush_keys import run as run_webpush_keys


def print_production_reminders():
    print_header("Production Reminders")
    print("These values must still be reviewed manually in production .env:")
    print("DJANGO_DEBUG=False")
    print("DJANGO_ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com")
    print("DJANGO_CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com")
    print("PORTAL_BASE_URL=https://yourdomain.com")
    print("DJANGO_SECURE_SSL_REDIRECT=True")
    print("DB_ENGINE=postgresql")
    print("DB_NAME=leave_management")
    print("DB_USER=leave_user")
    print("DB_HOST=localhost")
    print("DB_PORT=5432")
    print("EMAIL_HOST_PASSWORD=your-production-email-password")
    print("ADMIN_EMAIL=admin@yourdomain.com")
    print("\nDo not share .env or runtime/webpush_private_key.pem.")


def run():
    print_header("Production Secret Generator")
    update_direct = ask_yes_no("Do you want to update .env directly for generated values?")

    generated = {}
    generated.update(run_django_secret_key(update_direct=update_direct))
    generated.update(run_database_password(update_direct=update_direct))
    generated.update(run_webpush_keys(update_direct=update_direct))

    print_header("Generated Values Summary")
    for key, value in generated.items():
        print(f"{key}={value}")

    print_production_reminders()
    return generated


if __name__ == "__main__":
    run()
