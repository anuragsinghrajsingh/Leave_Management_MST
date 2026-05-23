import secrets
import string
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from _env_utils import ask_yes_no, print_header, write_env_value


def generate_database_password(length=32):
    alphabet = string.ascii_letters + string.digits + "_-"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def run(update_direct=None):
    print_header("Database Password")
    password = generate_database_password()

    if update_direct is None:
        update_direct = ask_yes_no("Do you want to update .env directly?")

    write_env_value("DB_PASSWORD", password, update_direct=update_direct)
    return {"DB_PASSWORD": password}


if __name__ == "__main__":
    run()
