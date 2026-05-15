from django.core.management.base import BaseCommand
from App.services.weekly_report_service import send_weekly_hr_report

class Command(BaseCommand):
    help = 'Triggers the Weekly HR Operational Snapshot report manually for testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Initializing Manual Report Generation ---'))
        try:
            send_weekly_hr_report()
            self.stdout.write(self.style.SUCCESS('SUCCESS: Weekly HR Report sent!'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERROR: Failed to send report: {e}'))
