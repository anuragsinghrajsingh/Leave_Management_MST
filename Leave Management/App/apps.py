import os
from django.apps import AppConfig


class AppConfig(AppConfig):
    name = 'App'

    def ready(self):
        import App.signals.db_signals
        import App.signals.logging_signals
        
        # Start the background scheduler (only in main process to avoid duplicates)
        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_SETTINGS_MODULE'):
            try:
                from .services.scheduler import start_scheduler
                start_scheduler()
            except Exception as e:
                import logging
                logging.getLogger('lms_master').error(f"SCHEDULER | Failed to start: {e}")




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