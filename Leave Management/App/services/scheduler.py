import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events

logger = logging.getLogger('lms_scheduler')

def start_scheduler():
    logger.info("SCHEDULER | START | Preparing in-app background scheduler.")
    from App.services.year_end_service import run_year_end_carry_forward_if_due
    from App.services.startup_checks import check_and_run_missed_backup, check_and_run_missed_weekly_report

    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")
    logger.info("SCHEDULER | JOBSTORE | DjangoJobStore attached.")

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

    register_events(scheduler)
    scheduler.start()
    logger.info("SCHEDULER | In-app background scheduler started successfully.")
