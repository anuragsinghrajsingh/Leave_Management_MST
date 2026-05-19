import argparse
import logging
import os
import sys
from pathlib import Path


def _setup_django():
    project_root = Path(__file__).resolve().parent.parent.parent
    if str(project_root) not in sys.path:
        sys.path.append(str(project_root))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")
    import django

    django.setup()


if __name__ == "__main__":
    _setup_django()

from django.conf import settings


MAINTENANCE_MODE_FLAG = Path(settings.BASE_DIR) / ".maintenance_mode"
maintenance_logger = logging.getLogger("lms_maintenance")


def is_maintenance_mode_enabled():
    return MAINTENANCE_MODE_FLAG.exists()


def enable_maintenance_mode():
    MAINTENANCE_MODE_FLAG.write_text("enabled\n", encoding="utf-8")
    maintenance_logger.info("MAINTENANCE | STATE | Flag file created at %s", MAINTENANCE_MODE_FLAG)


def disable_maintenance_mode():
    if MAINTENANCE_MODE_FLAG.exists():
        MAINTENANCE_MODE_FLAG.unlink()
        maintenance_logger.info("MAINTENANCE | STATE | Flag file removed from %s", MAINTENANCE_MODE_FLAG)
    else:
        maintenance_logger.info("MAINTENANCE | STATE | Disable requested but flag was already absent.")


def _confirmation_phrase(action):
    action_text = action.upper()
    if settings.DEBUG:
        return f"{action_text}_MAINTENANCE"
    return f"PRODUCTION_{action_text}_MAINTENANCE"


def confirm_maintenance_action(action):
    phrase = _confirmation_phrase(action)
    if not settings.DEBUG:
        print("PRODUCTION MODE DETECTED.")
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = input(f"Type {phrase} to {action} maintenance mode: ").strip()
    if confirmation != phrase:
        maintenance_logger.info("MAINTENANCE | CONFIRMATION | %s cancelled by terminal confirmation.", action.upper())
        print(f"{action.title()} cancelled.")
        return False
    maintenance_logger.info("MAINTENANCE | CONFIRMATION | %s accepted by terminal confirmation.", action.upper())
    return True


def main():
    maintenance_logger.info("MAINTENANCE | MANUAL_RUN | Opened direct runner.")
    parser = argparse.ArgumentParser(description="Control Leave Management maintenance mode.")
    parser.add_argument("action", nargs="?", choices=["status", "enable", "disable"], help="Maintenance mode action.")
    args = parser.parse_args()

    if not args.action:
        run_interactive_menu()
        return

    if args.action == "status":
        maintenance_logger.info("MAINTENANCE | STATUS | Checked by terminal | Enabled=%s", is_maintenance_mode_enabled())
        print("enabled" if is_maintenance_mode_enabled() else "disabled")
        return

    if args.action == "enable":
        if not confirm_maintenance_action("enable"):
            return
        enable_maintenance_mode()
        maintenance_logger.info("MAINTENANCE | ENABLED | By: terminal | Reason: direct CLI action")
        print("Maintenance mode enabled.")
        return

    if not confirm_maintenance_action("disable"):
        return
    disable_maintenance_mode()
    maintenance_logger.info("MAINTENANCE | DISABLED | By: terminal | Reason: direct CLI action")
    print("Maintenance mode disabled.")


def run_interactive_menu():
    maintenance_logger.info("MAINTENANCE | MENU | Interactive menu opened.")
    while True:
        status = "ENABLED" if is_maintenance_mode_enabled() else "DISABLED"
        print("\n--- MAINTENANCE MODE CONTROL ---")
        print(f"Current status: {status}")
        print("\n[1] Enable maintenance mode")
        print("[2] Disable maintenance mode")
        print("[3] Show status")
        print("[0] Exit")

        choice = input("\nChoose an option: ").strip()

        if choice == "1":
            if is_maintenance_mode_enabled():
                maintenance_logger.info("MAINTENANCE | MENU | Enable selected but already enabled.")
                print("Maintenance mode is already enabled.")
                continue

            if not confirm_maintenance_action("enable"):
                continue

            enable_maintenance_mode()
            maintenance_logger.info("MAINTENANCE | ENABLED | By: terminal | Reason: interactive CLI action")
            print("Maintenance mode enabled.")
            continue

        if choice == "2":
            if not is_maintenance_mode_enabled():
                maintenance_logger.info("MAINTENANCE | MENU | Disable selected but already disabled.")
                print("Maintenance mode is already disabled.")
                continue

            if not confirm_maintenance_action("disable"):
                continue

            disable_maintenance_mode()
            maintenance_logger.info("MAINTENANCE | DISABLED | By: terminal | Reason: interactive CLI action")
            print("Maintenance mode disabled.")
            continue

        if choice == "3":
            maintenance_logger.info("MAINTENANCE | STATUS | Checked from interactive menu | Enabled=%s", is_maintenance_mode_enabled())
            print(f"Maintenance mode is {status}.")
            continue

        if choice == "0":
            maintenance_logger.info("MAINTENANCE | MENU | Exit selected.")
            print("Exiting maintenance mode control.")
            return

        maintenance_logger.warning("MAINTENANCE | MENU | Invalid option selected | Value=%s", choice)
        print("Invalid option.")


if __name__ == "__main__":
    main()
