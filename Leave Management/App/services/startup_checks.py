import argparse
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path


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

from django.utils.timezone import localdate
from django.conf import settings

logger = logging.getLogger('lms_scheduler')


def get_backup_catchup_status():
    today = localdate()
    today_str = today.strftime('%Y%m%d')
    backup_dir = Path(settings.BASE_DIR) / 'backups'
    today_backups = list(backup_dir.glob(f"*_{today_str}_*.zip")) if backup_dir.exists() else []

    return {
        "today": today,
        "backup_dir": backup_dir,
        "today_backups": today_backups,
        "should_run": not bool(today_backups),
    }


def get_weekly_report_catchup_status():
    today = localdate()
    days_since_monday = today.weekday()
    monday_of_week = today - timedelta(days=days_since_monday)
    monday_str = monday_of_week.strftime('%Y-%m-%d')
    tracking_file = Path(settings.BASE_DIR) / 'backups' / 'last_weekly_report.txt'
    last_sent_monday = tracking_file.read_text().strip() if tracking_file.exists() else ""

    return {
        "today": today,
        "monday_str": monday_str,
        "tracking_file": tracking_file,
        "last_sent_monday": last_sent_monday,
        "should_run": last_sent_monday != monday_str,
    }


def get_year_end_catchup_status():
    from App.models import YearEndCarryForwardRun
    from App.services.year_end_service import SKIP_YEAR_END_YEARS

    processing_year = localdate().year
    if processing_year in SKIP_YEAR_END_YEARS:
        reason = f"protected year {processing_year}"
        should_run = False
    else:
        run_record = YearEndCarryForwardRun.objects.filter(year=processing_year).first()
        should_run = not bool(run_record and run_record.completed_at)
        reason = "not completed" if should_run else "already completed"

    return {
        "year": processing_year,
        "reason": reason,
        "should_run": should_run,
    }


def run_startup_catchup():
    """
    Checks for missed scheduled tasks during server downtime and runs them if necessary.
    """
    logger.info("SCHEDULER | Starting startup catch-up checks...")
    
    # 1. Check for missed Backup
    check_and_run_missed_backup()
    
    # 2. Check for missed Weekly Report
    check_and_run_missed_weekly_report()
    
    # 3. Check for missed Year-End Carry Forward (Already has its own check)
    check_and_run_year_end_carry_forward()

def check_and_run_missed_backup():
    """Runs a backup if one hasn't been performed yet today."""
    status = get_backup_catchup_status()
    backup_dir = status["backup_dir"]
    
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
    
    if status["should_run"]:
        logger.info(f"SCHEDULER | Catch-up | No backup found for {status['today']}. Triggering missed backup...")
        try:
            from manage_backups import run_backup
            run_backup()
        except Exception as e:
            logger.error(f"SCHEDULER | Catch-up | Missed backup failed: {e}")
    else:
        logger.info(f"SCHEDULER | Catch-up | Backup for {status['today']} already exists. Skipping.")

def check_and_run_missed_weekly_report():
    """Runs the weekly report if it's past Monday 9 AM and hasn't been sent this week."""
    status = get_weekly_report_catchup_status()
    
    if status["should_run"]:
        # Check if it's actually Monday 9 AM yet (or any time after that)
        # For simplicity, if it's Monday and we haven't sent it, we send it on startup
        logger.info(f"SCHEDULER | Catch-up | Weekly report for week of {status['monday_str']} not sent. Triggering now...")
        try:
            from App.services.weekly_report_service import send_weekly_hr_report
            sent = send_weekly_hr_report()
            if sent:
                status["tracking_file"].parent.mkdir(parents=True, exist_ok=True)
                status["tracking_file"].write_text(status["monday_str"])
            else:
                logger.error("SCHEDULER | Catch-up | Weekly report send returned false. Tracking file was not updated.")
        except Exception as e:
            logger.error(f"SCHEDULER | Catch-up | Missed weekly report failed: {e}")
    else:
        logger.info(f"SCHEDULER | Catch-up | Weekly report for week of {status['monday_str']} already sent. Skipping.")


def check_and_run_year_end_carry_forward():
    try:
        from App.services.year_end_service import run_year_end_carry_forward_if_due
        did_run = run_year_end_carry_forward_if_due()
        if did_run:
            logger.info("SCHEDULER | Catch-up | Year-end carry forward completed.")
        else:
            logger.info("SCHEDULER | Catch-up | Year-end carry forward not due or already completed. Skipping.")
    except Exception as e:
        logger.error(f"SCHEDULER | Catch-up | Year-end check failed: {e}")


def _selected_checks(args):
    checks = {
        "backup": args.backup,
        "weekly_report": args.weekly_report,
        "year_end": args.year_end,
    }

    if not any(checks.values()):
        return {key: True for key in checks}

    return checks


def print_startup_check_dry_run(selected):
    print("--- Startup Checks Dry Run ---")
    print("No backup, email, or balance changes will be made.\n")

    if selected["backup"]:
        status = get_backup_catchup_status()
        print(f"Backup: {'would run' if status['should_run'] else 'would skip'}")
        print(f"  Date: {status['today']}")
        print(f"  Found today backups: {len(status['today_backups'])}")

    if selected["weekly_report"]:
        status = get_weekly_report_catchup_status()
        print(f"Weekly report: {'would send' if status['should_run'] else 'would skip'}")
        print(f"  Week Monday: {status['monday_str']}")
        print(f"  Last sent marker: {status['last_sent_monday'] or 'missing'}")

    if selected["year_end"]:
        status = get_year_end_catchup_status()
        print(f"Year-end carry forward: {'would run' if status['should_run'] else 'would skip'}")
        print(f"  Year: {status['year']}")
        print(f"  Reason: {status['reason']}")


def run_selected_startup_checks(selected):
    if selected["backup"]:
        check_and_run_missed_backup()
    if selected["weekly_report"]:
        check_and_run_missed_weekly_report()
    if selected["year_end"]:
        check_and_run_year_end_carry_forward()


def main():
    parser = argparse.ArgumentParser(description="Inspect or run startup catch-up checks.")
    parser.add_argument("--dry-run", action="store_true", help="Show what would happen and exit without confirmation.")
    parser.add_argument("--run", action="store_true", help="Deprecated: real run is now the default after confirmation.")
    parser.add_argument("--backup", action="store_true", help="Include missed backup check.")
    parser.add_argument("--weekly-report", action="store_true", help="Include missed weekly report check.")
    parser.add_argument("--year-end", action="store_true", help="Include year-end carry forward check.")
    args = parser.parse_args()

    selected = _selected_checks(args)

    if args.dry_run:
        print_startup_check_dry_run(selected)
        return

    print_startup_check_dry_run(selected)
    print("\nThis may create backups, send email, or update leave balances.")
    confirmation_phrase = "PRODUCTION_RUN_STARTUP_CHECKS" if not settings.DEBUG else "RUN_STARTUP_CHECKS"
    if not settings.DEBUG:
        print("PRODUCTION MODE DETECTED.")
    print("Confirmation is case-sensitive. Type the phrase exactly as shown.")
    confirmation = input(f"Type {confirmation_phrase} to continue: ").strip()

    if confirmation != confirmation_phrase:
        print("Cancelled. Startup checks were not run.")
        return

    run_selected_startup_checks(selected)
    print("Startup checks finished. Review logs for details.")

if __name__ == "__main__":
    main()
