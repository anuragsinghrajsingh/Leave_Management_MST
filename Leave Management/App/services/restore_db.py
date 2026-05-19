import os
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


def confirm_restore():
    phrase = "RESTORE_DATABASE" if settings.DEBUG else "PRODUCTION_RESTORE_DATABASE"
    if not settings.DEBUG:
        print("PRODUCTION MODE DETECTED.")
    if not is_maintenance_mode_enabled():
        print("[ERROR] Enable maintenance mode before restoring a database backup.")
        return False
    print("This can overwrite the current database after you select a backup.")
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = input(f"Type {phrase} to continue: ").strip()
    if confirmation != phrase:
        print("[INFO] Restore cancelled.")
        return False
    return True


def main():
    """
    Emergency Database Restore Wrapper.
    Launches the full interactive restore utility from manage_backups.py.
    """
    print("="*40)
    print("   LMS EMERGENCY DATABASE RESTORE")
    print("="*40)
    
    # Identify the correct python executable
    python_exe = sys.executable
    
    # Path to the main backup script (it is 2 levels up from services/)
    backup_script = Path(__file__).resolve().parent.parent.parent / "manage_backups.py"
    
    if not backup_script.exists():
        print(f"[ERROR] Could not find {backup_script.name} in the current directory.")
        return

    if not confirm_restore():
        return

    try:
        # Run the restore command
        subprocess.run([python_exe, str(backup_script), "--restore"], check=True)
    except KeyboardInterrupt:
        print("\n\n[INFO] Restore process interrupted by user.")
    except subprocess.CalledProcessError:
        print("\n[ERROR] The restore process encountered an error.")
    except Exception as e:
        print(f"\n[ERROR] An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
