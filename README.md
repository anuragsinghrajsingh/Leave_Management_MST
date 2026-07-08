# Leave Management MST

A production-ready Django leave management system for MS Technology. It handles employee leave requests, HR approval workflows, admin operations, communications, notifications, reports, backups, and production scheduling.

This repository is not only the application code. It also contains living documentation for operating the production server safely.

## Current Documentation Map

Read these files in this order when you are unsure:

| File | Purpose |
|---|---|
| `PROJECT_START_HERE.md` | First file to open. Quick memory, command map, and where to go next. |
| `PROJECT_GUIDE.md` | Practical feature guide: roles, workflows, services, admin tools, logs, common tasks. |
| `PROJECT_DEPLOYMENT_GUIDE.md` | Full production deployment guide: Linux services, workers, nginx, static/media, backups, troubleshooting. |
| `PROJECT_DEEP_DIVE_BOOK.md` | Long technical book with file/function references and deep debugging notes. |
| `Leave Management/App/management/production_setup/README.md` | Secret/key generation helpers for production setup. |

If a new feature is added, update the relevant docs using the templates in `PROJECT_DEPLOYMENT_GUIDE.md` and `PROJECT_START_HERE.md`.

## What The System Does

The system supports three main roles:

| Role | Main Work |
|---|---|
| Admin | Django admin, users, leaves, holidays, WFH days, logs, backups, reports, maintenance, email jobs, communication center. |
| HR | HR dashboard, employee management, leave approval/rejection, reports, communications, notifications. |
| Employee | Apply/edit/delete pending leaves, view balance, profile, communications, notifications, forced password change. |

Core leave types:

```text
Short
Half
Sick
Earned
Unpaid
```

Core request statuses:

```text
Pending
Approved
Rejected
```

## Current Production Shape

Production project directory:

```text
/home/mstleave/Leave_Management_MST
```

Public portal:

```text
https://mstleave.mstlabs.in
```

Important production services:

| Service | Purpose |
|---|---|
| `nginx` | HTTPS/front layer, static files, media files, reverse proxy. |
| `gunicorn` | Django web app, admin, HR/employee pages, API endpoints. |
| `postgresql` | Production database. |
| `qcluster` | Django-Q background jobs, queued admin emails, async work. |
| `lms_scheduler` | Dedicated scheduler for backups, reports, holiday sync, recovery jobs. |

Current worker/process shape:

```text
Gunicorn: 1 master + 3 workers
qcluster: about 6 processes total, with 2 configured task workers
lms_scheduler: 1 scheduler process
```

## GitHub Layout Vs Production Layout

GitHub stores the Django project inside:

```text
Leave Management/
```

Production stores the contents of that folder directly under:

```text
/home/mstleave/Leave_Management_MST/
```

Example mapping:

```text
GitHub:     Leave Management/App/views.py
Production: App/views.py
```

That is why production updates often use:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

Do not blindly run `git pull` on production unless the production layout is intentionally changed to match the repository layout.

## Major Features

### Leave Workflow

- Employee applies leave from the employee portal.
- HR approves/rejects from HR pages.
- Admin can perform controlled admin workflow actions.
- PostgreSQL row locks protect approval/rejection against double processing.
- Leave balances and audits are maintained.
- Delete/edit flows send notifications and preserve audit context.

### Leave Rules

Short leave:

```text
Same day only
Max 2 hours
Working hours only: 10:00 AM to 7:00 PM
Max 2 per month
Deducts 0.25 day equivalent
```

Half leave:

```text
Same day only
Max 4 hours
Working hours only: 10:00 AM to 7:00 PM
Max 1 per month
Deducts 0.5 day equivalent
```

Full-day leaves:

```text
Sick
Earned
Unpaid
```

Full-day leaves can use WFH bridge, weekend, public holiday, and company holiday calculations.

Current configurable timing rules:

```env
SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES=15
SHORT_HALF_LEAVE_GRACE_MINUTES=5
SICK_LEAVE_SAME_DAY_CUTOFF_TIME=11:59
```

Meaning:

```text
Short/Half leave has 15 minute notice with 5 minute grace.
Sick leave for today is allowed through 11:59 AM and blocked from 12:00 PM.
```

### Notifications And Communications

- HR pending leave notifications.
- Employee leave decision notifications.
- Communication center for direct messages and announcements.
- Read/seen state for communication and leave notifications.
- Browser push notifications through service worker and VAPID keys.
- HTTPS is required for production browser push notifications.

### Email System

Email types include:

```text
leave applied
leave updated
leave deleted
leave approved/rejected
welcome/onboarding
forced password
password reset
reminder
login lock/unlock
weekly HR report
backup failure alert
```

Important email, portal, and security settings:

```env
EMAIL_HOST=
EMAIL_PORT=
EMAIL_USE_TLS=
EMAIL_USE_SSL=
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
DEFAULT_FROM_EMAIL=
LEAVE_DESK_FROM_EMAIL=
LEAVE_RECORD_EMAILS=
PORTAL_BASE_URL=
ADMIN_EMAIL=
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SESSION_COOKIE_SECURE=True
```

`LEAVE_RECORD_EMAILS` supports multiple comma-separated record recipients.

Important Web Push settings:

```env
WEB_PUSH_VAPID_PUBLIC_KEY=
WEB_PUSH_VAPID_PRIVATE_KEY=runtime/webpush_private_key.pem
WEB_PUSH_VAPID_SUBJECT=mailto:admin@example.com
```

Important qcluster tuning settings:

```env
LMS_Q_WORKERS=2
LMS_Q_TIMEOUT=120
LMS_Q_RETRY=300
LMS_Q_QUEUE_LIMIT=100
LMS_Q_BULK=20
```

### Admin Email Jobs

Bulk admin email jobs use database-backed tracking:

```text
AdminEmailJob
AdminEmailJobItem
```

Statuses are tracked per job and per recipient.

The scheduler runs admin email recovery every 5 minutes to recover stale running jobs.

### Backup And Restore

Backups use:

```text
manage_backups.py
pg_dump
zip compression
```

Valid production backups are `.zip` files in:

```text
/home/mstleave/Leave_Management_MST/backups
```

Restore uses `psql` and must be done carefully during maintenance.
Runtime/generated folders used by production:

```text
runtime/             startup state, Web Push private key path, public holiday cache
backups/             compressed database backups and weekly report tracker
logs/                application/service/security/email logs
media/               uploaded profile/media files
generated_pdfs/      weekly HR report PDFs
generated_reports/   admin/report export files
staticfiles/         collected production static files
```

### Scheduler

The dedicated scheduler service runs:

```bash
python manage.py run_lms_scheduler
```

Current scheduled jobs:

```text
startup catch-up checks
nightly backup at 02:00
year-end carry forward check at 01:00
weekly HR report Monday 09:00
public holiday sync monthly day 1 at 03:00
admin email job recovery every 5 minutes
scheduler keep-alive every 6 hours
```

### Security Features

- HTTPS production cookies.
- CSRF trusted origins.
- Wrong-password login lock counters.
- Password max length protection against long-password DoS attempts.
- Password complexity checks for password changes.
- Role-based access for Admin, HR, and Employee.
- Audit logs for admin/service actions.
- Controlled admin confirmation screens.
- No known user-controlled SQL/template/regex execution path from the current code review.

Current login lock limits:

```text
Admin:    5 wrong attempts in 15 minutes -> 30 minute lockout
HR:       5 wrong attempts in 15 minutes -> 15 minute lockout
Employee: 5 wrong attempts in 15 minutes -> 15 minute lockout
```

Current password input max length:

```env
PASSWORD_INPUT_MAX_LENGTH=128
```

## Local Development Setup

From the repository root on Windows/Linux/macOS:

```bash
python -m venv venv
```

Activate on Windows PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

Activate on Linux/macOS:

```bash
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r "Leave Management/requirements.txt"
```

Create `.env` inside `Leave Management/` using `Leave Management/.env.example` as reference.

Run migrations:

```bash
python "Leave Management/manage.py" migrate
```

Create superuser:

```bash
python "Leave Management/manage.py" createsuperuser
```

Run web server:

```bash
python "Leave Management/manage.py" runserver
```

Optional local qcluster:

```bash
python "Leave Management/manage.py" qcluster
```

Optional local scheduler:

```bash
python "Leave Management/manage.py" run_lms_scheduler
```

## Production Deployment Quick Path

Use the detailed guide in `PROJECT_DEPLOYMENT_GUIDE.md`. The short version is:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show --name-only --pretty=format:"%h %s" origin/main
python manage.py check
```

Copy changed files with `git show`, then run only what is needed:

```bash
python manage.py migrate        # only when migrations changed
python manage.py collectstatic  # only when static files changed
sudo systemctl restart gunicorn
sudo systemctl restart qcluster        # if background code/settings changed
sudo systemctl restart lms_scheduler   # if scheduler/startup/job code/settings changed
```

Check services:

```bash
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
sudo systemctl status postgresql --no-pager
sudo systemctl status nginx --no-pager
```

## Important Production Checks

Django check:

```bash
python manage.py check
```

Cookie security:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_HTTPONLY, settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SECURE)"
```

Expected:

```text
True True Lax True
```

Password max length:

```bash
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
```

Expected:

```text
128 128
```

Backup check:

```bash
ls -lh ~/Leave_Management_MST/backups | tail -20
python manage.py shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

Service PATH check:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

Expected PATH includes:

```text
/home/mstleave/Leave_Management_MST/venv/bin
/usr/bin
```

## Dev Vs Production Reminder

Development and production behave differently:

| Area | Development | Production |
|---|---|---|
| Static files | Django reads source static files | Must run `collectstatic` |
| Media files | Django can serve in DEBUG | nginx must serve `/media/` |
| Notifications | localhost can work | HTTPS required |
| Database | SQLite can be used | PostgreSQL is stricter |
| Backups | local/simple | needs `pg_dump` and service PATH |
| Scheduler | may appear in dev process | must run `lms_scheduler.service` |
| Background jobs | fallback may hide issues | must run `qcluster.service` |
| Reboot | manual restart | services must be enabled |

## Keeping Documentation Updated

Whenever you add a feature or fix production behavior, update docs in this order:

```text
README.md                       if the feature changes the public project overview
PROJECT_START_HERE.md           if daily commands/navigation changed
PROJECT_GUIDE.md                if workflow/feature behavior changed
PROJECT_DEPLOYMENT_GUIDE.md     if deployment/services/env/static/migration behavior changed
PROJECT_DEEP_DIVE_BOOK.md       if debugging/function reference needs current-state notes
production_setup/README.md      if secret/env generation changed
```

Use the future-change template in `PROJECT_DEPLOYMENT_GUIDE.md` when documenting production changes.

## License And Ownership

Proprietary internal project for MS Technology. Keep secrets, database passwords, email passwords, and private keys out of git.

## Detailed Feature Matrix

| Area | What exists now | Main files | Production owner |
|---|---|---|---|
| Role selection and login | Admin, HR, Employee entry flows with loading screens | `App/views.py`, `templates/*login*.html`, `static/js/login_form.js` | `gunicorn` |
| Login lock security | Wrong password counters, temporary locks, manual admin lock/unlock | `App/services/login_lock_service.py`, `App/views.py`, `App/admin.py` | `gunicorn`; optional email via `qcluster` |
| Password protection | Complexity checks, forced change, max input length 128 | `App/scripts/validators.py`, `App/forms.py`, `App/views.py`, `App/admin.py` | `gunicorn` |
| Employee leave apply | Short/Half/Sick/Earned/Unpaid rules and overlap checks | `App/views.py`, `App/models.py`, `templates/apply_leave.html`, `static/js/apply_leave.js` | `gunicorn` |
| My Leave page | Filters, edit/delete pending leave, history display | `templates/my_leave.html`, `static/js/my_leave.js`, `App/views.py` | `gunicorn`; static needs `collectstatic` |
| HR manage all | Employee cards, summaries, approvals, details | `templates/manage_all.html`, `static/js/manage_all.js`, `App/views.py` | `gunicorn`; static needs `collectstatic` |
| HR approve/reject | PostgreSQL-safe leave row lock | `App/views.py` | `gunicorn`, PostgreSQL |
| Admin panel | Users, leave, holidays, WFH, reports, logs, service actions | `App/admin.py`, `templates/admin/*` | `gunicorn` |
| Admin bulk emails | Job/item tracking, live status, stale recovery | `App/services/admin_bulk_email_jobs.py`, `App/admin.py`, `static/admin/js/admin_email_job_status.js` | `gunicorn`, `qcluster`, `lms_scheduler` |
| Communications | Direct messages, announcements, read/seen tracking | `App/models.py`, `App/views.py`, `static/js/communication_panel.js` | `gunicorn`, optional push/email |
| Browser push | Service worker subscriptions and test pushes | `App/services/push_notifications.py`, `static/js/push_notifications.js`, `static/js/service-worker.js` | HTTPS, `gunicorn`, `qcluster` |
| Weekly reports | HTML/PDF/email HR report | `App/services/weekly_report_service.py`, `App/services/pdf_generator.py` | `gunicorn`, `lms_scheduler`, Playwright |
| Backups | PostgreSQL pg_dump to compressed zip | `manage_backups.py`, `App/services/startup_checks.py` | `lms_scheduler`, `gunicorn` admin action |
| Restore | PostgreSQL restore through psql | `manage_backups.py`, `App/services/restore_db.py` | controlled terminal/admin maintenance |
| Public holidays | Google calendar sync with cache/fallback | `App/services/public_holidays.py` | `qcluster`, `lms_scheduler` |
| Uptime | App startup timestamp and display | `App/services/uptime_tracker.py`, `runtime/app_startup.json` | `gunicorn`, `lms_scheduler` |

## Main URLs And Screens

| URL/path | User | Purpose |
|---|---|---|
| `/` | All | Loading entry screen |
| `/portal/` | All | Role selection |
| `/employee-login/` and `/employee-login/form/` | Employee | Employee login loading/form |
| `/hr-login/` and `/hr-login/form/` | HR | HR login loading/form |
| `/admin-login/` and `/admin-login/form/` | Admin | Custom admin login loading/form |
| `/dashboard/` | Employee | Employee dashboard |
| `/apply_leave/` | Employee | Apply leave |
| `/my_leave/` | Employee | View/filter/edit/delete own leaves |
| `/profile/` | Logged-in users | Profile/password change |
| `/force-password-change/` | HR/Employee | Required password update |
| `/hr-dashboard/` | HR | HR dashboard |
| `/manage-all/` | HR | Employee/leave management |
| `/employees/` | HR | Employee creation/list management |
| `/reports/` | HR | Reports and weekly snapshot |
| `/admin/` | Admin | Django admin and service consoles |
| `/service-worker.js` | Browser | Push notification service worker |

## Important Files By Work Type

When you want to change something, start with the likely owner:

```text
Login behavior                 -> App/views.py, App/services/login_lock_service.py, templates/*login.html
Password rules                 -> App/scripts/validators.py, App/forms.py, App/admin.py, templates/auth/force_password_change.html
Leave apply/edit/delete         -> App/views.py, App/models.py, static/js/apply_leave.js, static/js/my_leave.js
HR approvals                   -> App/views.py, templates/manage_all.html, static/js/manage_all.js
Admin actions                  -> App/admin.py, templates/admin/*
Bulk admin emails              -> App/services/admin_bulk_email_jobs.py, static/admin/js/admin_email_job_status.js
Background task fallback        -> App/services/background_tasks.py
Scheduler jobs                 -> App/services/scheduler.py, App/management/commands/run_lms_scheduler.py
Startup catch-up               -> App/services/startup_checks.py
Backup/restore                 -> manage_backups.py, App/services/restore_db.py
Weekly report/PDF              -> App/services/weekly_report_service.py, App/services/pdf_generator.py
Push notifications             -> App/services/push_notifications.py, static/js/push_notifications.js, static/js/service-worker.js
Production settings/env         -> leave_management/settings.py, .env, .env.example
```

## Add A New Feature Without Breaking Docs

For every meaningful feature, record this in the relevant docs:

```text
Feature name:
Who uses it: Admin / HR / Employee / background / scheduler
Main files changed:
New env variables:
New migration: yes/no
Static changed: yes/no
Production commands needed:
How to verify:
Known risks:
Rollback:
```

If the feature affects production deployment, update `PROJECT_DEPLOYMENT_GUIDE.md` first.
