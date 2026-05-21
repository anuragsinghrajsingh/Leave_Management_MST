from django.core.management.base import BaseCommand
from App.services.weekly_report_service import build_manual_weekly_report_context_from_prompt, send_weekly_hr_report

class Command(BaseCommand):
    help = 'Triggers the Weekly HR Operational Snapshot report manually for testing.'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS('--- Initializing Manual Report Generation ---'))
        try:
            context = build_manual_weekly_report_context_from_prompt()
            if context is None:
                self.stdout.write(self.style.WARNING('Cancelled. Weekly HR Report was not sent.'))
                return

            confirmation = input("Type SEND to send, or anything else to cancel: ").strip()
            if confirmation != "SEND":
                self.stdout.write(self.style.WARNING('Cancelled. Weekly HR Report was not sent.'))
                return

            sent = send_weekly_hr_report(context=context)
            if sent:
                self.stdout.write(self.style.SUCCESS('SUCCESS: Weekly HR Report sent!'))
            else:
                self.stdout.write(self.style.ERROR('ERROR: Weekly HR Report was not sent. Check the report/email logs for details.'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'ERROR: Failed to send report: {e}'))
