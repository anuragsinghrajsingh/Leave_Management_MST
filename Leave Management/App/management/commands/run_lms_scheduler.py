import signal
import threading

from django.core.management.base import BaseCommand

from App.services.scheduler import start_scheduler


class Command(BaseCommand):
    help = "Run the LMS scheduler as a dedicated foreground process."

    def handle(self, *args, **options):
        stop_event = threading.Event()

        def request_stop(signum=None, frame=None):
            stop_event.set()

        signal.signal(signal.SIGTERM, request_stop)
        signal.signal(signal.SIGINT, request_stop)

        self.stdout.write(self.style.SUCCESS("Starting LMS scheduler process..."))
        scheduler = start_scheduler()
        self.stdout.write(self.style.SUCCESS("LMS scheduler is running. Press Ctrl+C to stop."))

        try:
            stop_event.wait()
        finally:
            if scheduler and scheduler.running:
                self.stdout.write("Stopping LMS scheduler...")
                scheduler.shutdown(wait=False)
            self.stdout.write(self.style.SUCCESS("LMS scheduler stopped."))
