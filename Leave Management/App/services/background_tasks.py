import logging
import importlib.util
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import monotonic

from django.conf import settings
from django.db import close_old_connections


logger = logging.getLogger("lms_background")
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lms-bg")
_qcluster_status_cache = {"checked_at": 0.0, "active": False}
_QCLUSTER_STATUS_TTL_SECONDS = 5


def _qcluster_looks_active():
    now = monotonic()
    if now - _qcluster_status_cache["checked_at"] < _QCLUSTER_STATUS_TTL_SECONDS:
        return _qcluster_status_cache["active"]

    active = _detect_qcluster()
    _qcluster_status_cache.update({"checked_at": now, "active": active})
    return active


def _detect_qcluster():
    if not importlib.util.find_spec("django_q"):
        return False

    try:
        from django_q.status import Stat

        if Stat.get_all():
            return True
    except Exception:
        logger.info("BACKGROUND_TASK_QUEUE_STATUS_UNAVAILABLE", exc_info=True)

    return _qcluster_process_looks_active()


def _qcluster_process_looks_active():
    try:
        import psutil
    except Exception:
        logger.info("BACKGROUND_TASK_QUEUE_PROCESS_CHECK_SKIPPED | psutil unavailable", exc_info=True)
        return False

    base_dir = Path(settings.BASE_DIR).resolve()
    for proc in psutil.process_iter(["cmdline", "cwd", "status"]):
        try:
            cmdline = proc.info.get("cmdline") or []
            command = " ".join(str(part).lower() for part in cmdline)
            if "manage.py" not in command or "qcluster" not in command:
                continue

            cwd = proc.info.get("cwd")
            if cwd and Path(cwd).resolve() == base_dir:
                return True

            if not cwd:
                return True
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue
        except Exception:
            logger.info("BACKGROUND_TASK_QUEUE_PROCESS_CHECK_ERROR", exc_info=True)

    return False


def _enqueue_with_django_q(func, *args, task_name="", **kwargs):
    if not _qcluster_looks_active():
        return None

    try:
        from django_q.tasks import async_task

        task_id = async_task(func, *args, **kwargs)
        label = task_name or getattr(func, "__name__", "background_task")
        logger.info("BACKGROUND_TASK_QUEUED | %s | %s", label, task_id)
        return task_id
    except Exception:
        logger.exception("BACKGROUND_TASK_QUEUE_FAILED | %s", task_name or getattr(func, "__name__", "background_task"))
        return None


def _enqueue_with_thread(func, *args, task_name="", **kwargs):
    label = task_name or getattr(func, "__name__", "background_task")

    def runner():
        close_old_connections()
        try:
            return func(*args, **kwargs)
        except Exception:
            logger.exception("BACKGROUND_TASK_FAILED | %s", label)
            return None
        finally:
            close_old_connections()

    logger.info("BACKGROUND_TASK_THREAD_FALLBACK | %s", label)
    return _executor.submit(runner)


def enqueue_background_task(func, *args, task_name="", **kwargs):
    """Queue slow side effects, falling back to an in-process thread when needed."""
    queued_task = _enqueue_with_django_q(func, *args, task_name=task_name, **kwargs)
    if queued_task:
        return queued_task

    return _enqueue_with_thread(func, *args, task_name=task_name, **kwargs)
