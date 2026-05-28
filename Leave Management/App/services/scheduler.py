import logging
import os
import sys
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger('lms_scheduler')


def _setup_django_for_direct_run():
    project_root = Path(__file__).resolve().parents[2]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "leave_management.settings")
    os.environ.setdefault("LMS_SKIP_UPTIME_RECORD", "1")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()


if __name__ == "__main__":
    _setup_django_for_direct_run()


SCHEDULER_JOB_DETAILS = [
    {
        "id": "startup_catchup",
        "name": "Startup catch-up checks",
        "schedule": "Runs once when scheduler starts",
        "service_file": "startup_checks.py",
        "function": "run_startup_catchup",
        "effect": "Checks missed backup and weekly report work after downtime.",
    },
    {
        "id": "year_end_carry_forward",
        "name": "Year-end carry forward",
        "schedule": "Daily at 01:00",
        "service_file": "year_end_service.py",
        "function": "run_year_end_carry_forward_if_due",
        "effect": "Runs leave carry-forward only when due.",
    },
    {
        "id": "nightly_backup",
        "name": "Nightly backup check",
        "schedule": "Daily at 02:00",
        "service_file": "startup_checks.py",
        "function": "check_and_run_missed_backup",
        "effect": "Checks whether backup is missed and runs it if needed.",
    },
    {
        "id": "weekly_hr_report",
        "name": "Weekly HR report",
        "schedule": "Every Monday at 09:00",
        "service_file": "startup_checks.py",
        "function": "check_and_run_missed_weekly_report",
        "effect": "Checks whether weekly HR report is missed and sends it if needed.",
    },
    {
        "id": "public_holiday_sync",
        "name": "Public holiday sync",
        "schedule": "Monthly on day 1 at 03:00, plus once after scheduler starts",
        "service_file": "public_holidays.py",
        "function": "sync_public_holidays",
        "effect": "Refreshes saved India public holidays without slowing user calendar requests.",
    },
    {
        "id": "admin_email_job_recovery",
        "name": "Admin email job recovery",
        "schedule": "Every 5 minutes",
        "service_file": "admin_bulk_email_jobs.py",
        "function": "recover_stuck_admin_email_jobs",
        "effect": "Retries admin email jobs stuck in running state after worker interruption.",
    },
    {
        "id": "scheduler_keepalive",
        "name": "Scheduler keep-alive",
        "schedule": "Every 6 hours",
        "service_file": "scheduler.py",
        "function": "logger.info keep-alive",
        "effect": "Logs that scheduler is alive. No data change.",
    },
]

def start_scheduler():
    logger.info("SCHEDULER | START | Preparing in-app background scheduler.")
    from App.services.year_end_service import run_year_end_carry_forward_if_due
    from App.services.startup_checks import check_and_run_missed_backup, check_and_run_missed_weekly_report
    from App.services.background_tasks import enqueue_background_task
    from App.services.public_holidays import sync_public_holidays
    from App.services.admin_bulk_email_jobs import recover_stuck_admin_email_jobs

    scheduler = BackgroundScheduler()
    logger.info("SCHEDULER | JOBSTORE | Using in-memory job store.")

    # Run catch-up checks for missed tasks during downtime
    try:
        from App.services.startup_checks import run_startup_catchup
        run_startup_catchup()
    except Exception as e:
        logger.error(f"SCHEDULER | Failed to run startup catch-up: {e}")

    enqueue_background_task(sync_public_holidays, task_name="public_holiday_sync_startup")

    # Schedule the year-end carry forward at 1:00 AM every night
    scheduler.add_job(
        run_year_end_carry_forward_if_due,
        trigger="cron",
        hour=1,
        minute=0,
        id="year_end_carry_forward",
        max_instances=1,
        replace_existing=True,
    )
    logger.info("SCHEDULER | JOB_ADDED | year_end_carry_forward | Daily 01:00")

    # Schedule the backup job at 2:00 AM every night
    scheduler.add_job(
        check_and_run_missed_backup,
        trigger="cron",
        hour=2,
        minute=0,
        id="nightly_backup",
        max_instances=1,
        replace_existing=True,
    )
    logger.info("SCHEDULER | JOB_ADDED | nightly_backup | Daily 02:00")

    # Schedule the Weekly HR Report at 9:00 AM every Monday
    scheduler.add_job(
        check_and_run_missed_weekly_report,
        trigger="cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="weekly_hr_report",
        max_instances=1,
        replace_existing=True,
    )
    logger.info("SCHEDULER | JOB_ADDED | weekly_hr_report | Monday 09:00")

    scheduler.add_job(
        sync_public_holidays,
        trigger="cron",
        day=1,
        hour=3,
        minute=0,
        id="public_holiday_sync",
        max_instances=1,
        replace_existing=True,
    )
    logger.info("SCHEDULER | JOB_ADDED | public_holiday_sync | Monthly day 1 03:00")

    scheduler.add_job(
        recover_stuck_admin_email_jobs,
        trigger="interval",
        minutes=5,
        id="admin_email_job_recovery",
        max_instances=1,
        replace_existing=True,
    )
    logger.info("SCHEDULER | JOB_ADDED | admin_email_job_recovery | Every 5 minutes")
    
    # Add a sanity check job that runs every 6 hours just to confirm the scheduler is alive
    scheduler.add_job(
        lambda: logger.info("SCHEDULER | Keep-alive check: Scheduler is running."),
        trigger="interval",
        hours=6,
        id="scheduler_keepalive",
        max_instances=1,
        replace_existing=True,
    )
    logger.info("SCHEDULER | JOB_ADDED | scheduler_keepalive | Every 6 hours")

    logger.info("SCHEDULER | STARTING | Starting scheduler with %s job(s).", len(scheduler.get_jobs()))
    scheduler.start()
    logger.info(
        "SCHEDULER | STARTED | In-app background scheduler started successfully | Running=%s | Jobs=%s",
        scheduler.running,
        len(scheduler.get_jobs()),
    )
    return scheduler


def _safe_input(prompt):
    try:
        return input(prompt).strip()
    except (EOFError, KeyboardInterrupt):
        print("")
        return "0"


def _print_job(job, index=None):
    prefix = f"{index}. " if index is not None else ""
    print(f"{prefix}{job['name']}")
    print(f"   ID: {job['id']}")
    print(f"   Schedule: {job['schedule']}")
    print(f"   Service: {job['service_file']}")
    print(f"   Function: {job['function']}")
    print(f"   Effect: {job['effect']}")


def show_scheduler_jobs():
    print("\nScheduler Job List")
    for index, job in enumerate(SCHEDULER_JOB_DETAILS, start=1):
        _print_job(job, index=index)
    _print_manual_run_note()


def show_scheduler_status():
    print("\nScheduler Status")
    print("Type: In-app APScheduler BackgroundScheduler")
    print("Job store: In-memory")
    print("Starts from: App startup/server bootstrap")
    print(f"Configured jobs: {len(SCHEDULER_JOB_DETAILS)}")
    print("Manual triggers: Not enabled here, to avoid accidental emails/data changes.")
    _print_manual_run_note()


def _print_manual_run_note():
    print("\nNote")
    print("If you want to run a specific scheduled job manually, use its own service file:")
    print("- Weekly HR report: weekly_report_service.py")
    print("- Startup catch-up / missed backup / missed weekly report checks: startup_checks.py")
    print("- Year-end carry forward: year_end_service.py")
    print("- Public holiday sync: public_holidays.py")
    print("- Scheduler keep-alive: scheduler.py only logs status; no manual run is needed.")


def run_interactive():
    while True:
        print("\nScheduler Viewer")
        print("1. View scheduler status")
        print("2. View configured jobs")
        print("3. View job detail")
        print("0. Exit")

        choice = _safe_input("Choose an option: ").lower()
        if choice in {"0", "exit", "q", "quit"}:
            print("Exit.")
            return 0
        if choice == "1":
            show_scheduler_status()
            _safe_input("\nPress Enter to continue...")
        elif choice == "2":
            show_scheduler_jobs()
            _safe_input("\nPress Enter to continue...")
        elif choice == "3":
            for index, job in enumerate(SCHEDULER_JOB_DETAILS, start=1):
                print(f"{index}. {job['name']} ({job['id']})")
            selected = _safe_input("Select job number (B=Back, 0=Exit): ").lower()
            if selected == "0":
                print("Exit.")
                return 0
            if selected == "b":
                continue
            if selected.isdigit() and 1 <= int(selected) <= len(SCHEDULER_JOB_DETAILS):
                print("")
                _print_job(SCHEDULER_JOB_DETAILS[int(selected) - 1])
                _safe_input("\nPress Enter to continue...")
            else:
                print("Invalid choice.")
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    raise SystemExit(run_interactive())
