from django.core.management.base import BaseCommand
from App.services.weekly_report_service import send_weekly_hr_report

class Command(BaseCommand):
    help = 'Triggers the Weekly HR Operational Snapshot report manually for testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Initializing Manual Report Generation ---'))
        try:
            sent = send_weekly_hr_report()
            if sent:
                self.stdout.write(self.style.SUCCESS('SUCCESS: Weekly HR Report sent!'))
            else:
                self.stdout.write(self.style.ERROR('ERROR: Weekly HR Report was not sent. Check the report/email logs for details.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERROR: Failed to send report: {e}'))
