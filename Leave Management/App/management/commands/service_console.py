import sys
from contextlib import contextmanager

from django.core.management.base import BaseCommand


@contextmanager
def _service_argv(command_name):
    original_argv = sys.argv[:]
    sys.argv = [command_name]
    try:
        yield
    finally:
        sys.argv = original_argv


def _safe_input(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return "0"


class Command(BaseCommand):
    help = "Open a central terminal launcher for LMS service utilities."

    def handle(self, *args, **options):
        while True:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("LMS Service Console"))
            self.stdout.write("1. User password reset")
            self.stdout.write("2. Force password change")
            self.stdout.write("3. Login lock manager")
            self.stdout.write("4. Employee welcome package")
            self.stdout.write("5. Weekly HR report")
            self.stdout.write("6. Report export")
            self.stdout.write("7. PDF generator")
            self.stdout.write("8. Maintenance mode")
            self.stdout.write("9. Startup checks")
            self.stdout.write("10. Year-end carry forward")
            self.stdout.write("11. Database restore")
            self.stdout.write("12. Uptime viewer")
            self.stdout.write("13. Email delivery logs")
            self.stdout.write("14. Push notifications")
            self.stdout.write("15. Scheduler viewer")
            self.stdout.write("0. Exit")

            choice = _safe_input("Choose a service: ").lower()
            if choice in {"0", "exit", "q", "quit"}:
                self.stdout.write("Exit.")
                return

            if choice == "1":
                from App.services.user_password_reset_service import run_interactive

                run_interactive()
            elif choice == "2":
                from App.services.forced_password_service import run_cli

                run_cli()
            elif choice == "3":
                from App.services.login_lock_service import run_login_lock_cli

                run_login_lock_cli("SERVICE_CONSOLE")
            elif choice == "4":
                from App.services.employee_welcome_service import run_interactive

                run_interactive()
            elif choice == "5":
                from App.services.weekly_report_service import main

                main()
            elif choice == "6":
                from App.services.report_export_service import run_interactive

                run_interactive()
            elif choice == "7":
                from App.services.pdf_generator import main

                main()
            elif choice == "8":
                from App.services.maintenance_mode import run_interactive_menu

                run_interactive_menu()
            elif choice == "9":
                from App.services.startup_checks import main

                with _service_argv("startup_checks.py"):
                    main()
            elif choice == "10":
                from App.services.year_end_service import main

                with _service_argv("year_end_service.py"):
                    main()
            elif choice == "11":
                from App.services.restore_db import main

                main()
            elif choice == "12":
                from App.services.uptime_tracker import main

                main()
            elif choice == "13":
                from App.services.email_delivery_log import run_interactive

                run_interactive()
            elif choice == "14":
                from App.services.push_notifications import run_interactive

                run_interactive()
            elif choice == "15":
                from App.services.scheduler import run_interactive

                run_interactive()
            else:
                self.stdout.write(self.style.ERROR("Invalid choice."))
                continue

            back = _safe_input("\nPress Enter to return to service console, or 0 to exit: ").lower()
            if back in {"0", "exit", "q", "quit"}:
                self.stdout.write("Exit.")
                return
