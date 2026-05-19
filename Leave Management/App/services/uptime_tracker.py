import json
import sys
from pathlib import Path

from django.conf import settings
from django.utils import timezone


UPTIME_STATE_FILE = Path(settings.BASE_DIR) / "runtime" / "app_startup.json"


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


def record_app_startup():
    if not _is_managed_server_process():
        return

    UPTIME_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "started_at": timezone.now().isoformat(),
    }
    UPTIME_STATE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def get_app_started_at():
    if not UPTIME_STATE_FILE.exists():
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
