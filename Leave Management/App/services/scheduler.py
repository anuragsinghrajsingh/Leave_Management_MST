import os
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from django_apscheduler.jobstores import DjangoJobStore, register_events
from manage_backups import run_backup

logger = logging.getLogger('lms_master')

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_jobstore(DjangoJobStore(), "default")

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
