import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events

logger = logging.getLogger('lms_scheduler')

def start_scheduler():
    from manage_backups import run_backup
    from App.services.year_end_service import run_year_end_carry_forward_if_due

    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

    # Run catch-up checks for missed tasks during downtime
    try:
        from App.services.startup_checks import run_startup_catchup
        run_startup_catchup()
    except Exception as e:
        logger.error(f"SCHEDULER | Failed to run startup catch-up: {e}")

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

    # Schedule the backup job at 2:00 AM every night
    scheduler.add_job(
        run_backup,
        trigger="cron",
        hour=2,
        minute=0,
        id="nightly_backup",
        max_instances=1,
        replace_existing=True,
    )

    # Schedule the Weekly HR Report at 9:00 AM every Monday
    from App.services.weekly_report_service import send_weekly_hr_report
    scheduler.add_job(
        send_weekly_hr_report,
        trigger="cron",
        day_of_week="mon",
        hour=9,
        minute=0,
        id="weekly_hr_report",
        max_instances=1,
        replace_existing=True,
    )
    
    # Add a sanity check job that runs every 6 hours just to confirm the scheduler is alive
    scheduler.add_job(
        lambda: logger.info("SCHEDULER | Keep-alive check: Scheduler is running."),
        trigger="interval",
        hours=6,
        id="scheduler_keepalive",
        max_instances=1,
        replace_existing=True,
    )

    register_events(scheduler)
    scheduler.start()
    logger.info("SCHEDULER | In-app background scheduler started successfully.")
