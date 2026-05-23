import secrets
import string
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from _env_utils import ask_yes_no, print_header, write_env_value


def generate_secret_key():
    try:
        from django.core.management.utils import get_random_secret_key

        return get_random_secret_key()
    except Exception:
        chars = string.ascii_letters + string.digits + string.punctuation
        return "".join(secrets.choice(chars) for _ in range(64))


def run(update_direct=None):
    print_header("Django Secret Key")
    secret_key = generate_secret_key()

    if update_direct is None:
        update_direct = ask_yes_no("Do you want to update .env directly?")

    write_env_value("DJANGO_SECRET_KEY", secret_key, update_direct=update_direct)
    return {"DJANGO_SECRET_KEY": secret_key}


if __name__ == "__main__":
    run()
