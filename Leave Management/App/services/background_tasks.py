import logging
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections


logger = logging.getLogger("lms_background")
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="lms-bg")


def enqueue_background_task(func, *args, task_name="", **kwargs):
    """Run slow side effects after the response path has been released."""
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

    return _executor.submit(runner)
