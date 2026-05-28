import json
import logging
import os
import sys
from pathlib import Path


def _setup_django_for_direct_run():
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
    _setup_django_for_direct_run()

from django.conf import settings
from django.utils import timezone


UPTIME_STATE_FILE = Path(settings.BASE_DIR) / "runtime" / "app_startup.json"
logger = logging.getLogger("lms_service_uptime_tracker")


def _is_managed_server_process():
    args = [Path(arg).name.lower() for arg in sys.argv]

    if not args:
        return True

    if "manage.py" not in args:
        return True

    if "runserver" not in args:
        return False

    # Django autoreloader starts a parent process and a child process. The child
    # is the actual server process, so record only that one.
    return bool(__import__("os").environ.get("RUN_MAIN") == "true")


def record_app_startup(force=False):
    if os.environ.get("LMS_SKIP_UPTIME_RECORD") == "1" and not force:
        logger.info("UPTIME | STARTUP_RECORD | Skipped because LMS_SKIP_UPTIME_RECORD=1.")
        return

    if not force and not _is_managed_server_process():
        logger.info("UPTIME | STARTUP_RECORD | Skipped because process is not managed server process.")
        return

    UPTIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "started_at": timezone.now().isoformat(),
    }
    UPTIME_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info(
        "UPTIME | STARTUP_RECORD | Recorded app startup at %s. | Force=%s",
        payload["started_at"],
        force,
    )


def get_app_started_at():
    if not UPTIME_STATE_FILE.exists():
        logger.info("UPTIME | READ | Startup state file missing.")
        return None

    try:
        payload = json.loads(UPTIME_STATE_FILE.read_text(encoding="utf-8"))
        started_at_raw = payload.get("started_at")
        if not started_at_raw:
            return None
        started_at = timezone.datetime.fromisoformat(started_at_raw)
        if timezone.is_naive(started_at):
            started_at = timezone.make_aware(started_at)
        return started_at
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        logger.warning("UPTIME | READ | Could not parse startup state file.")
        return None


def format_current_uptime():
    started_at = get_app_started_at()
    if not started_at:
        return "Not tracked yet"

    elapsed = timezone.now() - started_at
    total_seconds = max(int(elapsed.total_seconds()), 0)
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)

    parts = []
    if days:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes or not parts:
        parts.append(f"{minutes} min")

    return "Running for " + " ".join(parts[:3])


def main():
    logger.info("UPTIME | MANUAL_RUN | Opened direct viewer.")
    print("--- App Uptime Manual Viewer ---")
    print("This only reads uptime. It will not overwrite the recorded app startup time.")
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = input("Type SHOW to continue: ").strip()

    if confirmation != "SHOW":
        logger.info("UPTIME | MANUAL_RUN | Cancelled by confirmation.")
        print("Cancelled. Uptime was not shown.")
        return

    started_at = get_app_started_at()
    logger.info("UPTIME | MANUAL_RUN | Shown | StartedAt=%s | Uptime=%s", started_at, format_current_uptime())
    print(f"Startup Time: {timezone.localtime(started_at).strftime('%b %d, %Y %I:%M %p') if started_at else 'Not tracked yet'}")
    print(f"Current Uptime: {format_current_uptime()}")


if __name__ == "__main__":
    main()
