import os
import logging
from datetime import timedelta
from django.utils.timezone import localdate, now
from django.conf import settings
from pathlib import Path

logger = logging.getLogger('lms_scheduler')

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
    try:
        from App.services.year_end_service import run_year_end_carry_forward_if_due
        run_year_end_carry_forward_if_due()
    except Exception as e:
        logger.error(f"SCHEDULER | Catch-up | Year-end check failed: {e}")

def check_and_run_missed_backup():
    """Runs a backup if one hasn't been performed yet today."""
    today_str = localdate().strftime('%Y%m%d')
    backup_dir = Path(settings.BASE_DIR) / 'backups'
    
    if not backup_dir.exists():
        backup_dir.mkdir(parents=True, exist_ok=True)
    
    # Look for any zip file with today's date in its name
    today_backups = list(backup_dir.glob(f"*_{today_str}_*.zip"))
    
    if not today_backups:
        logger.info(f"SCHEDULER | Catch-up | No backup found for {localdate()}. Triggering missed backup...")
        try:
            from manage_backups import run_backup
            run_backup()
        except Exception as e:
            logger.error(f"SCHEDULER | Catch-up | Missed backup failed: {e}")
    else:
        logger.info(f"SCHEDULER | Catch-up | Backup for {localdate()} already exists. Skipping.")

def check_and_run_missed_weekly_report():
    """Runs the weekly report if it's past Monday 9 AM and hasn't been sent this week."""
    today = localdate()
    # Monday is 0 in weekday()
    days_since_monday = today.weekday()
    
    if days_since_monday < 0: # Not Monday or later yet (shouldn't happen with weekday())
        return

    # Target: Monday of the current week
    monday_of_week = today - timedelta(days=days_since_monday)
    monday_str = monday_of_week.strftime('%Y-%m-%d')
    
    # Tracking file to avoid duplicate sends on the same day
    tracking_file = Path(settings.BASE_DIR) / 'backups' / 'last_weekly_report.txt'
    
    last_sent_monday = ""
    if tracking_file.exists():
        last_sent_monday = tracking_file.read_text().strip()
    
    if last_sent_monday != monday_str:
        # Check if it's actually Monday 9 AM yet (or any time after that)
        # For simplicity, if it's Monday and we haven't sent it, we send it on startup
        logger.info(f"SCHEDULER | Catch-up | Weekly report for week of {monday_str} not sent. Triggering now...")
        try:
            from App.services.weekly_report_service import send_weekly_hr_report
            send_weekly_hr_report()
            # Update tracking file
            tracking_file.write_text(monday_str)
        except Exception as e:
            logger.error(f"SCHEDULER | Catch-up | Missed weekly report failed: {e}")
    else:
        logger.info(f"SCHEDULER | Catch-up | Weekly report for week of {monday_str} already sent. Skipping.")
