# Leave Management Deployment Guide

Last updated: 2026-07-08

This guide is the living deployment manual for the Leave Management project. It explains how the project is deployed on production, how to update it safely, how to operate the services, and how to debug common production issues.

Keep this file updated whenever deployment steps, services, environment variables, migrations, static files, scheduler jobs, or production rules change.

## 1. Current Production Shape

### 1.1 Production Server

Current production working directory:

```bash
/home/mstleave/Leave_Management_MST
```

Common production prompt:

```bash
(venv) mstleave@mstleave-VM:~/Leave_Management_MST$
```

Current public portal:

```text
https://mstleave.mstlabs.in
```

Current production services:

```text
postgresql      Database service
gunicorn        Django web app service
qcluster        Django-Q background task worker service
lms_scheduler   Dedicated LMS scheduler service
nginx           Reverse proxy, SSL/static/media front layer
```

### 1.2 GitHub Layout vs Production Layout

The GitHub repository stores the Django project inside:

```text
Leave Management/
```

But production is deployed with the contents of that folder directly under:

```text
/home/mstleave/Leave_Management_MST/
```

So a file in GitHub like:

```text
Leave Management/App/views.py
```

is loaded in production as:

```text
App/views.py
```

This is why production update commands use:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

Do not blindly use `git pull` on production unless the production working tree layout has been intentionally fixed to match the repository layout.

## 2. High-Level Architecture

### 2.1 Request Flow

Browser:

```text
https://mstleave.mstlabs.in
```

goes to:

```text
nginx
```

then nginx proxies dynamic requests to:

```text
gunicorn unix socket
```

then Gunicorn runs:

```text
leave_management.wsgi:application
```

then Django talks to:

```text
PostgreSQL
```

Static files are served from:

```text
staticfiles/
```

Uploaded media/profile photos are served from:

```text
media/
```

### 2.2 Background Work

Background tasks use Django-Q:

```text
qcluster.service
```

Common queued work includes:

```text
admin bulk email jobs
public holiday sync tasks
push notification tasks
email sending tasks where queued
```

The queue broker is database-backed through Django-Q ORM.

### 2.3 Scheduled Work

Scheduled work uses a dedicated systemd service:

```text
lms_scheduler.service
```

It runs:

```bash
python manage.py run_lms_scheduler
```

The scheduler process starts APScheduler jobs and also runs startup catch-up checks.

Current scheduler jobs:

```text
startup_catchup              Runs once when scheduler starts
year_end_carry_forward       Daily 01:00
nightly_backup               Daily 02:00
weekly_hr_report             Monday 09:00
public_holiday_sync          Monthly day 1 03:00, plus once after scheduler starts
admin_email_job_recovery     Every 5 minutes
scheduler_keepalive          Every 6 hours
```

## 3. Production Services

### 3.1 Gunicorn

Service:

```bash
sudo systemctl status gunicorn --no-pager
```

Restart:

```bash
sudo systemctl restart gunicorn
```

Logs:

```bash
sudo journalctl -u gunicorn -n 100 --no-pager
sudo journalctl -u gunicorn -f
```

Current observed setup:

```text
1 master process
3 worker processes
```

Gunicorn is responsible for web pages, admin pages, login pages, API endpoints, and normal Django requests.

Restart Gunicorn when these change:

```text
Python web code
Django settings
templates
.env values used by web requests
forms/admin/views/models/services used by web requests
```

### 3.2 Qcluster

Service:

```bash
sudo systemctl status qcluster --no-pager
```

Restart:

```bash
sudo systemctl restart qcluster
```

Logs:

```bash
sudo journalctl -u qcluster -n 100 --no-pager
sudo journalctl -u qcluster -f
```

Current observed setup:

```text
6 total qcluster processes
2 actual task worker processes
1 guard
1 monitor
1 pusher
1 parent/main process
```

Qcluster should be restarted when these change:

```text
background task code
email job code
settings used by background tasks
.env values used by background tasks
admin_bulk_email_jobs.py
push notification service code
email service code
```

Qcluster logs may show messages like:

```text
reincarnated pusher after sudden death
```

This means Django-Q restarted an internal process. If it happens once during reboot or database restart, it is usually not a problem. If it repeats constantly during normal time, investigate database connectivity and service health.

### 3.3 LMS Scheduler

Service:

```bash
sudo systemctl status lms_scheduler --no-pager
```

Restart:

```bash
sudo systemctl restart lms_scheduler
```

Logs:

```bash
sudo journalctl -u lms_scheduler -n 100 --no-pager
sudo journalctl -u lms_scheduler -f
```

Scheduler command:

```bash
python manage.py run_lms_scheduler
```

The command prints:

```text
Starting LMS scheduler process...
LMS scheduler is running. Press Ctrl+C to stop.
Stopping LMS scheduler...
LMS scheduler stopped.
```

Scheduler should be restarted when these change:

```text
scheduler.py
run_lms_scheduler.py
startup_checks.py
year_end_service.py
weekly_report_service.py
public_holidays.py
admin_bulk_email_jobs.py recovery logic
.env values used by scheduled jobs
```

### 3.4 PostgreSQL

Service:

```bash
sudo systemctl status postgresql --no-pager
```

Check client tools:

```bash
which pg_dump
which psql
pg_dump --version
psql --version
```

Backups require `pg_dump`.

Restores require `psql`.

Production systemd services must have `/usr/bin` in their PATH so `pg_dump` and `psql` can be found.

Check service environment:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

Expected PATH shape:

```text
PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

If `/usr/bin` is missing, backup or restore can fail with:

```text
[Errno 2] No such file or directory: 'pg_dump'
```

## 4. Environment Configuration

### 4.1 Real `.env`

Production uses:

```bash
/home/mstleave/Leave_Management_MST/.env
```

Do not overwrite the real `.env` with `.env.example`.

`.env.example` is documentation and a template only.

After changing `.env`, restart the services that need the changed value.

Usually:

```bash
sudo systemctl restart gunicorn
```

If background tasks or scheduler also use the setting:

```bash
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

### 4.2 Core Production Variables

Required production settings:

```env
DJANGO_SECRET_KEY=replace-with-real-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=mstleave.mstlabs.in
DJANGO_CSRF_TRUSTED_ORIGINS=https://mstleave.mstlabs.in
PORTAL_BASE_URL=https://mstleave.mstlabs.in
```

Database:

```env
DB_ENGINE=postgresql
DB_NAME=leave_management
DB_USER=leave_user
DB_PASSWORD=replace-this-db-password
DB_HOST=localhost
DB_PORT=5432
```

Email:

```env
EMAIL_HOST=mail.mst-india.com
EMAIL_PORT=465
EMAIL_USE_TLS=False
EMAIL_USE_SSL=True
EMAIL_HOST_USER=leavedesk@mst-india.com
EMAIL_HOST_PASSWORD=replace-with-real-password
DEFAULT_FROM_EMAIL=leavedesk@mst-india.com
LEAVE_DESK_FROM_EMAIL=leavedesk@mst-india.com
LEAVE_RECORD_EMAILS=leave@mst-india.com
```

Security:

```env
PASSWORD_INPUT_MAX_LENGTH=128
```

Leave timing:

```env
SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES=15
SHORT_HALF_LEAVE_GRACE_MINUTES=5
SICK_LEAVE_SAME_DAY_CUTOFF_TIME=11:59
```

Web push:

```env
WEB_PUSH_VAPID_PUBLIC_KEY=...
WEB_PUSH_VAPID_PRIVATE_KEY=runtime/webpush_private_key.pem
WEB_PUSH_VAPID_SUBJECT=mailto:admin@example.com
```

### 4.3 Security Settings Check

Run:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_HTTPONLY, settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SECURE)"
```

Expected production output:

```text
True True Lax True
```

## 5. First-Time Server Setup

This section is for a fresh Linux server.

### 5.1 System Packages

Install common packages:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip postgresql postgresql-client nginx git
```

`postgresql-client` provides:

```text
pg_dump
psql
```

Optional terminal clipboard helper:

```bash
sudo apt install xclip
```

This only affects the terminal password reset helper. It does not affect the web app.

### 5.2 Project Directory

Production project path:

```bash
cd ~
mkdir -p Leave_Management_MST
cd Leave_Management_MST
```

The current production layout stores Django files directly in this directory.

### 5.3 Virtual Environment

Create and activate venv:

```bash
python3 -m venv venv
source venv/bin/activate
```

Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

Install Playwright browser:

```bash
python -m playwright install chromium
```

Verify:

```bash
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); print('playwright chromium ok'); b.close(); p.stop()"
```

Expected:

```text
playwright chromium ok
```

### 5.4 Secrets

Production helper scripts:

```bash
python App/management/production_setup/generate_all.py
```

This can generate:

```text
DJANGO_SECRET_KEY
DB_PASSWORD
WEB_PUSH_VAPID_PUBLIC_KEY
WEB_PUSH_VAPID_PRIVATE_KEY
WEB_PUSH_VAPID_SUBJECT
```

Individual scripts:

```bash
python App/management/production_setup/generate_django_secret_key.py
python App/management/production_setup/generate_database_password.py
python App/management/production_setup/generate_webpush_keys.py
```

Do not regenerate web push keys after users have subscribed unless you are okay with users enabling notifications again.

### 5.5 Database

Create PostgreSQL DB/user according to the `.env` values.

Then run:

```bash
python manage.py migrate
```

Create admin user:

```bash
python manage.py createsuperuser
```

If the admin user cannot log in because role/profile flags are missing, run the known fix:

```bash
python manage.py shell -c "from django.utils import timezone; from App.models import CustomUser, Profile; u=CustomUser.objects.get(username='mst_leave_admin'); u.role='Admin'; u.is_staff=True; u.is_superuser=True; u.must_change_password=False; u.is_active=True; u.save(); Profile.objects.update_or_create(user=u, defaults={'role':'Admin','department':'Management','date_of_joining':timezone.localdate(),'employee_id':'MST_Admin-0001'}); print('Admin fixed:', u.username, u.role, u.is_staff, u.is_superuser, u.is_active)"
```

### 5.6 Static and Media

Collect static files:

```bash
python manage.py collectstatic
```

Answer:

```text
yes
```

Production nginx must serve:

```text
/static/ -> staticfiles/
/media/  -> media/
```

## 6. Systemd Services

### 6.1 Gunicorn Service

Typical command:

```text
/home/mstleave/Leave_Management_MST/venv/bin/gunicorn --workers 3 --bind unix:/home/mstleave/Leave_Management_MST/gunicorn.sock leave_management.wsgi:application
```

Important service properties:

```text
User=mstleave
Group=www-data
WorkingDirectory=/home/mstleave/Leave_Management_MST
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Use a systemd override when editing environment:

```bash
sudo systemctl edit gunicorn
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

### 6.2 Qcluster Service

Typical command:

```text
/home/mstleave/Leave_Management_MST/venv/bin/python /home/mstleave/Leave_Management_MST/manage.py qcluster
```

Important environment:

```text
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Edit:

```bash
sudo systemctl edit qcluster
sudo systemctl daemon-reload
sudo systemctl restart qcluster
```

### 6.3 LMS Scheduler Service

Typical command:

```text
/home/mstleave/Leave_Management_MST/venv/bin/python /home/mstleave/Leave_Management_MST/manage.py run_lms_scheduler
```

Important environment:

```text
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Edit:

```bash
sudo systemctl edit lms_scheduler
sudo systemctl daemon-reload
sudo systemctl restart lms_scheduler
```

Enable:

```bash
sudo systemctl enable gunicorn
sudo systemctl enable qcluster
sudo systemctl enable lms_scheduler
sudo systemctl enable postgresql
```

Check:

```bash
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
sudo systemctl is-enabled postgresql
```

Expected:

```text
enabled
enabled
enabled
enabled
```

## 7. Standard Deployment Workflow

Use this when code has been pushed to GitHub and production must load selected files.

### 7.1 Start

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
```

Check changed files in latest remote commit:

```bash
git show --name-only --pretty=format:"%h %s" origin/main
```

### 7.2 Load Files From GitHub

Because GitHub paths include `Leave Management/`, use:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

Examples:

```bash
git show origin/main:"Leave Management/App/admin.py" > App/admin.py
git show origin/main:"Leave Management/App/forms.py" > App/forms.py
git show origin/main:"Leave Management/App/models.py" > App/models.py
git show origin/main:"Leave Management/leave_management/settings.py" > leave_management/settings.py
git show origin/main:"Leave Management/templates/employee_login.html" > templates/employee_login.html
git show origin/main:"Leave Management/static/js/apply_leave.js" > static/js/apply_leave.js
```

If a new folder/file is added:

```bash
mkdir -p App/scripts
git show origin/main:"Leave Management/App/scripts/__init__.py" > App/scripts/__init__.py
git show origin/main:"Leave Management/App/scripts/validators.py" > App/scripts/validators.py
```

Empty `__init__.py` files are normal and should still be loaded.

### 7.3 Check for Migrations

If any file under this path changed:

```text
App/migrations/
```

run:

```bash
python manage.py migrate
```

If no migration changed, do not run migrate just for templates/static/Python code.

### 7.4 Check Static Files

Run collectstatic when any file under these paths changed:

```text
static/
static/admin/
static/css/
static/js/
static/images/
```

Command:

```bash
python manage.py collectstatic
```

Answer:

```text
yes
```

If only templates or Python files changed, collectstatic is not required.

### 7.5 Validate

Always run:

```bash
python manage.py check
```

Expected:

```text
System check identified no issues (0 silenced).
```

### 7.6 Restart Services

For web/templates/settings:

```bash
sudo systemctl restart gunicorn
```

For background task code/settings:

```bash
sudo systemctl restart qcluster
```

For scheduler/startup/backup/weekly report code/settings:

```bash
sudo systemctl restart lms_scheduler
```

Check:

```bash
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
```

Expected:

```text
Active: active (running)
```

## 8. Deployment Decision Table

Use this table to know which commands to run.

```text
Changed file type                         migrate   collectstatic   restart gunicorn   restart qcluster   restart scheduler
settings.py                               no        no              yes               maybe              maybe
.env                                      no        no              yes               maybe              maybe
App/views.py                              no        no              yes               no                 no
App/forms.py                              no        no              yes               no                 no
App/admin.py                              no        no              yes               maybe              no
App/models.py no field change             no        no              yes               maybe              maybe
App/models.py field/schema change         yes       no              yes               maybe              maybe
App/migrations/*.py                       yes       no              yes               maybe              maybe
templates/*.html                          no        no              yes               no                 no
static/js/*.js                            no        yes             yes               no                 no
static/css/*.css                          no        yes             yes               no                 no
App/services/admin_bulk_email_jobs.py     no        no              maybe             yes                yes if recovery changed
App/services/scheduler.py                 no        no              no                no                 yes
App/services/startup_checks.py            no        no              no                no                 yes
manage_backups.py                         no        no              yes if admin uses it no                yes
requirements.txt                          no        no              yes               yes                yes
```

After `requirements.txt` changes:

```bash
pip install -r requirements.txt
python manage.py check
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

## 9. Version-Specific Deployment Notes

### 9.1 Password Max Length Validator

Files involved:

```text
leave_management/settings.py
App/scripts/__init__.py
App/scripts/validators.py
App/views.py
App/forms.py
App/admin.py
App/services/user_password_reset_service.py
templates/admin_login.html
templates/employee_login.html
templates/hr_login.html
templates/login.html
templates/auth/force_password_change.html
templates/employee_details.html
.env.example
```

Production `.env` should contain:

```env
PASSWORD_INPUT_MAX_LENGTH=128
```

Verify:

```bash
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
```

Expected:

```text
128 128
```

No migration.

No collectstatic.

Restart:

```bash
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

### 9.2 Leave Timing Rules

Production `.env`:

```env
SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES=15
SHORT_HALF_LEAVE_GRACE_MINUTES=5
SICK_LEAVE_SAME_DAY_CUTOFF_TIME=11:59
```

Meaning:

```text
Short/Half leave: 15 minute notice, with 5 minute grace.
Sick leave for today: allowed through 11:59 AM; blocked at 12:00 PM.
```

Verify:

```bash
python manage.py shell -c "from django.conf import settings; from App.views import _get_apply_leave_rule_config, _is_after_sick_leave_same_day_cutoff, _get_sick_leave_same_day_cutoff_time; from datetime import time; c=_get_sick_leave_same_day_cutoff_time(); print(settings.SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES, settings.SHORT_HALF_LEAVE_GRACE_MINUTES, settings.SICK_LEAVE_SAME_DAY_CUTOFF_TIME); print(_get_apply_leave_rule_config()); print('11:59 blocked?', _is_after_sick_leave_same_day_cutoff(time(11,59), c)); print('12:00 blocked?', _is_after_sick_leave_same_day_cutoff(time(12,0), c))"
```

Expected:

```text
15 5 11:59
11:59 blocked? False
12:00 blocked? True
```

### 9.3 Multiple Leave Record Emails

Production `.env`:

```env
LEAVE_RECORD_EMAILS=leave@mst-india.com,another-record@mst-india.com
```

Verify:

```bash
python manage.py shell -c "from django.conf import settings; from App.views import get_leave_record_emails; print(settings.LEAVE_RECORD_EMAILS); print(get_leave_record_emails())"
```

Expected example:

```text
leave@mst-india.com
['leave@mst-india.com']
```

### 9.4 Admin Email Job Tracking

Core files:

```text
App/models.py
App/admin.py
App/views.py
App/services/admin_bulk_email_jobs.py
templates/admin/admin_email_job_change_form.html
static/admin/js/admin_email_job_status.js
templates/admin/bulk_onboarding_email_confirm.html
templates/admin/bulk_reminder_email_confirm.html
templates/admin/bulk_user_status_confirm.html
templates/admin/login_lock_action.html
templates/admin/push_subscription_deactivate_confirm.html
```

Requires migrations when job models/choices change.

Requires collectstatic when:

```text
static/admin/js/admin_email_job_status.js
```

changes.

Requires qcluster for queued job execution.

Scheduler also runs:

```text
admin_email_job_recovery every 5 minutes
```

to recover stale/running admin email jobs.

## 10. Backups

### 10.1 Automatic Backup

Automatic backup runs through:

```text
lms_scheduler.service
```

Schedule:

```text
Daily 02:00
```

It calls:

```text
check_and_run_missed_backup()
```

which calls:

```text
run_backup()
```

which uses:

```text
pg_dump
```

for PostgreSQL.

Backup directory:

```bash
~/Leave_Management_MST/backups
```

Check backups:

```bash
ls -lh ~/Leave_Management_MST/backups | tail -20
```

Check scheduler backup logs:

```bash
sudo journalctl -u lms_scheduler --since "2026-07-08 01:55:00" --no-pager
```

### 10.2 Manual Backup

Run:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
python manage_backups.py --backup
```

Or use admin/service console if available.

If it fails with:

```text
No such file or directory: 'pg_dump'
```

then PostgreSQL client tools or service PATH is wrong.

Fix:

```bash
sudo apt install postgresql-client
which pg_dump
sudo systemctl show gunicorn -p Environment
sudo systemctl show lms_scheduler -p Environment
```

Ensure `/usr/bin` is included.

### 10.3 Backup Cleanup

The backup code removes incomplete raw `.sql` files if `pg_dump` fails.

Successful PostgreSQL backup flow:

```text
backup_prod_YYYY-MM-DD_HH-MM-SS.sql
compress to backup_prod_YYYY-MM-DD_HH-MM-SS.zip
delete raw .sql
```

If zero-byte `.sql` files appear, they are failed/incomplete backups and should not be treated as valid.

## 11. Restore

Restore is dangerous. Use only during a controlled maintenance window.

Rules:

```text
Enable maintenance mode first.
Use trusted backup ZIP only.
Understand restore overwrites current database state.
Restart services after restore.
```

Terminal restore:

```bash
python manage_backups.py --restore
```

Service console:

```bash
python manage.py service_console
```

Choose:

```text
11. Database restore
```

PostgreSQL restore requires:

```text
psql
```

Check:

```bash
which psql
psql --version
```

## 12. Service Console

Open:

```bash
python manage.py service_console
```

Menu:

```text
1. User password reset
2. Force password change
3. Login lock manager
4. Employee welcome package
5. Weekly HR report
6. Report export
7. PDF generator
8. Maintenance mode
9. Startup checks
10. Year-end carry forward
11. Database restore
12. Uptime viewer
13. Email delivery logs
14. Push notifications
15. Scheduler viewer
```

Use service console for controlled terminal operations.

## 13. Logs

### 13.1 Systemd Logs

Web:

```bash
sudo journalctl -u gunicorn -n 100 --no-pager
sudo journalctl -u gunicorn -f
```

Background tasks:

```bash
sudo journalctl -u qcluster -n 100 --no-pager
sudo journalctl -u qcluster -f
```

Scheduler:

```bash
sudo journalctl -u lms_scheduler -n 100 --no-pager
sudo journalctl -u lms_scheduler -f
```

Today:

```bash
sudo journalctl -u gunicorn --since "2026-07-08 00:00:00" --no-pager
```

Recent:

```bash
sudo journalctl -u gunicorn --since "10 minutes ago" --no-pager
```

### 13.2 Project Logs

Project logs are under:

```bash
logs/prod/
```

Common folders:

```text
auth/
leave/
analytics/
email/
master/
profile/
security/
maintenance/
backups/
scheduler/
api/
services/
```

List:

```bash
ls -R logs | head -50
```

Tail master log:

```bash
tail -100 logs/prod/master/system_master.log
```

### 13.3 Common Log Messages

Disallowed host:

```text
Invalid HTTP_HOST header: '122.176.33.249:8000'
```

Meaning:

```text
Someone accessed by direct IP/wrong host. Django blocked it.
```

Do not add unknown IPs to `ALLOWED_HOSTS` unless intentional.

Missing bot paths:

```text
Not Found: /robots.txt
Not Found: /sitemap.txt
Not Found: /sitemap_index.xml
```

Meaning:

```text
Bots/scanners. Usually harmless.
```

Scheduler missed by a few seconds:

```text
Run time of job ... was missed by 0:00:02
```

Meaning:

```text
Scheduler ran a few seconds late. Not a problem unless delay is large or recurring.
```

Database EOF during shutdown:

```text
OperationalError: SSL SYSCALL error: EOF detected
```

Meaning:

```text
PostgreSQL connection closed while qcluster/process was reading. If during reboot/shutdown, usually harmless.
```

## 14. Health Checks

### 14.1 Basic App Check

```bash
python manage.py check
```

Expected:

```text
System check identified no issues (0 silenced).
```

### 14.2 Services

```bash
sudo systemctl status postgresql --no-pager
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
```

### 14.3 Scheduler Logs

```bash
sudo journalctl -u lms_scheduler -n 80 --no-pager
```

Look for:

```text
SCHEDULER | STARTED | In-app background scheduler started successfully | Running=True | Jobs=6
```

### 14.4 Qcluster Logs

```bash
sudo journalctl -u qcluster -n 80 --no-pager
```

Look for:

```text
Q Cluster ... running.
Processed ...
```

### 14.5 Backup Status

```bash
ls -lh ~/Leave_Management_MST/backups | tail -20
python manage.py shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

Expected:

```text
'should_run': False
```

when today's backup exists.

## 15. Performance Checks

### 15.1 System Load

```bash
uptime
free -h
df -h
```

Healthy examples:

```text
load average under CPU count
available RAM healthy
disk not near full
```

### 15.2 Top CPU/RAM

```bash
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -20
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -20
```

Common normal processes:

```text
postgres
gunicorn
qcluster
lms_scheduler
systemd-journald
```

### 15.3 Swap

Swap is disk-backed backup memory.

Check:

```bash
free -h
```

If RAM available is high but swap used is also high, the system may still feel slow. Do not clear swap unless available RAM is greater than used swap.

Safe only when:

```text
available RAM > swap used
```

Command:

```bash
sudo swapoff -a
sudo swapon -a
free -h
```

If unsure, do not do it.

### 15.4 Extra Terminal/GUI Processes

```bash
who
tmux ls
pgrep -af "htop|atop|ccze|hollywood|tree /sys/devices|firefox|chrome|chromium|code|gedit|nautilus"
```

If old heavy tools are running, close them.

## 16. Security Deployment Checks

### 16.1 Allowed Hosts

Direct IP requests may log:

```text
DisallowedHost
```

This is good when users should only use the domain.

Production should generally use:

```env
DJANGO_ALLOWED_HOSTS=mstleave.mstlabs.in
DJANGO_CSRF_TRUSTED_ORIGINS=https://mstleave.mstlabs.in
```

### 16.2 HTTPS Cookies

Check:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_HTTPONLY, settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SECURE)"
```

Expected:

```text
True True Lax True
```

### 16.3 Password Max Length

Check:

```bash
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
```

Expected:

```text
128 128
```

### 16.4 Login Rate Limits

Current code protects login with:

```text
5 attempts
15 minute window
15 minute lockout for HR/Employee
30 minute lockout for Admin
```

Long password DoS prevention blocks passwords above:

```text
PASSWORD_INPUT_MAX_LENGTH
```

### 16.5 Clipboard Note

The web app does not use browser clipboard APIs.

Terminal password reset can optionally copy generated passwords using:

```text
Set-Clipboard
pbcopy
xclip
```

This is terminal-only. For sensitive resets, choose not to copy to clipboard.

## 17. Admin Email Jobs

### 17.1 How It Works

Admin bulk email actions create:

```text
AdminEmailJob
AdminEmailJobItem
```

Each selected user gets an item with status:

```text
Queued
Running
Sent
Failed
Skipped
```

The admin job detail page shows live delivery status.

### 17.2 Qcluster Required

Queued jobs need:

```bash
sudo systemctl status qcluster --no-pager
```

If qcluster is down, fallback may run in-process for some helpers, but durable queued processing depends on qcluster and recovery logic.

### 17.3 Recovery

Scheduler runs:

```text
recover_stuck_admin_email_jobs
```

every 5 minutes.

It can retry admin email jobs stuck in running state after worker interruption.

Potential duplicate risk:

```text
Email sent
worker died before marking item Sent
recovery retries
same email may send again
```

This is rare but possible in any retry-after-crash design.

## 18. Static and Browser Cache

If static files changed:

```bash
python manage.py collectstatic
sudo systemctl restart gunicorn
```

If browser still shows old UI:

```text
hard refresh
clear browser cache
check staticfiles timestamp
check nginx/static cache
```

Static update examples:

```bash
git show origin/main:"Leave Management/static/js/my_leave.js" > static/js/my_leave.js
python manage.py collectstatic
sudo systemctl restart gunicorn
```

## 19. Common Production Update Recipes

### 19.1 Python and Template Only

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show origin/main:"Leave Management/App/views.py" > App/views.py
git show origin/main:"Leave Management/templates/my_leave.html" > templates/my_leave.html
python manage.py check
sudo systemctl restart gunicorn
```

### 19.2 Static JS/CSS Change

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show origin/main:"Leave Management/static/js/my_leave.js" > static/js/my_leave.js
python manage.py check
python manage.py collectstatic
sudo systemctl restart gunicorn
```

### 19.3 Migration Change

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show origin/main:"Leave Management/App/models.py" > App/models.py
git show origin/main:"Leave Management/App/migrations/000X_name.py" > App/migrations/000X_name.py
python manage.py migrate
python manage.py check
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

### 19.4 Settings or Env Change

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show origin/main:"Leave Management/leave_management/settings.py" > leave_management/settings.py
nano .env
python manage.py check
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

## 20. Reboot Checklist

Before reboot:

```bash
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
sudo systemctl is-enabled postgresql
```

Expected:

```text
enabled
enabled
enabled
enabled
```

Reboot:

```bash
sudo reboot
```

After reconnect:

```bash
uptime
free -h
sudo systemctl status postgresql --no-pager
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
python manage.py check
```

Check scheduler:

```bash
sudo journalctl -u lms_scheduler -n 80 --no-pager
```

Look for:

```text
SCHEDULER | STARTED
```

## 21. Troubleshooting

### 21.1 App Shows 500

Check:

```bash
sudo journalctl -u gunicorn -n 120 --no-pager
tail -100 logs/prod/django_errors.log
```

Then:

```bash
python manage.py check
```

### 21.2 Admin or User Cannot Log In

Check:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE)"
```

Check user:

```bash
python manage.py shell -c "from App.models import CustomUser; print(list(CustomUser.objects.filter(username='mst_leave_admin').values('username','role','is_active','is_staff','is_superuser','must_change_password')))"
```

### 21.3 Static File Not Updating

Run:

```bash
python manage.py collectstatic
sudo systemctl restart gunicorn
```

Then hard refresh browser.

### 21.4 Backup Fails

Check:

```bash
which pg_dump
pg_dump --version
sudo systemctl show lms_scheduler -p Environment
sudo systemctl show gunicorn -p Environment
```

If missing:

```bash
sudo apt install postgresql-client
```

Ensure `/usr/bin` is in service PATH.

### 21.5 Qcluster Not Processing

Check:

```bash
sudo systemctl status qcluster --no-pager
sudo journalctl -u qcluster -n 100 --no-pager
```

Restart:

```bash
sudo systemctl restart qcluster
```

### 21.6 Scheduler Not Running

Check:

```bash
sudo systemctl status lms_scheduler --no-pager
sudo journalctl -u lms_scheduler -n 100 --no-pager
```

Restart:

```bash
sudo systemctl restart lms_scheduler
```

### 21.7 System Feels Slow

Check:

```bash
uptime
free -h
df -h
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -20
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -20
```

High swap with enough available RAM can make system feel slow, but do not clear swap unless you understand the risk.

## 22. What To Update In This Guide

Whenever any of these change, update this file:

```text
new production service
service name change
systemd command change
new environment variable
new scheduled job
new migration/deploy rule
new backup/restore behavior
new static build step
new package requirement
new security setting
new common troubleshooting pattern
```

## 23. Quick Command Sheet

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show --name-only --pretty=format:"%h %s" origin/main
python manage.py check
python manage.py migrate
python manage.py collectstatic
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
sudo journalctl -u gunicorn -n 100 --no-pager
sudo journalctl -u qcluster -n 100 --no-pager
sudo journalctl -u lms_scheduler -n 100 --no-pager
ls -lh backups | tail -20
```

## 24. Current Known Good Checks

Password max-length:

```bash
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
```

Expected:

```text
128 128
```

Cookie security:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_HTTPONLY, settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SECURE)"
```

Expected:

```text
True True Lax True
```

Backup catch-up:

```bash
python manage.py shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

Expected when today's backup exists:

```text
'should_run': False
```

Services:

```bash
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
```

Expected:

```text
Active: active (running)
```


## 25. Deployment History From Start To Today

This section records the important production changes that shaped the current setup. Keep adding to it whenever a future production change changes deployment behavior.

### 25.1 Initial Production Layout

Current GitHub repository path:

```text
Leave Management/
```

Current production path:

```text
/home/mstleave/Leave_Management_MST/
```

The important detail is that production contains the inside of `Leave Management/`, not the parent folder itself.

That is why production uses commands like:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

instead of blindly using:

```bash
git pull
```

This manual file-copy style is currently intentional because production layout and repository layout do not match perfectly.

### 25.2 Core Production Stack

The project is currently deployed with:

```text
nginx       HTTPS, reverse proxy, static files, media files
gunicorn   Django web app process
postgresql Production database
qcluster   Django-Q background task worker
lms_scheduler Dedicated APScheduler process
```

All critical services are enabled at boot:

```bash
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
sudo systemctl is-enabled postgresql
```

Expected:

```text
enabled
enabled
enabled
enabled
```

### 25.3 SSL And Browser Notifications

Earlier, browser push/system notifications worked in development because localhost is trusted by browsers.

Production needed HTTPS. After SSL was configured for:

```text
https://mstleave.mstlabs.in
```

browser notifications became valid in production.

Related production check:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.CSRF_COOKIE_SECURE)"
```

Expected:

```text
True True
```

### 25.4 Media And Static Production Difference

Development:

```text
Django can serve media files when DEBUG=True.
Static files load directly from the app folders.
```

Production:

```text
nginx must serve media from media/
collectstatic must copy static files to staticfiles/
```

Rule:

```text
If static JS/CSS/images change, run collectstatic.
If templates/Python only change, collectstatic is not needed.
```

Command:

```bash
python manage.py collectstatic
```

### 25.5 Dedicated LMS Scheduler

The scheduler was separated from Gunicorn into its own service:

```text
lms_scheduler.service
```

It runs:

```bash
python manage.py run_lms_scheduler
```

Why this was needed:

```text
Gunicorn workers are for web requests.
Scheduled production jobs need one stable long-running process.
If scheduler lived inside normal web workers, duplicate/missed jobs were more likely.
```

Current scheduler jobs:

```text
year_end_carry_forward       Daily 01:00
nightly_backup               Daily 02:00
weekly_hr_report             Monday 09:00
public_holiday_sync          Monthly day 1 03:00
admin_email_job_recovery     Every 5 minutes
scheduler_keepalive          Every 6 hours
```

The scheduler also runs startup catch-up checks when it starts.

### 25.6 Startup Catch-Up Checks

Startup checks exist so the system can recover after downtime.

When `lms_scheduler.service` starts, it checks:

```text
Was today's backup already created?
Was this week's HR report already sent?
Is year-end carry forward due?
```

If something is due and missing, it runs it.

Example:

```text
If server was off at 02:00, scheduler starts later, sees no backup for today, and creates one.
```

Important:

```text
Startup checks run when the scheduler starts.
They do not repeatedly run every minute while scheduler is already running.
Nightly backup still has its own 02:00 scheduled job.
```

### 25.7 Backup PATH Problem And Fix

Production backup failed earlier with:

```text
[Errno 2] No such file or directory: 'pg_dump'
```

Root cause:

```text
pg_dump existed on the server, but systemd service PATH did not include /usr/bin.
Interactive terminal could find pg_dump.
Gunicorn/lms_scheduler could not.
```

Fix:

```text
Add full PATH override to gunicorn, qcluster, and lms_scheduler.
```

Expected service environment:

```text
PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

Check:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

### 25.8 Backup Self-Healing Cleanup

Backup logic was improved so failed raw `.sql` files are cleaned up.

Why:

```text
A failed pg_dump can create a zero-byte .sql file.
That file must not be confused with a valid backup.
```

Current successful backup flow:

```text
Create raw .sql
Compress it into .zip
Remove raw .sql
Keep .zip as valid backup
```

Current known-good proof:

```text
backup_prod_YYYY-MM-DD_02-00-00.zip is created by scheduler.
```

### 25.9 Runtime Startup Timestamp

The app records startup time in:

```text
runtime/app_startup.json
```

This is mainly for viewing/debugging uptime.

It does not control business logic.

It records timestamps in local production time format after the India-time update.

### 25.10 PostgreSQL Leave Approval Lock Fix

Production showed:

```text
FOR UPDATE cannot be applied to the nullable side of an outer join
```

Cause:

```text
approve_leave/reject_leave used select_for_update with select_related("user", "user__profile").
Profile relation is nullable, so PostgreSQL did not allow locking that outer joined table.
```

Fix:

```python
Leave.objects.select_for_update(of=("self",)).select_related("user", "user__profile")
```

Meaning:

```text
Lock only the Leave row.
Still load user/profile data.
Do not try to lock nullable profile join.
```

This preserved the original reason for locking: prevent two people from approving/rejecting the same leave at the same time.

### 25.11 Notification Symbol Escaping Fix

Some leave type symbols appeared as encoded text like:

```text
&#9684;
```

instead of showing the visual symbol.

Cause:

```text
Frontend inserted already-escaped HTML entity text as plain text.
```

Fix direction:

```text
Use the actual safe symbol/display mapping instead of showing raw encoded entity text.
```

Security note:

```text
Do not blindly inject notification text as HTML.
Only known controlled symbols should render as symbols.
User-controlled text should stay escaped.
```

### 25.12 Leave Apply And Edit Timing Rules

Rules were made configurable from `.env`.

Current values:

```env
SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES=15
SHORT_HALF_LEAVE_GRACE_MINUTES=5
SICK_LEAVE_SAME_DAY_CUTOFF_TIME=11:59
```

Meaning:

```text
Short/Half leave has 15 minute notice and 5 minute grace.
Sick leave for today is allowed at 11:59 AM.
Sick leave for today is blocked from 12:00 PM.
```

Apply and edit flows should use the same backend rule.

Frontend date/time messages should match backend values.

### 25.13 Leave Delete Email

Employee leave deletion was updated so HR/record recipients can be notified when a leave is deleted.

Important design note:

```text
The deleted leave row should not be used as a foreign key in email logs after deletion.
Use copied details/snapshot data instead.
```

This prevents FK/log problems after the leave record is gone.

### 25.14 Multiple Leave Record Emails

Originally there was one record email.

Current setting:

```env
LEAVE_RECORD_EMAILS=leave@mst-india.com
```

It can hold multiple comma-separated recipients:

```env
LEAVE_RECORD_EMAILS=leave@mst-india.com,records@example.com
```

Verify:

```bash
python manage.py shell -c "from django.conf import settings; from App.views import get_leave_record_emails; print(settings.LEAVE_RECORD_EMAILS); print(get_leave_record_emails())"
```

### 25.15 Password Max Length Protection

Long password DoS protection was added.

Current setting:

```env
PASSWORD_INPUT_MAX_LENGTH=128
```

Protection exists in:

```text
login pages
force password change
profile password change
HR create employee
Django admin user creation/password reset
terminal password reset service
Django password validators
```

Verify:

```bash
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
```

Expected:

```text
128 128
```

### 25.16 Production Security Review Notes

Security checks already reviewed:

```text
Server-side template injection: no user-controlled template rendering found.
SQL injection: ORM/parameterized usage; no raw user SQL found.
NoSQL injection: no NoSQL database in this project.
Regex/ReDoS: no user-supplied regex patterns found.
Login replay: cookies are Secure/HttpOnly/SameSite=Lax; CSRF tokens in forms.
Clipboard hijack: no browser clipboard API use; only terminal password reset helper uses optional clipboard.
```

Keep the future rule:

```text
Never build SQL, template names, regex patterns, shell commands, or HTML from raw user input.
```

### 25.17 Current Known-Good Production State

Current known-good checks already observed:

```text
gunicorn active
qcluster active
lms_scheduler active
postgresql active
nightly backup successful
password max length verification output 128 128
cookie security output True True Lax True
system load normal after reboot
```

## 26. Future Change Record Template

Whenever a new production change is made, add an entry here or below it.

Copy this block and fill it:

```text
### YYYY-MM-DD - Change Name

Reason:
What problem or requirement caused this change?

Files changed:
- path/to/file.py
- path/to/template.html
- path/to/static.js

Environment changes:
- NEW_ENV_VAR=value
- Existing value changed from X to Y

Database/migrations:
- Migration needed: yes/no
- Migration file:

Static files:
- collectstatic needed: yes/no

Services restarted:
- gunicorn: yes/no
- qcluster: yes/no
- lms_scheduler: yes/no

Production commands used:
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
python manage.py check

Verification:
- command:
- expected output:
- actual output:

Rollback plan:
- Which files/env values to restore?
- Which services to restart?

Notes:
- Anything confusing that future you should remember.
```

### 26.1 Future Deployment Rule

For every change, answer these before touching production:

```text
1. Did models/migrations change?
2. Did static files change?
3. Did .env/settings change?
4. Does Gunicorn need restart?
5. Does qcluster need restart?
6. Does lms_scheduler need restart?
7. What command proves the change is working?
8. What is the rollback path?
```

### 26.2 Future Feature Checklist

Use this when adding a new feature:

```text
Code:
[ ] Python files copied
[ ] Templates copied
[ ] Static files copied
[ ] New folders created
[ ] Empty __init__.py copied if needed

Database:
[ ] Migrations copied
[ ] migrate run if needed
[ ] no accidental DB reset

Environment:
[ ] .env.example updated
[ ] production .env updated manually
[ ] secrets not committed

Static:
[ ] collectstatic run if static changed
[ ] browser hard refresh tested

Services:
[ ] gunicorn restarted
[ ] qcluster restarted if background code/settings changed
[ ] lms_scheduler restarted if scheduler/startup/job settings changed

Verification:
[ ] python manage.py check passed
[ ] service status active
[ ] relevant shell verification command passed
[ ] logs checked
[ ] UI tested
```

## 27. Production Command Mistakes To Avoid

Do not run `git show` from the home directory:

```bash
cd ~/Leave_Management_MST
```

must be done first.

Do not overwrite `.env` from `.env.example`.

Do not use the wrong service name:

```text
Correct: lms_scheduler
Wrong:   lms_schedule
```

Do not assume terminal PATH equals systemd PATH.

Check:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

Do not treat zero-byte `.sql` files as backups.

Valid production backups are `.zip` files created successfully.

Do not add random IPs to `ALLOWED_HOSTS` just because logs show `DisallowedHost`.

That usually means Django blocked direct-IP scans correctly.

## 28. Guide Maintenance Rule

Whenever you finish a production deployment, update this guide with:

```text
what changed
why it changed
exact files
exact production commands
restart list
verification command and output
known risk or rollback note
```

This is what will keep the guide useful months later when the details are no longer fresh.

## 29. Linux Tuning And Worker Setup Explained For Non-Technical Deployment

This section explains the production Linux setup in simple words. The goal is that even a non-technical person can understand what is running, why it is running, and how to check if it is healthy.

### 29.1 What Is A Service?

A Linux service is a program that systemd keeps running in the background.

For this project, the important services are:

```text
gunicorn        Runs the website/app pages
qcluster        Runs background jobs like queued emails
lms_scheduler   Runs timed jobs like backup at 02:00
postgresql      Stores the database
nginx           Receives browser traffic and forwards it to Gunicorn
```

If you close PuTTY or terminal, these services keep running because systemd owns them.

Check any service:

```bash
sudo systemctl status gunicorn --no-pager
```

Healthy status:

```text
Active: active (running)
```

### 29.2 What Does Auto-Start Mean?

Auto-start means the service starts automatically after server reboot.

Check auto-start:

```bash
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
sudo systemctl is-enabled postgresql
```

Expected:

```text
enabled
enabled
enabled
enabled
```

If any service says `disabled`, enable it:

```bash
sudo systemctl enable SERVICE_NAME
```

Example:

```bash
sudo systemctl enable lms_scheduler
```

### 29.3 Gunicorn Workers Explained

Gunicorn runs the Django website.

Current setup:

```text
1 Gunicorn master process
3 Gunicorn worker processes
```

Meaning:

```text
Master process = manager
Worker processes = actual request handlers
```

A browser request is handled by one worker. With 3 workers, the app can handle multiple users/requests better than a single worker.

Typical production command:

```text
gunicorn --workers 3 --bind unix:/home/mstleave/Leave_Management_MST/gunicorn.sock leave_management.wsgi:application
```

How to see workers:

```bash
sudo systemctl status gunicorn --no-pager
```

You should see one main PID and multiple child Gunicorn worker processes.

Important:

```text
More workers is not always better.
Too many workers use more RAM and can slow a small server.
Current 3 workers is a balanced setup for this VM.
```

### 29.4 Qcluster Workers Explained

Qcluster is Django-Q background worker system.

Current settings come from `leave_management/settings.py`:

```python
"workers": env.int("LMS_Q_WORKERS", default=2)
```

Current default:

```text
2 actual task workers
```

But `systemctl status qcluster` may show around 6 processes.

That does not mean 6 workers. It means:

```text
1 parent/main process
1 guard process
1 monitor process
1 pusher process
2 task worker processes
```

So if you see 6 qcluster processes, that is normal.

Check process count:

```bash
pgrep -af "manage.py qcluster"
pgrep -fc "manage.py qcluster"
```

Normal observed count:

```text
6
```

### 29.5 LMS Scheduler Is Not A Worker Pool

`lms_scheduler` is one long-running scheduler process.

It does not need multiple workers.

It only decides when to run timed jobs:

```text
01:00 year-end check
02:00 backup
Monday 09:00 weekly report
Monthly public holiday sync
Every 5 minutes admin email recovery
Every 6 hours keep-alive log
```

Check:

```bash
sudo systemctl status lms_scheduler --no-pager
```

Normal:

```text
1 python process running manage.py run_lms_scheduler
```

### 29.6 Why We Added PATH Overrides

Problem faced:

```text
Backup worked in terminal but failed from admin/scheduler.
```

Reason:

```text
Terminal PATH and systemd service PATH are different.
```

In terminal:

```bash
which pg_dump
```

worked and showed:

```text
/usr/bin/pg_dump
```

But the service could not find `pg_dump`, so backup failed.

Fix:

```text
We added /usr/bin and other system paths to Gunicorn, qcluster, and lms_scheduler service environments.
```

Check:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

Expected:

```text
PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

### 29.7 What Is A Systemd Override?

A systemd override is an extra service configuration file.

It lets us change one part of a service without editing the original service file directly.

Command:

```bash
sudo systemctl edit gunicorn
```

Example override:

```ini
[Service]
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Then apply it:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

Why override is good:

```text
Original service remains clean.
Only our custom environment is stored in the drop-in override.
```

### 29.8 Wrong Password Attempt Counter

The app has login protection for wrong passwords.

Code file:

```text
App/services/login_lock_service.py
```

Current limits:

```text
Admin:    5 wrong attempts in 15 minutes -> locked for 30 minutes
HR:       5 wrong attempts in 15 minutes -> locked for 15 minutes
Employee: 5 wrong attempts in 15 minutes -> locked for 15 minutes
```

Simple example:

```text
Employee enters wrong password 1 time -> failed counter 1/5
Employee enters wrong password 2 times -> failed counter 2/5
Employee enters wrong password 5 times within 15 minutes -> account login locked for 15 minutes
```

For Admin:

```text
Admin enters wrong password 5 times within 15 minutes -> admin login locked for 30 minutes
```

What happens after lock:

```text
The user cannot log in until the lock expires or admin manually unlocks it.
```

Where to manage it:

```text
Django admin login lock tools
service_console.py login lock manager
terminal direct login lock service
```

Service console:

```bash
python manage.py service_console
```

Then choose:

```text
3. Login lock manager
```

### 29.9 Password Length Counter And Long Password DoS Protection

The app also protects against very long passwords.

Current limit:

```env
PASSWORD_INPUT_MAX_LENGTH=128
```

Why:

```text
Very long passwords can make password hashing expensive.
Attackers can send extremely long passwords repeatedly to slow login.
```

Protection exists on both sides:

```text
Frontend: browser field maxlength stops normal typing/pasting beyond 128 chars.
Backend: server rejects too-long passwords even if attacker bypasses frontend.
```

Verify:

```bash
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
```

Expected:

```text
128 128
```

### 29.10 Linux Load, RAM, Cache, And Swap Explained

Run:

```bash
uptime
free -h
```

`uptime` shows load average:

```text
load average: 0.66, 0.66, 0.68
```

Simple meaning:

```text
Lower is better.
If load stays much higher than CPU count, server may feel slow.
```

`free -h` shows memory:

```text
total      Total RAM
used       RAM used by apps and system
free       Completely unused RAM
buff/cache RAM Linux uses for file cache
available  RAM Linux can still give to apps if needed
swap       Disk memory used when RAM pressure happens
```

Important:

```text
Free RAM being low is not always bad.
Available RAM is more important.
Linux uses free RAM as cache to make the system faster.
```

Swap:

```text
Swap is disk-backed emergency memory.
It is slower than RAM.
High swap can make the server feel slow.
```

We decided not to clear swap unless needed.

Safe swap cleanup rule:

```text
Only clear swap if available RAM is greater than used swap.
```

Command if needed:

```bash
sudo swapoff -a
sudo swapon -a
free -h
```

### 29.11 Extra Linux Processes We Checked

Sometimes slowness is not from the Django app.

We checked for old heavy terminal/GUI tools:

```bash
who
tmux ls
pgrep -af "htop|atop|ccze|hollywood|tree /sys/devices|firefox|chrome|chromium|code|gedit|nautilus"
```

Meaning:

```text
who     shows logged-in terminal sessions
tmux ls shows detached terminal sessions
pgrep   finds running heavy/extra programs
```

Earlier issue:

```text
hollywood/htop/ccze/tmux style processes were running and making Linux feel slow.
```

Fix:

```text
Close/kill unnecessary terminal visual tools.
```

### 29.12 Accounts Daemon Issue

We saw `accounts-daemon` using high CPU/RAM.

This is an Ubuntu system service for user account information.

It is not part of the Django app.

Restart command:

```bash
sudo systemctl restart accounts-daemon
```

If it remains stuck/high after restart, reboot can clear it.

After reboot, the app services auto-started correctly because they were enabled.

### 29.13 Reboot Confidence Check

Before reboot:

```bash
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
sudo systemctl is-enabled postgresql
```

After reboot:

```bash
uptime
free -h
sudo systemctl status postgresql --no-pager
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
```

If all services are active, production is running.

## 30. Problems Faced During Deployment And How We Solved Them

This is the practical history of deployment problems. Keep it because it explains why the current setup exists.

### 30.1 Scheduler Worked In Development But Not Production

Problem:

```text
Scheduler worked on development machine but no backups appeared in production.
```

Cause:

```text
Development server process was different from production Gunicorn.
Production needed a dedicated always-running scheduler service.
```

Fix:

```text
Created lms_scheduler.service running python manage.py run_lms_scheduler.
Enabled it at boot.
```

Verification:

```bash
sudo systemctl status lms_scheduler --no-pager
sudo journalctl -u lms_scheduler -n 80 --no-pager
```

Expected log:

```text
SCHEDULER | STARTED | In-app background scheduler started successfully | Running=True | Jobs=6
```

### 30.2 Backup Failed Even Though PostgreSQL Was Installed

Problem:

```text
Backup failed with pg_dump not found.
```

Cause:

```text
postgresql server package and postgresql-client tools are different.
Also systemd PATH did not include /usr/bin.
```

Fix:

```bash
sudo apt install postgresql-client
sudo systemctl edit gunicorn
sudo systemctl edit lms_scheduler
sudo systemctl edit qcluster
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl restart lms_scheduler
sudo systemctl restart qcluster
```

Expected:

```bash
which pg_dump
pg_dump --version
```

Output:

```text
/usr/bin/pg_dump
pg_dump (PostgreSQL) 16.x
```

### 30.3 Zero-Byte Backup Files Appeared

Problem:

```text
0 byte backup_prod_YYYY-MM-DD.sql files appeared.
```

Cause:

```text
pg_dump failed after creating the raw file.
```

Fix:

```text
Backup cleanup now removes incomplete raw backup files.
Only .zip success files should be treated as valid backup.
```

### 30.4 Admin Backup Failed But Terminal pg_dump Worked

Problem:

```text
Terminal could run pg_dump, but admin backup failed.
```

Cause:

```text
Admin backup runs inside Gunicorn service, not inside your terminal.
Gunicorn had different PATH.
```

Fix:

```text
Gunicorn systemd PATH override added /usr/bin.
```

### 30.5 Public Holiday Sync Ran During Scheduler Start

Observation:

```text
Public holiday sync appeared in qcluster logs after scheduler start.
```

Reason:

```text
Scheduler enqueues one startup public holiday sync task, and also schedules monthly day 1 sync.
```

Not a problem unless it repeats continuously.

### 30.6 Leave Approval Showed Session Expired But Real Error Was Database Lock

Problem shown to user:

```text
Session expired / redirect to dashboard / approval failed.
```

Real production log:

```text
FOR UPDATE cannot be applied to the nullable side of an outer join
```

Cause:

```text
PostgreSQL rejected select_for_update on nullable user__profile outer join.
```

Fix:

```python
select_for_update(of=("self",))
```

Meaning:

```text
Only lock the Leave row, not nullable joined profile row.
```

### 30.7 Static File Changes Did Not Show In Production

Problem:

```text
UI looked old after code push.
```

Cause:

```text
Production serves collected staticfiles, not source static files directly.
```

Fix:

```bash
python manage.py collectstatic
sudo systemctl restart gunicorn
```

Then hard refresh browser.

### 30.8 Media/Profile Photos Production Difference

Problem risk:

```text
Profile photos/media can work in dev but fail in production.
```

Cause:

```text
Django serves media automatically only in development when DEBUG=True.
Production needs nginx media config.
```

Current status:

```text
Media/profile photos were confirmed working in production.
```

### 30.9 Email Links Need PORTAL_BASE_URL

Problem risk:

```text
Emails send but buttons open old/wrong URL.
```

Cause:

```text
Email templates build links from PORTAL_BASE_URL.
```

Production value:

```env
PORTAL_BASE_URL=https://mstleave.mstlabs.in
```

### 30.10 qcluster Down Or Restarted During Task

Problem risk:

```text
Queued background task may be delayed or stuck if qcluster stops.
```

What happens:

```text
If task is still queued in Django-Q table, qcluster can pick it after restart.
If custom business record says Running but worker died, app-specific recovery may be needed.
```

Fix added for admin email jobs:

```text
Scheduler runs admin_email_job_recovery every 5 minutes.
It can reset stale Running admin email jobs and enqueue fresh processing.
```

Risk:

```text
If email was sent but worker died before marking item Sent, recovery may resend it.
This duplicate risk is small but possible.
```

### 30.11 Wrong Service Name Mistake

Problem:

```bash
sudo systemctl restart lms_schedule
```

failed with:

```text
Unit lms_schedule.service not found.
```

Correct service:

```bash
sudo systemctl restart lms_scheduler
```

### 30.12 Git Command From Wrong Directory

Problem:

```text
git show origin/main:"Leave Management/manage_backups.py" > manage_backups.py
fatal: not a git repository
```

Cause:

```text
Command was run from home directory, not project directory.
```

Fix:

```bash
cd ~/Leave_Management_MST
```

then run git commands.

### 30.13 Direct IP Requests In Logs

Problem seen:

```text
Invalid HTTP_HOST header: '122.176.33.249:8000'
```

Meaning:

```text
Someone or some bot tried to access server by IP/wrong host.
Django blocked it.
```

Do not fix by adding random IP to `ALLOWED_HOSTS` unless you intentionally want public IP access.

### 30.14 Browser Notification Needed HTTPS

Problem:

```text
Notifications worked on localhost but not production.
```

Cause:

```text
Browsers require HTTPS for service worker push notifications outside localhost.
```

Fix:

```text
Network team added SSL and production was configured with HTTPS.
```

### 30.15 Login Lock And Wrong Password Counter Confusion

Problem:

```text
Need to know if wrong password attempts are counted and locked.
```

Current behavior:

```text
Each portal has a failed-attempt counter.
Counters are stored in Django cache.
Successful login clears failure state.
Too many failures create temporary lock.
Admin can manually lock/unlock too.
```

Limits:

```text
Admin:    5 attempts / 15 min window / 30 min lock
HR:       5 attempts / 15 min window / 15 min lock
Employee: 5 attempts / 15 min window / 15 min lock
```

### 30.16 Long Password Attack Protection

Problem:

```text
Very long password login attempts can waste server CPU during password hashing.
```

Fix:

```text
PASSWORD_INPUT_MAX_LENGTH=128
Frontend maxlength + backend validation + Django password validator.
```

### 30.17 System Felt Slow After Many Terminal Tools

Problem:

```text
Linux and application felt slow.
```

Checks used:

```bash
uptime
free -h
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -20
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -20
pgrep -af "htop|atop|ccze|hollywood|tree /sys/devices|firefox|chrome|chromium|code|gedit|nautilus"
```

Findings:

```text
Some decorative/monitoring terminal tools were running earlier.
accounts-daemon also used high memory/CPU once.
```

Fix:

```text
Close unnecessary tools.
Restart accounts-daemon or reboot if system process is stuck.
```

After reboot:

```text
App services auto-started.
Load returned to normal.
```

## 31. Non-Technical Full Deployment Walkthrough

This is the plain-English version of deploying a change.

### 31.1 Before You Start

Ask:

```text
What changed?
Was it Python?
Was it HTML/template?
Was it static JS/CSS?
Was it database model/migration?
Was it .env/settings?
Was it scheduler/background code?
```

Then use the decision table in section 8.

### 31.2 Log In To Production

Use PuTTY or terminal and connect to the server.

Then:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
```

You should see:

```text
(venv) mstleave@mstleave-VM:~/Leave_Management_MST$
```

### 31.3 Fetch Latest GitHub Code

```bash
git fetch origin
```

See what changed:

```bash
git show --name-only --pretty=format:"%h %s" origin/main
```

This tells you which files need to be copied.

### 31.4 Copy Changed Files

Example for Python file:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

Example for template:

```bash
git show origin/main:"Leave Management/templates/my_leave.html" > templates/my_leave.html
```

Example for static JS:

```bash
git show origin/main:"Leave Management/static/js/my_leave.js" > static/js/my_leave.js
```

Example for new folder/file:

```bash
mkdir -p App/scripts
git show origin/main:"Leave Management/App/scripts/__init__.py" > App/scripts/__init__.py
git show origin/main:"Leave Management/App/scripts/validators.py" > App/scripts/validators.py
```

### 31.5 Update `.env` Only If Needed

Open:

```bash
nano .env
```

Add/change only the required variable.

Never overwrite `.env` with `.env.example`.

### 31.6 Run Django Check

```bash
python manage.py check
```

Expected:

```text
System check identified no issues (0 silenced).
```

### 31.7 Run Migrations If Needed

Only if migrations/model schema changed:

```bash
python manage.py migrate
```

If no migrations changed, skip this.

### 31.8 Run collectstatic If Needed

Only if static files changed:

```bash
python manage.py collectstatic
```

Type:

```text
yes
```

If only Python/template changed, skip this.

### 31.9 Restart Correct Services

Always restart Gunicorn for web changes:

```bash
sudo systemctl restart gunicorn
```

Restart qcluster if background jobs/settings changed:

```bash
sudo systemctl restart qcluster
```

Restart scheduler if scheduler/startup/backup/timed job/settings changed:

```bash
sudo systemctl restart lms_scheduler
```

### 31.10 Confirm Services Are Alive

```bash
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
```

Look for:

```text
Active: active (running)
```

### 31.11 Check Logs

```bash
sudo journalctl -u gunicorn -n 80 --no-pager
sudo journalctl -u qcluster -n 80 --no-pager
sudo journalctl -u lms_scheduler -n 80 --no-pager
```

If logs only show normal restarts and no traceback, deployment is likely fine.

### 31.12 Test In Browser

Open:

```text
https://mstleave.mstlabs.in
```

Test the exact feature you changed.

If static UI is old:

```text
Hard refresh browser.
Confirm collectstatic was run.
```

## 32. Simple Mental Model Of The Whole Production System

Think of production like this:

```text
nginx is the front gate.
gunicorn is the web office.
postgresql is the record room.
qcluster is the background worker team.
lms_scheduler is the alarm clock.
backups are the safety copies.
.env is the private settings drawer.
staticfiles is the public CSS/JS/image shelf.
media is the uploaded user file shelf.
logs are the CCTV footage.
```

When something breaks:

```text
Website page problem -> check gunicorn logs.
Background email/task problem -> check qcluster logs.
Scheduled backup/report problem -> check lms_scheduler logs.
Database problem -> check postgresql and Django traceback.
Static UI problem -> run collectstatic and hard refresh.
Uploaded image problem -> check nginx media config and media folder.
Login lock problem -> check login lock manager/service console.
```

## 33. Copy-Paste Linux Setup Code Used For Production Services

This section keeps the Linux setup code in one place. Use it when rebuilding the server, checking service files, or explaining how production was created.

Important production paths:

```text
Project directory: /home/mstleave/Leave_Management_MST
Virtualenv:        /home/mstleave/Leave_Management_MST/venv
Gunicorn socket:   /home/mstleave/Leave_Management_MST/gunicorn.sock
Static root:       /home/mstleave/Leave_Management_MST/staticfiles
Media root:        /home/mstleave/Leave_Management_MST/media
Backups:           /home/mstleave/Leave_Management_MST/backups
```

### 33.1 Base Linux Packages

Fresh server package setup:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip postgresql postgresql-client nginx git
sudo apt install xclip
```

Why these are needed:

```text
python3/python3-venv/python3-pip -> Django runtime and virtualenv
postgresql -> database server
postgresql-client -> pg_dump and psql for backup/restore
nginx -> public web server and SSL/static/media layer
git -> fetch files from GitHub
xclip -> optional terminal clipboard helper for password reset
```

Verify PostgreSQL client tools:

```bash
which pg_dump
which psql
pg_dump --version
psql --version
```

Expected shape:

```text
/usr/bin/pg_dump
/usr/bin/psql
pg_dump (PostgreSQL) 16.x
psql (PostgreSQL) 16.x
```

### 33.2 Project Virtualenv Setup

```bash
cd /home/mstleave/Leave_Management_MST
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Install Playwright Chromium for weekly report PDF generation:

```bash
python -m playwright install chromium
```

Verify:

```bash
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); print('playwright chromium ok'); b.close(); p.stop()"
```

Expected:

```text
playwright chromium ok
```

### 33.3 Gunicorn Service File

Service file location:

```text
/etc/systemd/system/gunicorn.service
```

Typical content:

```ini
[Unit]
Description=gunicorn daemon for Leave Management
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=mstleave
Group=www-data
WorkingDirectory=/home/mstleave/Leave_Management_MST
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/mstleave/Leave_Management_MST/venv/bin/gunicorn --workers 3 --bind unix:/home/mstleave/Leave_Management_MST/gunicorn.sock leave_management.wsgi:application
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Apply:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl start gunicorn
sudo systemctl status gunicorn --no-pager
```

Restart after web code/settings/template changes:

```bash
sudo systemctl restart gunicorn
```

### 33.4 Gunicorn PATH Override

If the main service file already exists and only PATH must be fixed, use override:

```bash
sudo systemctl edit gunicorn
```

Put this above the comment area:

```ini
[Service]
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Apply:

```bash
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
sudo systemctl show gunicorn -p Environment
```

Expected:

```text
Environment=PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

### 33.5 Qcluster Service File

Service file location:

```text
/etc/systemd/system/qcluster.service
```

Typical content:

```ini
[Unit]
Description=Django Q Cluster for Leave Management
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=mstleave
Group=mstleave
WorkingDirectory=/home/mstleave/Leave_Management_MST
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/mstleave/Leave_Management_MST/venv/bin/python /home/mstleave/Leave_Management_MST/manage.py qcluster
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Apply:

```bash
sudo systemctl daemon-reload
sudo systemctl enable qcluster
sudo systemctl start qcluster
sudo systemctl status qcluster --no-pager
```

Restart after background task code/settings changes:

```bash
sudo systemctl restart qcluster
```

### 33.6 Qcluster PATH Override

```bash
sudo systemctl edit qcluster
```

Put:

```ini
[Service]
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Apply:

```bash
sudo systemctl daemon-reload
sudo systemctl restart qcluster
sudo systemctl show qcluster -p Environment
```

### 33.7 LMS Scheduler Service File

Service file location:

```text
/etc/systemd/system/lms_scheduler.service
```

Typical content:

```ini
[Unit]
Description=LMS Scheduler for Leave Management
After=network.target postgresql.service
Requires=postgresql.service

[Service]
User=mstleave
Group=mstleave
WorkingDirectory=/home/mstleave/Leave_Management_MST
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/home/mstleave/Leave_Management_MST/venv/bin/python /home/mstleave/Leave_Management_MST/manage.py run_lms_scheduler
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Apply:

```bash
sudo systemctl daemon-reload
sudo systemctl enable lms_scheduler
sudo systemctl start lms_scheduler
sudo systemctl status lms_scheduler --no-pager
```

Restart after scheduler/startup/backup/timed job code/settings changes:

```bash
sudo systemctl restart lms_scheduler
```

### 33.8 LMS Scheduler PATH Override

```bash
sudo systemctl edit lms_scheduler
```

Put:

```ini
[Service]
Environment="PATH=/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
```

Apply:

```bash
sudo systemctl daemon-reload
sudo systemctl restart lms_scheduler
sudo systemctl show lms_scheduler -p Environment
```

### 33.9 Nginx Production Server Block

The repo has a Docker-style sample at:

```text
Leave Management/nginx/nginx.conf
```

Production nginx is normally a host-level config, not Docker `web:8000` upstream.

Typical production server block shape:

```nginx
server {
    listen 80;
    server_name mstleave.mstlabs.in;

    client_max_body_size 20M;

    location /static/ {
        alias /home/mstleave/Leave_Management_MST/staticfiles/;
    }

    location /media/ {
        alias /home/mstleave/Leave_Management_MST/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/home/mstleave/Leave_Management_MST/gunicorn.sock;
    }
}
```

If SSL is handled directly in nginx, production also needs HTTPS/443 config. If SSL is handled by the network team/reverse proxy, keep nginx aligned with their setup.

Check nginx:

```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl status nginx --no-pager
```

### 33.10 Static And Media Folder Commands

Create folders if missing:

```bash
cd /home/mstleave/Leave_Management_MST
mkdir -p staticfiles
mkdir -p media
mkdir -p backups
```

Collect static:

```bash
source venv/bin/activate
python manage.py collectstatic
```

Type:

```text
yes
```

Check folder sizes:

```bash
du -sh staticfiles media backups logs
```

### 33.11 Service Enable And Reboot Safety Code

Enable services:

```bash
sudo systemctl enable postgresql
sudo systemctl enable gunicorn
sudo systemctl enable qcluster
sudo systemctl enable lms_scheduler
sudo systemctl enable nginx
```

Check enabled:

```bash
sudo systemctl is-enabled postgresql
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
sudo systemctl is-enabled nginx
```

Expected:

```text
enabled
enabled
enabled
enabled
enabled
```

After reboot, check:

```bash
uptime
free -h
sudo systemctl status postgresql --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
```

### 33.12 Logs Command Set

Gunicorn:

```bash
sudo journalctl -u gunicorn -n 100 --no-pager
sudo journalctl -u gunicorn -f
```

Qcluster:

```bash
sudo journalctl -u qcluster -n 100 --no-pager
sudo journalctl -u qcluster -f
```

LMS scheduler:

```bash
sudo journalctl -u lms_scheduler -n 100 --no-pager
sudo journalctl -u lms_scheduler -f
```

Nginx:

```bash
sudo journalctl -u nginx -n 100 --no-pager
sudo tail -100 /var/log/nginx/error.log
sudo tail -100 /var/log/nginx/access.log
```

Project logs:

```bash
cd /home/mstleave/Leave_Management_MST
find logs -type f | sort | head -50
tail -100 logs/prod/master/system_master.log
```

### 33.13 Worker Count Check Code

Gunicorn:

```bash
pgrep -af "gunicorn"
```

Expected idea:

```text
1 master + 3 workers
```

Qcluster:

```bash
pgrep -af "manage.py qcluster"
pgrep -fc "manage.py qcluster"
```

Expected observed count:

```text
6 total qcluster processes for 2 configured workers
```

Scheduler:

```bash
pgrep -af "run_lms_scheduler"
```

Expected:

```text
1 scheduler process
```

### 33.14 Production Deployment Command Skeleton

Use this pattern for most deployments:

```bash
cd /home/mstleave/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show --name-only --pretty=format:"%h %s" origin/main
python manage.py check
sudo systemctl restart gunicorn
sudo systemctl status gunicorn --no-pager
```

Add these only when needed:

```bash
python manage.py migrate
python manage.py collectstatic
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

## 34. Development Vs Production Differences

Many things work in development but need extra setup in production. This section lists those differences clearly.

### 34.1 Summary Table

```text
Area                 Development behavior                         Production behavior
Static JS/CSS        Loaded directly from static/                 Must run collectstatic into staticfiles/
Media uploads        Django can serve when DEBUG=True             nginx must serve /media/
HTTPS                localhost allowed for many browser APIs       Real HTTPS required
Push notifications   localhost works                              HTTPS + VAPID + service worker required
Scheduler            Can appear to work in dev process             Needs lms_scheduler.service
Background jobs      Can run fallback/in-process sometimes         Needs qcluster.service for durable work
Database             SQLite may be used                            PostgreSQL is used
Backups              May use sqlite/dev backup behavior            PostgreSQL needs pg_dump
Restore              May be simple locally                         PostgreSQL needs psql and maintenance window
Email links          localhost link okay                           PORTAL_BASE_URL must be production domain
Cookies/CSRF         Secure cookies may be off                     Secure cookies/CSRF trusted origins required
Static cache         Browser may see latest file quickly           collectstatic/browser cache/nginx may show old UI
Service PATH         Terminal PATH usually complete                systemd PATH must include /usr/bin
Workers              runserver single process                      Gunicorn has master + workers
Reboot               dev is manual                                 production services must be enabled
```

### 34.2 Static Files: Works In Dev, Old UI In Production

Development:

```text
Django finds static/js/my_leave.js directly.
```

Production:

```text
nginx serves staticfiles/js/my_leave.js.
```

If you change `static/js/my_leave.js` and forget `collectstatic`, production may still show old JavaScript.

Fix:

```bash
python manage.py collectstatic
sudo systemctl restart gunicorn
```

Then hard refresh browser.

### 34.3 Media Files: Works In Dev, Broken Images In Production

Development:

```text
DEBUG=True can serve uploaded media through Django URL helpers.
```

Production:

```text
nginx must map /media/ to /home/mstleave/Leave_Management_MST/media/
```

If employee photos/profile images do not load in production, check nginx media config and file permissions.

### 34.4 HTTPS And Browser Notifications

Development:

```text
localhost is treated as secure by browser for service workers.
```

Production:

```text
Browser push notification requires HTTPS.
```

If HTTPS is missing, push subscription/notification can fail even if code is correct.

### 34.5 Scheduler: Dev Can Look Fine, Production Needs Service

Development:

```text
You may run Django directly and scheduler code may appear to start.
```

Production:

```text
Gunicorn workers should not own the scheduler.
A dedicated lms_scheduler.service must run it.
```

Check:

```bash
sudo systemctl status lms_scheduler --no-pager
```

Without scheduler:

```text
nightly backup will not run
weekly report may not send
public holiday sync may not run on schedule
admin email recovery will not run every 5 minutes
```

### 34.6 Background Tasks: Dev Fallback Vs Production qcluster

Development:

```text
A helper may run fallback/in-process if qcluster is unavailable.
```

Production:

```text
Durable background processing needs qcluster.service.
```

If qcluster is stopped:

```text
queued admin emails can delay
background push/email tasks can delay
some fallback may run only while the web request is alive
if the web process stops mid-task, fallback work can be lost
```

Check:

```bash
sudo systemctl status qcluster --no-pager
```

### 34.7 Database: SQLite Dev Vs PostgreSQL Production

Development can use SQLite for easy local testing.

Production uses PostgreSQL.

This matters because PostgreSQL is stricter. Example issue faced:

```text
FOR UPDATE cannot be applied to the nullable side of an outer join
```

That appeared in production but may not appear the same way in SQLite dev.

Rule:

```text
For database locking, concurrency, and select_for_update behavior, trust PostgreSQL production behavior more than SQLite development behavior.
```

### 34.8 Backup: Dev File Backup Vs PostgreSQL pg_dump

Development backup can be simple.

Production PostgreSQL backup needs:

```text
pg_dump
systemd PATH containing /usr/bin
write permission to backups/
```

Check:

```bash
which pg_dump
sudo systemctl show lms_scheduler -p Environment
```

### 34.9 Email Links: Localhost Vs Production Domain

Development:

```text
http://localhost:8000
```

Production:

```text
https://mstleave.mstlabs.in
```

If `PORTAL_BASE_URL` is wrong, emails still send but buttons open wrong links.

Production value:

```env
PORTAL_BASE_URL=https://mstleave.mstlabs.in
```

### 34.10 Cookies And CSRF

Development may allow HTTP.

Production should use:

```text
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_HTTPONLY=True
SESSION_COOKIE_SAMESITE=Lax
```

Check:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_HTTPONLY, settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SECURE)"
```

Expected:

```text
True True Lax True
```

If CSRF trusted origins are wrong, login/forms can show CSRF/session style errors.

Production value:

```env
DJANGO_CSRF_TRUSTED_ORIGINS=https://mstleave.mstlabs.in
```

### 34.11 Service PATH Difference

Development terminal:

```bash
which pg_dump
```

may work.

Production service:

```text
Gunicorn/lms_scheduler may still fail if systemd PATH is short.
```

Fix is service override PATH.

This was one of the real problems we faced.

### 34.12 Worker Difference

Development:

```bash
python manage.py runserver
```

usually means one simple process.

Production:

```text
nginx -> gunicorn master -> 3 workers
qcluster -> multiple child processes
lms_scheduler -> one dedicated scheduler process
```

That is why logs can appear from multiple PIDs.

Multiple Gunicorn workers can also record startup/uptime around the same time because each worker boots Django.

### 34.13 Reboot Difference

Development:

```text
You manually start the server when needed.
```

Production:

```text
Services must auto-start after reboot.
```

Check:

```bash
sudo systemctl is-enabled gunicorn qcluster lms_scheduler postgresql nginx
```

### 34.14 Performance Difference

Development has few users and small data.

Production has:

```text
real database data
multiple users
email sending
background jobs
scheduled backups
browser assets served by nginx
logs growing over time
```

If production feels slow, check:

```bash
uptime
free -h
df -h
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%cpu | head -20
ps -eo pid,ppid,cmd,%mem,%cpu --sort=-%mem | head -20
```

### 34.15 Permission Difference

Development files are owned by your local user.

Production files are accessed by:

```text
mstleave user
www-data group for Gunicorn/nginx access where needed
postgres user for database
```

If uploads, backups, static, or logs fail, check ownership/permissions.

Useful checks:

```bash
ls -ld media staticfiles backups logs
ls -lh backups | tail -20
```

### 34.16 Timezone Difference

Production uses India time behavior for app-facing timestamps.

Scheduler logs and runtime startup should be read using IST expectations.

If checking journalctl with time filters, use absolute date/time:

```bash
sudo journalctl -u lms_scheduler --since "2026-07-08 01:55:00" --no-pager
```

Do not rely on `today 01:55` if journalctl rejects it.

## 35. Production Setup Code Checklist For A Fresh Rebuild

Use this as a high-level fresh production rebuild script. Read each line before running it.

### 35.1 Install Packages

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip postgresql postgresql-client nginx git xclip
```

### 35.2 Prepare Project

```bash
cd /home/mstleave
mkdir -p Leave_Management_MST
cd Leave_Management_MST
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

### 35.3 Prepare Runtime Folders

```bash
mkdir -p runtime
mkdir -p media
mkdir -p staticfiles
mkdir -p backups
mkdir -p logs
```

### 35.4 Prepare `.env`

```bash
nano .env
```

Must include production values for:

```text
DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=mstleave.mstlabs.in
DJANGO_CSRF_TRUSTED_ORIGINS=https://mstleave.mstlabs.in
PORTAL_BASE_URL=https://mstleave.mstlabs.in
DB_ENGINE=postgresql
DB_NAME=leave_management
DB_USER=leave_user
DB_PASSWORD=real-password
DB_HOST=localhost
DB_PORT=5432
EMAIL_HOST
EMAIL_PORT
EMAIL_USE_TLS
EMAIL_USE_SSL
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL
LEAVE_DESK_FROM_EMAIL
LEAVE_RECORD_EMAILS
PASSWORD_INPUT_MAX_LENGTH=128
SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES=15
SHORT_HALF_LEAVE_GRACE_MINUTES=5
SICK_LEAVE_SAME_DAY_CUTOFF_TIME=11:59
WEB_PUSH_VAPID_PUBLIC_KEY
WEB_PUSH_VAPID_PRIVATE_KEY
WEB_PUSH_VAPID_SUBJECT
```

### 35.5 Database Setup

Create PostgreSQL DB/user according to `.env`, then:

```bash
python manage.py migrate
python manage.py createsuperuser
```

Admin profile/role repair if needed:

```bash
python manage.py shell -c "from django.utils import timezone; from App.models import CustomUser, Profile; u=CustomUser.objects.get(username='mst_leave_admin'); u.role='Admin'; u.is_staff=True; u.is_superuser=True; u.must_change_password=False; u.is_active=True; u.save(); Profile.objects.update_or_create(user=u, defaults={'role':'Admin','department':'Management','date_of_joining':timezone.localdate(),'employee_id':'MST_Admin-0001'}); print('Admin fixed:', u.username, u.role, u.is_staff, u.is_superuser, u.is_active)"
```

### 35.6 Static Files

```bash
python manage.py collectstatic
```

### 35.7 Create Services

Create/check:

```text
/etc/systemd/system/gunicorn.service
/etc/systemd/system/qcluster.service
/etc/systemd/system/lms_scheduler.service
```

Then:

```bash
sudo systemctl daemon-reload
sudo systemctl enable gunicorn
sudo systemctl enable qcluster
sudo systemctl enable lms_scheduler
sudo systemctl start gunicorn
sudo systemctl start qcluster
sudo systemctl start lms_scheduler
```

### 35.8 Configure Nginx

Create nginx server block pointing to:

```text
/home/mstleave/Leave_Management_MST/gunicorn.sock
/home/mstleave/Leave_Management_MST/staticfiles/
/home/mstleave/Leave_Management_MST/media/
```

Then:

```bash
sudo nginx -t
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### 35.9 Final Checks

```bash
python manage.py check
sudo systemctl status postgresql --no-pager
sudo systemctl status nginx --no-pager
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_HTTPONLY, settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SECURE)"
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
```

Expected security/password outputs:

```text
True True Lax True
128 128
```
