import os
import logging
import subprocess
import sys
from pathlib import Path


def _setup_django():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


if __name__ == "__main__":
    _setup_django()

from django.conf import settings
from App.services.maintenance_mode import is_maintenance_mode_enabled

logger = logging.getLogger("lms_service_restore_db")


def confirm_restore():
    phrase = "RESTORE_DATABASE" if settings.DEBUG else "PRODUCTION_RESTORE_DATABASE"
    if not settings.DEBUG:
        print("PRODUCTION MODE DETECTED.")
    if not is_maintenance_mode_enabled():
        logger.warning("RESTORE_DB | BLOCKED | Maintenance mode is OFF.")
        print("[ERROR] Enable maintenance mode before restoring a database backup.")
        return False
    print("This can overwrite the current database after you select a backup.")
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = input(f"Type {phrase} to continue: ").strip()
    if confirmation != phrase:
        logger.info("RESTORE_DB | CANCELLED | Initial restore confirmation declined.")
        print("[INFO] Restore cancelled.")
        return False
    logger.info("RESTORE_DB | CONFIRMED | Initial restore confirmation accepted.")
    return True


def main():
    """
    Emergency Database Restore Wrapper.
    Launches the full interactive restore utility from manage_backups.py.
    """
    logger.info("RESTORE_DB | MANUAL_RUN | Opened direct runner.")
    print("="*40)
    print("   LMS EMERGENCY DATABASE RESTORE")
    print("="*40)
    
    # Identify the correct python executable
    python_exe = sys.executable
    
    # Path to the main backup script (it is 2 levels up from services/)
    backup_script = Path(__file__).resolve().parent.parent.parent / "manage_backups.py"
    
    if not backup_script.exists():
        logger.error("RESTORE_DB | BLOCKED | Backup script not found | Path=%s", backup_script)
        print(f"[ERROR] Could not find {backup_script.name} in the current directory.")
        return

    if not confirm_restore():
        return

    try:
        # Run the restore command
        logger.info("RESTORE_DB | DELEGATE | Launching manage_backups restore | Script=%s", backup_script)
        subprocess.run([python_exe, str(backup_script), "--restore"], check=True)
        logger.info("RESTORE_DB | SUCCESS | manage_backups restore process completed.")
    except KeyboardInterrupt:
        logger.warning("RESTORE_DB | INTERRUPTED | Restore process interrupted by user.")
        print("\n\n[INFO] Restore process interrupted by user.")
    except subprocess.CalledProcessError:
        logger.error("RESTORE_DB | FAILED | manage_backups restore returned a non-zero exit code.")
        print("\n[ERROR] The restore process encountered an error.")
    except Exception as e:
        logger.error("RESTORE_DB | FAILED | Unexpected error: %s", e)
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
