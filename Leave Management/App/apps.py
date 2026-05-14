from django.apps import AppConfig


class AppConfig(AppConfig):
    name = 'App'

    def ready(self):
        import App.signals.db_signals
        import App.signals.logging_signals




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