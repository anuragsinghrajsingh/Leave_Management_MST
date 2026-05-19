import os
import logging
import threading
from django.apps import AppConfig


_scheduler_lock = threading.Lock()
_scheduler_started = False


def _should_start_scheduler_process():
    return os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_SETTINGS_MODULE')


def _start_scheduler_once():
    global _scheduler_started

    with _scheduler_lock:
        if _scheduler_started:
            logging.getLogger('lms_scheduler').info("SCHEDULER | START | Already started in this process. Skipping duplicate start.")
            return
        _scheduler_started = True

    try:
        from .services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        logging.getLogger('lms_master').error(f"SCHEDULER | Failed to start: {e}")


def _start_scheduler_after_app_ready():
    if not _should_start_scheduler_process():
        logging.getLogger('lms_scheduler').info("SCHEDULER | START | Skipped for non-server/bootstrap process.")
        return

    starter = threading.Timer(2.0, _start_scheduler_once)
    starter.daemon = True
    starter.start()
    logging.getLogger('lms_scheduler').info("SCHEDULER | START | Delayed startup scheduled.")


class AppConfig(AppConfig):
    name = 'App'

    def ready(self):
        import App.signals.db_signals
        import App.signals.logging_signals

        try:
            from .services.uptime_tracker import record_app_startup
            record_app_startup()
        except Exception as e:
            logging.getLogger('lms_master').error(f"UPTIME | Failed to record startup: {e}")
        
        _start_scheduler_after_app_ready()




# from django.apps import AppConfig
# from django.db import connection

# class AppConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'App'

#     def ready(self):
#         from django.contrib.sessions.models import Session
#         try:
#             Session.objects.all().delete()
#         except:
#             pass



# from django.contrib.sessions.models import Session
# Session.objects.all().delete()
