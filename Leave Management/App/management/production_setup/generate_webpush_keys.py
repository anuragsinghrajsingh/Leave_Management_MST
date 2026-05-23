import base64
import sys
from pathlib import Path


CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from _env_utils import ask_yes_no, ensure_runtime_dir, print_header, write_many_env_values


PRIVATE_KEY_NAME = "webpush_private_key.pem"
PUBLIC_KEY_NAME = "webpush_public_key.pem"


def _base64url_no_padding(value):
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _public_application_server_key(public_key):
    numbers = public_key.public_numbers()
    x = numbers.x.to_bytes(32, "big")
    y = numbers.y.to_bytes(32, "big")
    return _base64url_no_padding(b"\x04" + x + y)


def generate_vapid_key_pair():
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()

    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    app_server_key = _public_application_server_key(public_key)
    return private_pem, public_pem, app_server_key


def run(update_direct=None):
    print_header("Web Push VAPID Keys")

    runtime_dir = ensure_runtime_dir()
    private_key_path = runtime_dir / PRIVATE_KEY_NAME
    public_key_path = runtime_dir / PUBLIC_KEY_NAME

    overwrite_files = True
    if private_key_path.exists() or public_key_path.exists():
        overwrite_files = ask_yes_no("Web push key files already exist. Overwrite?")

    if overwrite_files:
        private_pem, public_pem, app_server_key = generate_vapid_key_pair()
        private_key_path.write_bytes(private_pem)
        public_key_path.write_bytes(public_pem)
        print(f"Wrote {private_key_path}")
        print(f"Wrote {public_key_path}")
    else:
        print("Kept existing web push key files.")
        print("Run again and choose overwrite if you need a new production pair.")
        app_server_key = input("Enter existing WEB_PUSH_VAPID_PUBLIC_KEY to write/print env values: ").strip()
        if not app_server_key:
            print("No public key entered. Skipping env values.")
            return {}

    values = {
        "WEB_PUSH_VAPID_PUBLIC_KEY": app_server_key,
        "WEB_PUSH_VAPID_PRIVATE_KEY": f"runtime/{PRIVATE_KEY_NAME}",
        "WEB_PUSH_VAPID_SUBJECT": "mailto:admin@yourdomain.com",
    }

    if update_direct is None:
        update_direct = ask_yes_no("Do you want to update .env directly?")

    write_many_env_values(values, update_direct=update_direct)
    return values


if __name__ == "__main__":
    run()
