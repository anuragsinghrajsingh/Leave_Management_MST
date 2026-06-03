# Leave Management Project Guide

This guide is the working memory for the Leave Management project. It explains what the system does, how the major features work, how production is deployed, and how to troubleshoot the issues we have already seen.

## 1. Project Identity

Local workspace:

```text
C:\Users\anura\Desktop\Work\Leave Management
```

Production workspace:

```text
/home/mstleave/Leave_Management_MST
```

GitHub stores files under:

```text
Leave Management/App/...
Leave Management/templates/...
Leave Management/static/...
```

Production is flattened, so the same files live as:

```text
App/...
templates/...
static/...
```

Example deployment mapping:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
git show origin/main:"Leave Management/static/js/manage_all.js" > static/js/manage_all.js
```

Important project-level files:

```text
manage.py              Django management entrypoint
manage_backups.py      Database backup/restore utility
App/                   Main Django app
leave_management/      Django project settings/urls/wsgi/asgi
templates/             HTML templates
static/                Source static JS/CSS/images
staticfiles/           Collected production static output
backups/               Database backup ZIP files
runtime/               Runtime state/cache files
logs/                  Runtime logs
```

## 2. Main Roles

The system uses a custom user model:

```python
CustomUser.role = "Admin" | "HR" | "EMPLOYEE"
```

Admin:

- Uses Django admin.
- Can manage users, profiles, leave records, holidays, WFH days, audit logs, reports, backups, maintenance mode, system health, email jobs, and communication center records.
- `CustomUser.save()` automatically sets `is_staff=True` for Admin.
- Admin users do not need forced password change.

HR:

- Uses HR portal.
- Can view employees, manage leave approvals/rejections, manage employee details, view reports, use HR communications, and receive HR leave notifications.

Employee:

- Uses employee portal.
- Can apply leave, edit/delete pending leave, view balance, update profile, receive messages/notifications, and complete forced password change.

## 3. Core Models

Important models in `App/models.py`:

- `CustomUser`: login user with role and `must_change_password`.
- `Profile`: user profile, employee ID, department, joining date, phone, address, profile photo, bio.
- `Leave`: leave request with type, dates, times, status, reason, reviewer, deduction source, WFH bridge override fields.
- `LeaveBalance`: sick/earned/total leave tracking.
- `LeaveBalanceAudit`: balance change history.
- `AdminAuditLog`: generic admin audit table. Fields are capped/truncated to avoid DB length crashes.
- `EmailDeliveryLog`: email send/fail tracking.
- `AdminEmailJob` and `AdminEmailJobItem`: bulk admin email job and per-user delivery status.
- `PushSubscription`: browser push subscription records.
- `CompanyHoliday`: admin-defined company holidays.
- `WorkFromHomeDay`: WFH days used by bridge calculations.
- `YearEndCarryForwardRun`: protects year-end carry-forward from running twice.
- `Communication`: direct messages and announcements.
- `CommunicationRead`, `CommunicationSeen`: read/seen state for communications.
- `LeaveNotificationRead`, `LeaveNotificationSeen`: read/seen state for leave notifications.
- Proxy models like `EmployeeCommunication`, `HRCommunication`, `AdminCommunicationCenter` organize admin screens.
- Log/control proxy models like `SystemHealthControl`, `ServiceActionControl`, `BackupRestoreControl`, `ReportExportControl`.

## 4. Leave Workflow

Employee applies leave from `apply_leave`.

Main leave types:

```text
Short
Half
Unpaid
Sick
Earned
```

Statuses:

```text
Pending
Approved
Rejected
```

Short leave:

- Same day only.
- Max 2 hours.
- Working hours only: 10 AM to 7 PM.
- Max 2 short leaves per month.
- Deducts 0.25 day equivalent.

Half leave:

- Same day only.
- Max 4 hours.
- Working hours only: 10 AM to 7 PM.
- Max 1 half leave per month.
- Deducts 0.5 day equivalent.

Full-day leave:

- `Sick`, `Earned`, `Unpaid`.
- Date-based.
- Works with WFH bridge and holiday/weekend rules.

When leave is applied:

- The system validates type/date/time/reason.
- It checks monthly limits for Short/Half.
- It checks overlapping leave.
- It calculates balance/deduction.
- It creates leave record.
- It notifies HR by in-app notification and push/email where configured.

When HR approves:

- Only `Pending` leave can be approved.
- Leave status becomes `Approved`.
- `approved_at` and `reviewed_by` are set.
- Employee is notified.

When HR rejects:

- Only `Pending` leave can be rejected.
- Rejection reason is required and capped.
- Balance is restored/reconciled where needed.
- Employee is notified.

Important PostgreSQL lock fix:

```python
Leave.objects.select_for_update(of=("self")).select_related("user", "user__profile")
```

This locks only the `Leave` row while still loading user/profile. It avoids:

```text
FOR UPDATE cannot be applied to the nullable side of an outer join
```

## 5. WFH, Holiday, Weekend Rules

WFH bridge rules apply only to full-day leave types:

```python
FULL_DAY_LEAVE_TYPES = {"Unpaid", "Sick", "Earned"}
```

They do not apply to:

```text
Short
Half
```

Public holidays:

- Fetched from Google India public holiday calendar.
- Cached in `runtime/public_holidays_india.json`.
- If network fails, fallback holidays are still available:
  - Republic Day
  - Independence Day
  - Gandhi Jayanti

Company holidays:

- Stored in DB.
- Managed by admin.
- Can block leave or affect calculations depending on workflow.

WFH days:

- Stored in DB.
- Managed by admin.
- Used to bridge full-day leave ranges where applicable.

## 6. Notification System

Notification types:

- HR pending leave notifications.
- Employee leave decision notifications.
- Communication notifications.
- Browser push notifications.

Read/seen state:

- Leave notification read state is stored separately for HR and Employee proxy models.
- Communication read/seen state is stored separately.
- Admin edits to important leave details can reset read/seen state so users see updated leave notifications again.

Sound behavior:

- Sound can trigger when the browser tab is open and polling.
- If the browser is closed, normal polling/sound cannot run.
- Push notifications require browser permission and HTTPS.

Production HTTPS:

- Required for browser service worker push notifications.
- SSL was configured by the network team and tested.

Notification symbol issue:

- Literal HTML entities like `&#9684;` appeared in a notification menu.
- Fixed by using Unicode values and normalizing any copied entity text before rendering.

## 7. Communication Center

The communication system supports:

- Employee to HR direct messages.
- HR to Employee direct messages.
- Admin announcements.
- HR announcements where allowed.
- Admin communication center feed.

Admin can edit/delete communication records in admin. If an announcement/message is edited, users can be informed again by resetting read/seen state and push/badge behavior depending on the specific flow.

Incoming vs outgoing:

- For a recipient, a message sent by someone else is incoming.
- Edited incoming messages can become unread again for that recipient.

Admin communication center templates:

```text
templates/admin/admin_communication_center.html
templates/admin/includes/admin_communication_table.html
static/js/communication_panel.js
```

## 8. Email System

Main email types:

- Welcome/onboarding email.
- Forced password email.
- Clear forced password email.
- Password reset email.
- Admin reminder email.
- Login lock email.
- Login unlock email.
- Leave applied email.
- Leave approved/rejected email.
- Weekly HR report email.
- Backup failure alert.

Email delivery logs:

- Stored in `EmailDeliveryLog`.
- Tracks subject, recipients, status, type, related user, related leave, triggered by, metadata.

Important email settings:

```text
EMAIL_HOST
EMAIL_PORT
EMAIL_USE_TLS
EMAIL_USE_SSL
EMAIL_HOST_USER
EMAIL_HOST_PASSWORD
DEFAULT_FROM_EMAIL
PORTAL_BASE_URL
```

`PORTAL_BASE_URL` is used inside email buttons/links. If it is wrong, emails can send successfully but links open the wrong URL.

## 9. Admin Bulk Email Jobs

Admin bulk email jobs use:

```text
AdminEmailJob
AdminEmailJobItem
App/services/admin_bulk_email_jobs.py
templates/admin/admin_email_job_change_form.html
static/admin/js/admin_email_job_status.js
```

Supported job types include:

- onboarding
- force password
- reminder
- login lock
- login unlock

Job status:

```text
queued
running
completed
completed_with_failures
failed
```

Item status:

```text
queued
running
sent
failed
skipped
```

Flow:

```text
Admin selects users
-> confirmation page shows per-user preview
-> job is created
-> items are created
-> qcluster processes the job
-> admin status page auto-refreshes
-> each user shows sent/failed/skipped
```

Recovery:

- `recover_stuck_admin_email_jobs()` checks stale running items.
- Runs every 5 minutes from `lms_scheduler`.
- Resets stale running items back to queued.
- Status message becomes:

```text
Retried after stale running state.
```

Duplicate email edge risk:

- If an email was sent but the worker died before marking it sent, recovery may retry it.
- Timeout is used to reduce this risk.
- Sent items are not touched.

## 10. Password And Login Security

Forced password change:

- Admin can set `must_change_password=True` for HR/Employee.
- User is redirected to `/force-password-change/`.
- Password fields are hidden by default.
- Eye toggle works.
- Password rules are hidden while confirming password.

Password rules:

- At least 8 characters.
- One uppercase letter.
- One number.
- One symbol.
- New and confirm passwords must match.

Login lock:

- Failed login attempts are tracked by portal/user/IP.
- Users can be locked after repeated wrong password attempts.
- Lockout email can include:
  - portal
  - lock duration
  - retry time
  - reason/source

Admin lock/unlock:

- Admin can lock/unlock selected users.
- Confirmation pages show which users will change and which are already in that state.
- Admin can choose email sending where implemented.

Terminal password reset helper:

```text
App/services/user_password_reset_service.py
```

Linux clipboard helper uses:

```text
xclip
```

If `xclip` is missing, only copy-to-clipboard fails. Password can still print.

Production now has:

```text
/usr/bin/xclip
```

## 11. Admin Panel Features

Important admin actions and screens:

- Create/edit Admin, HR, Employee.
- Profile inline.
- Audit reason fields.
- Activate/deactivate users.
- Force/clear password change.
- Lock/unlock login.
- Resend onboarding email.
- Send reminder email.
- Export selected employee archive PDFs.
- Admin leave workflow:
  - approve selected leaves
  - reject selected leaves
  - sync selected leaves
  - delete selected leaves with workflow
  - recalculate selected leave balances
- Company holiday CSV upload and preview.
- WFH bridge impact preview.
- Leave balance adjustment.
- Report export center.
- Log viewer.
- System health.
- Service actions.
- Backup restore.
- Maintenance mode.

Important templates:

```text
templates/admin/bulk_user_status_confirm.html
templates/admin/bulk_onboarding_email_confirm.html
templates/admin/bulk_reminder_email_confirm.html
templates/admin/login_lock_action.html
templates/admin/push_subscription_deactivate_confirm.html
templates/admin/admin_leave_workflow_confirm.html
templates/admin/system_health.html
templates/admin/service_actions.html
templates/admin/backup_restore.html
templates/admin/maintenance_mode.html
```

## 12. Audit System

Audit logs are central to admin safety.

Main audit models:

- `AdminAuditLog`
- `UserAdminAudit`
- `ProfileAdminAudit`
- `LeaveAdminAudit`
- `HolidayAdminAudit`
- `WorkFromHomeAdminAudit`
- `DeleteAdminAudit`
- `EmployeeCommunicationAudit`
- `HRCommunicationAudit`
- `AdminCommunicationAudit`
- Read/seen audit proxy models.

Important DB crash fix:

- Audit log short fields were expanded/capped.
- Long values are truncated before saving.
- Purpose: avoid errors like:

```text
value too long for type character varying(20)
```

Admin audit values should not crash pages even if reason/action/message is long.

## 13. Background Task System

File:

```text
App/services/background_tasks.py
```

Flow:

```text
enqueue_background_task()
-> try Django-Q/qcluster first
-> if qcluster not active, fallback to ThreadPoolExecutor
```

Thread fallback:

```python
ThreadPoolExecutor(max_workers=8)
```

Important limitation:

- qcluster jobs are DB-backed.
- Thread fallback is in-process.
- If Gunicorn dies while fallback thread is running, that fallback work can be lost.
- Admin email jobs have DB recovery to reduce this risk.

qcluster is used for:

- admin bulk email jobs
- public holiday sync tasks
- push/email side effects queued from app flows

Check qcluster:

```bash
sudo systemctl status qcluster
pgrep -af "manage.py qcluster"
pgrep -fc "manage.py qcluster"
```

Normal process count is around 6:

- main
- guard
- workers
- monitor
- pusher

## 14. Scheduler

Production scheduler service:

```text
lms_scheduler.service
```

Command:

```bash
/home/mstleave/Leave_Management_MST/venv/bin/python /home/mstleave/Leave_Management_MST/manage.py run_lms_scheduler
```

Scheduler jobs:

```text
startup_catchup              Runs once when scheduler starts
year_end_carry_forward       Daily 01:00
nightly_backup               Daily 02:00
weekly_hr_report             Monday 09:00
public_holiday_sync          Monthly day 1 03:00, plus once at startup
admin_email_job_recovery     Every 5 minutes
scheduler_keepalive          Every 6 hours
```

Check scheduler:

```bash
sudo systemctl status lms_scheduler
sudo journalctl -u lms_scheduler -n 100 --no-pager
sudo journalctl -u lms_scheduler -f
```

Known journal timestamp note:

Some systems do not parse:

```bash
--since "today 01:55"
```

Use exact date:

```bash
sudo journalctl -u lms_scheduler --since "2026-05-31 01:55:00" --no-pager
```

## 15. Backup And Restore

File:

```text
manage_backups.py
```

Backup flow:

```text
run_backup()
-> backup_postgres()
-> pg_dump creates raw .sql
-> compress_file() creates .zip
-> raw .sql removed
-> cleanup_old_backups()
```

Final valid backup is `.zip`:

```text
backup_prod_YYYY-MM-DD_HH-MM-SS.zip
```

Failed raw `.sql` cleanup:

- If `pg_dump` fails after creating raw `.sql`, the code now deletes the incomplete raw `.sql`.
- This prevents `0 byte .sql` leftovers.

Backup directory:

```text
/home/mstleave/Leave_Management_MST/backups
```

Check backup files:

```bash
ls -lh ~/Leave_Management_MST/backups | tail -10
```

Check scheduler backup logs:

```bash
sudo journalctl -u lms_scheduler --since "2026-05-31 01:55:00" --no-pager
```

Successful backup log example:

```text
BACKUP | POSTGRES | Running pg_dump
BACKUP | COMPRESS
BACKUP | SUCCESS | Created: backup_prod_2026-05-31_02-00-00.zip
STARTUP_CHECKS | BACKUP | Backup result=True
```

Required tools:

```bash
which pg_dump
which psql
pg_dump --version
psql --version
```

Production fixed tools:

```text
/usr/bin/pg_dump
/usr/bin/psql
```

Restore:

- Restore uses `psql`.
- Restore overwrites current database.
- Enable maintenance mode before restore.
- Use only during controlled maintenance.

## 16. Production Services

Main services:

```text
nginx
gunicorn
postgresql
qcluster
lms_scheduler
```

Service purpose:

```text
nginx          HTTPS, static/media, reverse proxy
gunicorn       Django web app/admin/API
postgresql     Database
qcluster       Django-Q background workers
lms_scheduler  Scheduled jobs
```

All-in-one status:

```bash
sudo systemctl status nginx gunicorn postgresql qcluster lms_scheduler
```

Enabled check:

```bash
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
```

PATH overrides:

All Python services should include:

```text
/home/mstleave/Leave_Management_MST/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
```

Check:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

Why PATH matters:

- The venv path remains first, so Python/Django use the project virtualenv.
- `/usr/bin` allows system tools like `pg_dump`, `psql`, `xclip`.

## 17. Production Deployment

Always start in project directory:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
```

Always fetch before loading pushed code:

```bash
git fetch origin
```

Load a specific file:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

Examples:

```bash
git show origin/main:"Leave Management/manage_backups.py" > manage_backups.py
git show origin/main:"Leave Management/App/services/uptime_tracker.py" > App/services/uptime_tracker.py
git show origin/main:"Leave Management/static/js/manage_all.js" > static/js/manage_all.js
```

Run check:

```bash
python manage.py check
```

Run migrations if models/migrations changed:

```bash
python manage.py migrate
```

Run collectstatic if static JS/CSS/images changed:

```bash
python manage.py collectstatic
```

Restart services depending on file type:

```text
Python web code          restart gunicorn
Background task code     restart qcluster
Scheduler code           restart lms_scheduler
Static JS/CSS            collectstatic, then restart gunicorn if needed
Templates                restart gunicorn
Models/migrations        migrate, restart gunicorn/qcluster/scheduler as needed
```

Common restart commands:

```bash
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

Verify loaded file:

```bash
grep -n "some known text" path/to/file.py
```

If `grep` does not show the new line, usually `git fetch origin` was missed.

## 18. Static Files

Production serves collected static files from:

```text
staticfiles/
```

If you change source static files in:

```text
static/js/
static/css/
static/admin/js/
static/admin/css/
```

then run:

```bash
python manage.py collectstatic
sudo systemctl restart gunicorn
```

Symptoms when collectstatic is missed:

- Old JavaScript behavior still appears.
- UI fix works locally but not production.
- Password eye toggle/static UI does not update.
- Notification symbol fix does not appear.

## 19. Runtime Files And Logs

Runtime startup tracker:

```text
runtime/app_startup.json
```

Purpose:

- Only for uptime display/reporting.
- Does not control app features.

Current expected format:

```json
{
  "started_at": "2026-05-30T14:26:32.195169+05:30",
  "timezone": "Asia/Kolkata"
}
```

If missing:

- App still works.
- Uptime display may show `Not tracked yet`.

Log folders include:

```text
logs/master/
logs/security/
logs/auth/
logs/leave/
logs/email/
logs/backups/
logs/services/
logs/scheduler/
logs/api/
logs/profile/
logs/analytics/
```

Admin log viewer can read these from Django admin.

## 20. Reports

Reports include:

- HR dashboard/report page.
- Weekly HR report preview/download/email.
- Report export center.
- CSV/PDF generation for different report types.

Weekly report:

```text
App/services/weekly_report_service.py
App/services/pdf_generator.py
templates/emails/weekly_hr_report.html
templates/emails/weekly_hr_report_cover.html
```

PDF generation uses Playwright Chromium:

```python
sync_playwright()
```

Check production:

```bash
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); print('playwright chromium ok'); b.close(); p.stop()"
```

Known good output:

```text
playwright chromium ok
```

## 21. Production Troubleshooting

Backup failed with `pg_dump` missing:

```bash
which pg_dump
sudo systemctl show gunicorn -p Environment
sudo systemctl show lms_scheduler -p Environment
```

Backup check:

```bash
ls -lh ~/Leave_Management_MST/backups | tail -10
sudo journalctl -u lms_scheduler --since "YYYY-MM-DD 01:55:00" --no-pager
```

qcluster stopped:

```bash
sudo systemctl status qcluster
sudo systemctl restart qcluster
pgrep -fc "manage.py qcluster"
```

Scheduler stopped:

```bash
sudo systemctl status lms_scheduler
sudo systemctl restart lms_scheduler
sudo journalctl -u lms_scheduler -n 100 --no-pager
```

Static change not visible:

```bash
python manage.py collectstatic
sudo systemctl restart gunicorn
```

Email job stuck:

```bash
python manage.py shell -c "from App.services.admin_bulk_email_jobs import recover_stuck_admin_email_jobs; print(recover_stuck_admin_email_jobs())"
```

PostgreSQL nullable join lock error:

```text
FOR UPDATE cannot be applied to the nullable side of an outer join
```

Fix pattern:

```python
select_for_update(of=("self",))
```

Notification symbol shows code like `&#9684;`:

- Check static JS loaded.
- Run collectstatic.
- Check `manage_all.js` normalization.

Session/CSRF/session expired confusion:

- Check gunicorn logs first.
- It may be a server error, not CSRF.

```bash
sudo journalctl -u gunicorn -n 200 --no-pager
```

## 22. Recent Major Fixes And Decisions

Important implementation history:

- Audit log fields expanded/capped/truncated to avoid DB length crashes.
- Fresh DB can use one clean initial migration after resetting DB, but migration files are still how Django creates tables.
- Forced password page fixed:
  - passwords hidden by default
  - confirm password toggle works
  - rules hide while confirming
- Welcome/onboarding email support extended to HR/Admin as optional.
- Admin communication center editable by admin.
- Admin can edit/delete HR/employee communication records from admin.
- Edited messages/announcements can become unread again.
- Leave notification read/seen reset added for important admin leave edits.
- WFH bridge behavior documented as full-day only.
- Admin email job tracking added:
  - job + per-user item tracking
  - live status auto-refresh
  - queued/running/sent/failed/skipped
- Admin bulk action confirmation pages improved:
  - force/clear password
  - lock/unlock
  - activate/deactivate
  - onboarding
  - reminder
  - push subscription deactivate
- Login lock/unlock emails added for admin actions.
- Wrong-password lockout email includes lock duration/retry time.
- Background fallback ThreadPoolExecutor increased to 8 workers.
- Admin email stale job recovery added.
- Dedicated `lms_scheduler.service` created.
- Scheduler startup records uptime with `force=True`.
- Production service PATH fixed for:
  - gunicorn
  - lms_scheduler
  - qcluster
- `pg_dump`, `psql`, `xclip`, Playwright Chromium verified.
- Backup failed raw `.sql` cleanup added.
- Uptime JSON changed to Indian time `+05:30` plus timezone label.
- HR approve/reject fixed with `select_for_update(of=("self",))`.
- Notification symbol/entity display issue fixed.

## 23. Command Cheat Sheet

Go to production project:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
```

Fetch latest GitHub state:

```bash
git fetch origin
```

Load one file:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

Django check:

```bash
python manage.py check
```

Migrate:

```bash
python manage.py migrate
```

Collect static:

```bash
python manage.py collectstatic
```

Restart services:

```bash
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

Service status:

```bash
sudo systemctl status nginx gunicorn postgresql qcluster lms_scheduler
```

Enabled check:

```bash
sudo systemctl is-enabled gunicorn
sudo systemctl is-enabled qcluster
sudo systemctl is-enabled lms_scheduler
```

PATH check:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

qcluster process count:

```bash
pgrep -af "manage.py qcluster"
pgrep -fc "manage.py qcluster"
```

Scheduler logs:

```bash
sudo journalctl -u lms_scheduler -n 100 --no-pager
sudo journalctl -u lms_scheduler -f
```

Gunicorn logs:

```bash
sudo journalctl -u gunicorn -n 200 --no-pager
```

Backup files:

```bash
ls -lh ~/Leave_Management_MST/backups | tail -10
```

Backup catch-up status:

```bash
python manage.py shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

Manual admin email recovery:

```bash
python manage.py shell -c "from App.services.admin_bulk_email_jobs import recover_stuck_admin_email_jobs; print(recover_stuck_admin_email_jobs())"
```

Check production tools:

```bash
which pg_dump
which psql
which xclip
pg_dump --version
psql --version
```

Check Playwright:

```bash
python -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(headless=True); print('playwright chromium ok'); b.close(); p.stop()"
```

Fix admin user after fresh DB:

```bash
python manage.py shell -c "from django.utils import timezone; from App.models import CustomUser, Profile; u=CustomUser.objects.get(username='mst_leave_admin'); u.role='Admin'; u.is_staff=True; u.is_superuser=True; u.must_change_password=False; u.is_active=True; u.save(); Profile.objects.update_or_create(user=u, defaults={'role':'Admin','department':'Management','date_of_joining':timezone.localdate(),'employee_id':'MST_Admin-0001'}); print('Admin fixed:', u.username, u.role, u.is_staff, u.is_superuser, u.is_active)"
```

## 24. Simple Rule For Future Changes

Before deploying, ask:

```text
Did I change Python code?
Did I change models/migrations?
Did I change static JS/CSS?
Did I change scheduler/background code?
Did I change templates?
```

Then run the matching commands:

```text
Python/template web change -> python manage.py check -> restart gunicorn
Model/migration change      -> migrate -> restart services
Static change               -> collectstatic -> restart gunicorn
qcluster task change        -> restart qcluster
scheduler change            -> restart lms_scheduler
backup utility change       -> restart gunicorn and lms_scheduler
```

When in doubt, check logs immediately after restart.

# Part II: Detailed Book-Style Guide

This part is meant to be read slowly when you forget how the project works. The earlier sections are a quick operating guide. This section explains the thinking behind each feature, the normal user flow, the production flow, and the code modules behind it.

## 25. How To Think About The Whole System

The project is a Django web application with three layers:

```text
Browser/UI
-> Django views/admin/API
-> Models/services/database/background jobs
```

In production, requests flow like this:

```text
User browser
-> nginx
-> gunicorn
-> Django app
-> PostgreSQL
```

Background work flows like this:

```text
Django view/admin action
-> enqueue_background_task()
-> qcluster if running
-> ThreadPoolExecutor fallback if qcluster is not detected
```

Scheduled work flows like this:

```text
lms_scheduler.service
-> APScheduler
-> startup checks / backup / weekly report / year-end / public holidays / recovery
```

The most important idea:

```text
Views handle user requests.
Services handle reusable business logic.
Models store data and validation.
Admin classes expose management tools.
Systemd services keep production processes running.
```

If something breaks, first decide which layer it belongs to:

```text
Page not loading             -> gunicorn/nginx/view/template/static
Email not sent               -> email settings/qcluster/email logs
Background job stuck         -> qcluster/AdminEmailJob/lms_scheduler recovery
Backup failed                -> lms_scheduler/manage_backups/pg_dump/PATH
Leave calculation wrong      -> leave_breakdown/admin_leave_workflow/views
Admin action wrong           -> admin.py/templates/admin/services
Static behavior old          -> collectstatic/browser cache/staticfiles
```

## 26. Daily Operating Map

Use this when you are managing the live system.

Morning check:

```bash
sudo systemctl status nginx gunicorn postgresql qcluster lms_scheduler
ls -lh ~/Leave_Management_MST/backups | tail -10
sudo journalctl -u lms_scheduler --since "YYYY-MM-DD 01:55:00" --no-pager
```

What good looks like:

```text
nginx active
gunicorn active
postgresql active
qcluster active
lms_scheduler active
latest backup is today's .zip
no 0 byte .sql files
BACKUP | SUCCESS in scheduler log
```

After pushing code:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show origin/main:"Leave Management/path/from/repo.py" > production/path.py
python manage.py check
sudo systemctl restart gunicorn
```

Only add these extra steps when needed:

```text
models/migrations changed -> python manage.py migrate
static files changed      -> python manage.py collectstatic
qcluster task changed     -> sudo systemctl restart qcluster
scheduler changed         -> sudo systemctl restart lms_scheduler
backup utility changed    -> restart gunicorn and lms_scheduler
```

## 27. Fresh Database And Superuser Setup

Fresh DB means all existing data is gone. Django still needs migration files because migrations create tables.

Normal fresh DB flow:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
```

After creating the superuser, fix it as project Admin:

```bash
python manage.py shell -c "from django.utils import timezone; from App.models import CustomUser, Profile; u=CustomUser.objects.get(username='mst_leave_admin'); u.role='Admin'; u.is_staff=True; u.is_superuser=True; u.must_change_password=False; u.is_active=True; u.save(); Profile.objects.update_or_create(user=u, defaults={'role':'Admin','department':'Management','date_of_joining':timezone.localdate(),'employee_id':'MST_Admin-0001'}); print('Admin fixed:', u.username, u.role, u.is_staff, u.is_superuser, u.is_active)"
```

What this command does:

```text
finds user mst_leave_admin
sets role to Admin
allows Django admin login by setting is_staff and is_superuser
keeps account active
turns off forced password change
creates or updates a Profile row
prints final confirmation
```

Why the profile is needed:

- Many screens assume a user has profile data.
- Admin/HR/Employee display labels use profile fields.
- Reports and employee IDs depend on profiles.

## 28. How To Use The Service Console

Command:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
python manage.py service_console
```

File:

```text
App/management/commands/service_console.py
```

This is a terminal launcher for important service utilities. It does not run automatically. You open it manually when you need a controlled terminal tool.

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
0. Exit
```

How it works:

- The command imports the selected service module.
- It calls that service module's interactive function.
- After the tool finishes, it returns you to the service console.

Important helper:

```python
_service_argv(command_name)
```

Some direct-run service files check `sys.argv[0]`. This helper temporarily sets `sys.argv` so those services behave as if they were run directly.

Example:

```text
Choose 9
-> runs startup_checks.py interactive flow
-> lets you view/check missed backup, weekly report, year-end status
```

## 29. Employee Portal Step-By-Step

Employee login:

```text
employee-login/
employee-login/form/
employee-login/dashboard-loading/
dashboard/
```

Main employee pages:

```text
dashboard/
apply_leave/
my_leave/
profile/
force-password-change/
```

Apply leave flow:

```text
Employee opens Apply Leave
-> chooses leave type
-> fills date/time/reason
-> submits
-> view validates input
-> overlap/holiday/WFH/balance logic runs
-> Leave row is created
-> balance is updated
-> HR notifications are created/refreshed
-> email/push side effects are queued
```

Example Short Leave:

```text
Type: Short
Date: 10 June 2026
From: 04:00 PM
To: 05:30 PM
Value: 0.25 day
Limit: max 2 short leaves per month
```

Example Half Leave:

```text
Type: Half
Date: 10 June 2026
From: 02:00 PM
To: 06:00 PM
Value: 0.5 day
Limit: max 1 half leave per month
```

Example Full-Day Sick Leave:

```text
Type: Sick
From: 10 June 2026
To: 12 June 2026
Value: calculated by working days and bridge rules
WFH bridge may apply
```

Employee My Leave:

- Shows pending, approved, rejected sections.
- Allows editing only pending leaves.
- Allows deleting pending leaves.
- Uses AJAX responses for smooth updates.

Employee profile:

- Can update phone, address, bio, and profile photo.
- Photo is sanitized and resized.
- Phone must be a valid Indian mobile number.
- Phone uniqueness is checked.

## 30. HR Portal Step-By-Step

HR login:

```text
hr-login/
hr-login/form/
hr-login/dashboard-loading/
hr-dashboard/
manage-all/
```

HR main work:

```text
view pending requests
approve leave
reject leave
view employee cards
download reports
send/receive communications
```

Approve flow:

```text
HR clicks approve
-> POST /approve-leave/<id>/
-> system locks only Leave row
-> checks leave is still Pending
-> sets status Approved
-> records reviewer and approved_at
-> logs action
-> queues employee notification/email/push
-> returns updated employee card if AJAX
```

Reject flow:

```text
HR enters rejection reason
-> POST /reject-leave/<id>/
-> system locks only Leave row
-> checks leave is still Pending
-> validates rejection reason
-> restores/reconciles balance
-> sets status Rejected
-> logs action
-> queues employee notification/email/push
-> returns updated employee card if AJAX
```

Why `select_for_update(of=("self"))` matters:

- It prevents two HR/admin operations from changing the same leave at the same time.
- It avoids PostgreSQL nullable join errors from profile joins.

Manage All:

- HR can view employee cards.
- HR can open employee details.
- Notification menu shows pending requests.
- Summary API gives counts.

## 31. Admin Portal Step-By-Step

Admin login:

```text
admin-login/
admin-login/form/
admin/
```

Admin can manage:

```text
users
profiles
leave records
leave balances
holidays
WFH days
communications
email jobs
audit logs
reports
system health
backup/restore
maintenance mode
service actions
push subscriptions
```

Creating a user:

```text
Admin opens Users
-> Add user
-> selects role
-> fills username/email/password/profile fields
-> optional welcome package/email can be sent
-> audit reason captures why this user was created
```

Editing user:

```text
Admin changes user/profile fields
-> reason is required where configured
-> audit log records old/new changes
-> role sync JS hides irrelevant fields
```

Bulk action confirmation pattern:

```text
Admin selects users
-> chooses action
-> preview page appears
-> each row shows what will happen
-> admin confirms
-> action runs only for eligible users
-> skipped users are reported
```

This pattern exists for:

- activate/deactivate
- force/clear password flag
- lock/unlock login
- resend onboarding
- reminder email
- push subscription deactivate

## 32. Backup Story In Detail

The backup system has two entrypoints:

```text
Admin manual backup
Scheduler automatic backup
```

Admin manual backup:

```text
Admin -> Service Actions -> RUN_BACKUP
-> gunicorn process imports manage_backups.run_backup()
-> pg_dump creates raw .sql
-> zip is created
-> raw .sql removed
```

Scheduler automatic backup:

```text
lms_scheduler at 02:00
-> check_and_run_missed_backup()
-> get_backup_catchup_status()
-> if no .zip for today, run_backup()
-> pg_dump -> .sql -> .zip
```

Startup catch-up:

```text
lms_scheduler starts
-> run_startup_catchup()
-> if today's backup zip is missing, trigger backup
-> if weekly report marker is missing, trigger report
-> if year-end is due, run year-end
```

Why backup failed before:

- `pg_dump` existed in your terminal.
- systemd services had PATH only to the virtualenv.
- Service processes could not find `/usr/bin/pg_dump`.
- Fix was adding full PATH override to `gunicorn`, `lms_scheduler`, and `qcluster`.

Why `.sql` files appeared:

- `backup_postgres()` opened the raw `.sql` file before `pg_dump` succeeded.
- If `pg_dump` failed, the file existed but was empty.
- Fix added cleanup on failure.

Valid backup:

```text
backup_prod_2026-05-31_02-00-00.zip
```

Invalid failed leftover:

```text
backup_prod_2026-05-31_02-00-00.sql 0 bytes
```

Current code deletes failed raw `.sql` automatically.

## 33. Restore Story In Detail

Restore is intentionally dangerous because it overwrites the database.

Restore flow:

```text
Admin enables maintenance mode
-> Admin opens Backup Restore
-> selects backup zip
-> types RESTORE
-> provides restore reason
-> restore_backup_file()
-> extracts .sql from zip
-> psql restores database
-> audit log records restore attempt/result
```

Why maintenance mode first:

- Restore can remove or change active data.
- Employees/HR should not keep using the app while restore happens.
- Maintenance mode blocks normal traffic.

Never casually test restore on production. If you need to test restore, use a staging environment or a controlled maintenance window.

## 34. Email Job Story With Example

Example: Admin sends force password email to three users.

Step 1:

```text
Admin selects 3 users
-> action: Force password change
```

Step 2:

```text
Confirmation page shows:
User A -> will change and email queued
User B -> already forced, skip/change depending action
User C -> no email, email skipped
```

Step 3:

```text
Admin confirms
-> AdminEmailJob created
-> 3 AdminEmailJobItem rows created
```

Step 4:

```text
create_admin_email_job()
-> enqueue_background_task(process_admin_email_job, job.id)
```

Step 5:

```text
qcluster processes job
-> item status queued -> running -> sent/skipped/failed
-> job counts refresh
```

Step 6:

```text
Admin job page auto-refreshes
-> shows total/sent/failed/skipped per user
```

If qcluster dies during item:

```text
item may remain running
-> scheduler recovery runs every 5 minutes
-> after stale timeout, item reset to queued
-> fresh task queued
```

## 35. Notification Story With Example

Example: Employee applies leave.

```text
Employee submits leave
-> Leave row created
-> HR notification context builds pending item
-> HR bell count increases
-> HR browser polling sees new item
-> sound can play if HR tab is open
-> push notification can go if permission and HTTPS are configured
```

Example: HR approves leave.

```text
HR approves leave
-> Employee notification item becomes available
-> Employee bell count increases
-> Employee email/push can be queued
```

Example: Admin edits pending leave dates.

```text
Admin changes important leave details
-> pending notification is refreshed
-> read/seen state may reset
-> HR can see it as new/unread again
```

Sound requirement:

```text
browser tab open + polling active = sound can play
browser closed = no normal polling sound
browser push permission + HTTPS = push can appear
```

## 36. Function Reference: Project-Level Backup

File:

```text
manage_backups.py
```

Functions:

```text
get_master_logger()
Returns the backup logger.

get_email_logger()
Returns the email/system alert logger.

backup_timestamp()
Creates timestamp text used in backup filenames.

backup_sqlite()
Copies SQLite DB for development mode.

backup_postgres()
Runs pg_dump and creates raw .sql in backups directory.
If pg_dump fails, incomplete .sql is removed.

compress_file(file_path)
Creates .zip from raw backup and removes raw file.

cleanup_old_backups()
Deletes backup files older than retention days.

run_backup()
Main backup function used by admin and scheduler.

restore_database()
Interactive terminal restore utility.

restore_backup_file(selected_backup)
Programmatic restore function used by admin restore.

restore_sqlite(selected_backup)
Restores SQLite backup in dev mode.

restore_postgres(selected_backup)
Uses psql to restore PostgreSQL backup.
```

Example manual backup from shell:

```bash
python manage.py shell -c "from manage_backups import run_backup; print(run_backup())"
```

## 37. Function Reference: Background Tasks

File:

```text
App/services/background_tasks.py
```

Functions:

```text
_qcluster_looks_active()
Uses a short cache to avoid checking qcluster too often.

_detect_qcluster()
Checks Django-Q Stat first, then process list.

_qcluster_process_looks_active()
Uses psutil to find manage.py qcluster process in the project directory.

_enqueue_with_django_q()
Queues work with django_q.tasks.async_task if qcluster is active.

_enqueue_with_thread()
Runs work in ThreadPoolExecutor fallback.

enqueue_background_task()
Public helper used by views/admin/services for slow side effects.
```

Example:

```python
enqueue_background_task(send_branded_email, subject, template, context, recipients, task_name="leave_email")
```

Meaning:

```text
try qcluster
if qcluster unavailable, use in-process thread
```

## 38. Function Reference: Admin Bulk Email Jobs

File:

```text
App/services/admin_bulk_email_jobs.py
```

Functions:

```text
create_admin_email_job()
Creates AdminEmailJob and AdminEmailJobItem rows, then queues processing.

process_admin_email_job(job_id)
Processes queued items one by one.

recover_stuck_admin_email_jobs()
Finds stale running items and resets them to queued.

_process_job_item()
Dispatches each item by job type.

_send_onboarding_item()
Sends/resends welcome package.

_send_force_password_item()
Sends force or clear forced-password email.

_send_reminder_item()
Sends admin reminder email.

_send_login_lock_item()
Sends admin lock notification email.

_send_login_unlock_item()
Sends admin unlock notification email.

_send_plain_job_email()
Shared plain-text email sender for lock/unlock type jobs.

_display_name()
Returns full name or username.

_actor_name()
Returns admin actor name or Administrator.

_finish_item()
Updates item final status, message, error, finished_at.
```

## 39. Function Reference: Leave Breakdown

File:

```text
App/services/leave_breakdown.py
```

Functions:

```text
_iter_dates()
Yields dates from start to end.

get_work_from_home_weekdays()
Loads WFH weekdays from WorkFromHomeDay records.

get_work_from_home_weekday_labels()
Turns WFH weekday numbers into readable labels.

_is_wfh_day()
Checks if date is WFH day.

_is_bridge_day()
Checks if date should be included as bridge day.

_resolve_requested_range()
Keeps original employee-requested range separate from expanded range.

_starts_after_consecutive_weekend()
Detects range starting after weekend.

expand_full_day_leave_range()
Expands Sick/Earned/Unpaid leave around WFH/weekend bridge rules.

calculate_leave_breakdown()
Returns working days, WFH days, weekend days, company holiday days.

calculate_leave_breakdown_for_leave()
Wrapper that uses a Leave object.

reconcile_user_full_day_leave_bridges()
Rechecks all full-day leave for a user and updates bridge dates.

preview_user_full_day_leave_bridge_reconciliation()
Shows what reconciliation would do before applying it.
```

Important rule:

```text
Bridge applies only to Sick, Earned, Unpaid.
It does not apply to Short or Half.
```

## 40. Function Reference: Public Holidays

File:

```text
App/services/public_holidays.py
```

Functions:

```text
_holiday_cache_file()
Returns runtime/public_holidays_india.json.

fallback_public_holidays(year)
Returns basic fixed fallback holidays.

_read_holidays_from_file(year)
Reads cached holidays from runtime JSON.

_write_holidays_to_file(year, holidays)
Writes fetched holidays to runtime JSON.

_fetch_google_public_holidays(year)
Downloads Google India holiday ICS and parses it.

get_public_holidays(year=None)
Reads from cache/file/fallback for app use.

sync_public_holidays(year=None)
Fetches fresh holidays and saves cache. Used by qcluster/scheduler.
```

Failure behavior:

```text
If Google/DNS/network fails, sync returns False.
App still uses cached/fallback holidays.
```

## 41. Function Reference: Login Lock

File:

```text
App/services/login_lock_service.py
```

Key functions:

```text
safe_username()
Normalizes username for cache keys.

login_cache_token()
Hashes values for safe cache keys.

login_cache_key()
Builds cache key for username/IP/portal state.

get_login_rate_config()
Loads rate/lock config per portal.

detect_user_portal()
Returns Admin/HR/Employee portal based on user role.

default_lock_minutes_for_portal()
Returns default lock duration.

remember_failed_login_ip()
Stores last failed login IP for a username.

get_login_lock_status()
Returns current lock status.

lock_user_login()
Admin/service function to lock a user.

unlock_user_login()
Admin/service function to unlock a user.

login_lock_status_payload()
Serializes status for UI/API.

record_login_lock_audit()
Writes audit log for lock/unlock/check actions.

format_remaining()
Turns seconds into readable time.

run_login_lock_cli()
Interactive terminal manager.
```

Example:

```text
Wrong password repeatedly
-> cache counter increases
-> user gets locked
-> login page shows retry time
-> email can notify user
```

## 42. Function Reference: Forced Password

File:

```text
App/services/forced_password_service.py
```

Key functions:

```text
user_can_be_forced_to_change_password()
Returns True only for users where forced password makes sense.

send_forced_password_email()
Sends forced/cleared password email and records delivery.

send_password_reset_email()
Sends password reset email after admin/manual reset.

run_cli()
Interactive terminal manager for force password actions.
```

Events:

```text
forced   -> user must change password
cleared  -> forced flag removed
```

## 43. Function Reference: Employee Welcome

File:

```text
App/services/employee_welcome_service.py
```

Key functions:

```text
send_employee_welcome_package()
Creates welcome communication and optionally sends welcome email.

_get_leave_summary()
Builds leave balance summary for welcome body.

_build_welcome_body()
Builds welcome message text.

_last_welcome_email()
Finds previous welcome email log.

_welcome_package_status()
Returns whether welcome package was sent.

_last_email_status_text()
Returns text like Sent - date (count).

_record_welcome_audit()
Records admin/service action audit.

run_interactive()
Terminal welcome package manager.
```

Welcome package meaning:

```text
communication/message inside app
optional welcome email
tracking in profile/email logs
```

## 44. Function Reference: Startup Checks

File:

```text
App/services/startup_checks.py
```

Functions:

```text
get_backup_catchup_status()
Checks whether today's backup .zip exists.

get_weekly_report_catchup_status()
Checks whether weekly report marker exists.

get_year_end_catchup_status()
Checks whether year-end carry-forward is due.

run_startup_catchup()
Runs missed backup/report/year-end checks at scheduler start.

check_and_run_missed_backup()
Runs backup if today's .zip is missing.

check_and_run_missed_weekly_report()
Sends weekly report if missed.

check_and_run_year_end_carry_forward()
Runs year-end if due.

print_startup_check_dry_run()
Shows what would happen without changing data.

run_selected_startup_checks()
Runs selected checks from terminal.

main()
Interactive direct-run entrypoint.
```

## 45. Function Reference: Scheduler

File:

```text
App/services/scheduler.py
```

Functions:

```text
start_scheduler()
Creates APScheduler, runs startup catch-up, adds jobs, starts scheduler.

show_scheduler_jobs()
Prints configured jobs.

show_scheduler_status()
Prints scheduler type/status info.

run_interactive()
Terminal scheduler viewer.
```

Service command:

```text
App/management/commands/run_lms_scheduler.py
```

This command:

```text
records startup time with force=True
starts scheduler
waits until service stops
shuts scheduler down cleanly
```

## 46. Function Reference: Uptime Tracker

File:

```text
App/services/uptime_tracker.py
```

Functions:

```text
record_app_startup(force=False)
Writes runtime/app_startup.json.

get_app_started_at()
Reads started_at from runtime JSON.

format_current_uptime()
Returns "Running for X".

main()
Terminal uptime viewer.
```

This is only for display/reporting. It does not control any feature.

## 47. Function Reference: Weekly Report

File:

```text
App/services/weekly_report_service.py
```

Key functions:

```text
get_week_range()
Calculates current/previous/custom week range.

build_weekly_hr_report_context()
Builds all data needed for weekly report template.

render_weekly_hr_report_html()
Renders HTML report.

generate_weekly_hr_report_pdf_bytes()
Creates PDF bytes using Playwright.

generate_weekly_hr_report_pdf_file()
Writes PDF to generated_pdfs.

send_weekly_hr_report()
Emails the report to active HR recipients.

build_manual_weekly_report_context_from_prompt()
Interactive terminal data selection.

main()
Terminal weekly report manager.
```

System health in report can include:

```text
backup status
security warnings
uptime
database latency
notification health
```

## 48. Function Reference: PDF Generator

File:

```text
App/services/pdf_generator.py
```

Functions:

```text
generate_pdf_from_html()
Uses Playwright Chromium to convert HTML to PDF bytes.

_generated_pdf_dir()
Returns generated_pdfs directory.

_write_pdf_bytes()
Writes generated PDF to disk.

_generate_weekly_report_pdf()
Terminal helper to create weekly PDF.

_generate_custom_template_pdf()
Terminal helper to convert a template/file to PDF.

main()
Interactive PDF generator.
```

Production dependency:

```text
Playwright Chromium must be installed and launchable.
```

## 49. Function Reference: Report Export

File:

```text
App/services/report_export_service.py
```

Core functions:

```text
build_report_export()
Main export builder. Returns CSV/PDF data based on filters.

get_report_row_count()
Counts rows before export.

describe_export_filters()
Creates readable filter summary.

describe_period()
Describes selected period.

_build_rows()
Dispatches to report-specific row builders.

_employee_master_rows()
Employee master report.

_leave_request_rows()
Leave request report.

_leave_balance_rows()
Leave balance report.

_leave_balance_audit_rows()
Balance audit report.

_admin_audit_rows()
Admin audit report.

_delete_audit_rows()
Delete audit report.

_communication_rows()
Communication report.

_email_delivery_rows()
Email delivery report.

_holiday_rows()
Holiday report.

_wfh_rows()
WFH report.

_year_end_rows()
Year-end report.

_system_health_rows()
System health report.

_hr_summary_rows()
HR summary report.

_rows_to_csv()
Converts rows to CSV.

_rows_to_pdf()
Converts rows to simple PDF.

_record_export_audit()
Records export audit.

run_interactive()
Terminal export tool.
```

## 50. Function Reference: Push Notifications

File:

```text
App/services/push_notifications.py
```

Key functions:

```text
push_is_configured()
Checks webpush keys/settings.

build_push_payload()
Creates payload sent to browser.

send_push_to_user()
High-level send to a user.

send_push_payload_to_user()
Sends payload to active subscriptions.

_deactivate_one_subscription()
Terminal helper to disable one subscription.

_deactivate_all_failed()
Terminal helper to clean failed subscriptions.

run_interactive()
Terminal push notification manager.
```

Production requirements:

```text
HTTPS
valid webpush keys
browser permission
service worker registered
```

## 51. Function Reference: Views By Feature

File:

```text
App/views.py
```

Portal/loading functions:

```text
role_select()
app_loading()
employee_login_loading()
hr_login_loading()
admin_login_loading()
employee_workspace_loading()
hr_workspace_loading()
admin_workspace_loading()
employee_dashboard_loading_page()
hr_dashboard_loading_page()
admin_dashboard_loading_page()
logout_loading()
employee_logout_loading_page()
hr_logout_loading_page()
admin_logout_loading_page()
```

Login/security functions:

```text
employee_login()
hr_login()
admin_login()
logout_view()
_register_login_failure()
_record_successful_login()
_send_login_security_alert()
_login_blocked_response()
```

Notification functions:

```text
hr_notifications()
employee_notifications()
notifications_mark_read()
notifications_mark_seen()
build_hr_pending_notifications()
build_employee_notifications()
get_hr_notification_context()
get_employee_notification_context()
refresh_pending_leave_notification()
reset_hr_notification_state_for_leave()
```

Communication functions:

```text
communications_feed()
communications_send()
communications_mark_read()
communications_mark_seen()
get_communication_queryset()
build_communication_items()
get_communication_context()
queue_communication_push()
```

Push API:

```text
push_notification_config()
push_subscribe()
push_unsubscribe()
push_test()
service_worker()
```

HR functions:

```text
hr_dashboard()
manage_all()
manage_all_employee_detail()
manage_all_summary()
approve_leave()
reject_leave()
employee_details()
delete_employee()
download_employee_archive()
update_employee_contact_field()
reports()
weekly_report_preview()
weekly_report_download()
weekly_report_email()
```

Employee functions:

```text
dashboard()
apply_leave()
leave_calendar_data()
my_leave()
apply_status_filter()
clear_status_filter()
clear_status_filter_field()
delete_leave()
edit_leave()
profile_view()
force_password_change()
```

Validation/helper functions:

```text
normalize_employee_phone()
validate_employee_address()
validate_plain_text_field()
validate_employee_username()
validate_employee_email()
validate_employee_leave_total()
validate_profile_bio()
get_valid_leave_type()
get_valid_leave_status()
get_valid_filter_month()
get_valid_filter_date()
get_capped_positive_int()
get_nonnegative_int()
```

Email/helper functions:

```text
send_branded_email()
get_leave_alert_recipients()
get_leave_decision_email_recipients()
queue_hr_leave_push()
queue_employee_leave_push()
```

## 52. Function Reference: Admin By Feature

File:

```text
App/admin.py
```

Health/log helper groups:

```text
_tail_log_file()
_search_log_files()
_get_database_health()
_get_email_config_health()
_get_scheduler_health()
_get_storage_health()
_get_security_config_health()
_get_business_health()
```

Backup helpers:

```text
_get_backup_restore_files()
_get_safe_backup_path()
_get_latest_file_info()
_backup_age_health()
```

Audit helpers:

```text
_audit_value()
_collect_model_changes()
_create_admin_audit_log()
_snapshot_model_fields()
admin_reason_field()
```

User admin:

```text
CustomUserAdmin
activate_selected_users()
deactivate_selected_users()
force_password_change_for_selected_users()
clear_forced_password_change_for_selected_users()
resend_onboarding_email_to_selected_users()
send_reminder_email_to_selected_users()
lock_login_for_selected_users()
unlock_login_for_selected_users()
check_login_lock_status_for_selected_users()
export_selected_archive_pdfs()
```

Leave admin:

```text
LeaveAdmin
admin_approve_selected_leaves()
admin_reject_selected_leaves()
admin_sync_selected_leaves()
admin_delete_selected_leaves_with_workflow()
admin_recalculate_selected_leave_balances()
```

Communication admin:

```text
CommunicationAdmin
EmployeeCommunicationProxyAdmin
HRCommunicationProxyAdmin
AdminCommunicationCenterAdmin
CommunicationReadAdmin
CommunicationSeenAdmin
LeaveNotificationReadAdmin
LeaveNotificationSeenAdmin
```

Service/admin control:

```text
DashboardSummaryControlAdmin
SystemHealthControlAdmin
ServiceActionControlAdmin
BackupRestoreControlAdmin
MaintenanceModeControlAdmin
ReportExportControlAdmin
```

Admin email jobs:

```text
AdminEmailJobAdmin
AdminEmailJobItemAdmin
AdminEmailJobItemInline
```

Log viewers:

```text
LogViewerAdmin
SecurityLogViewerAdmin
AuthLogViewerAdmin
LeaveLogViewerAdmin
EmailLogViewerAdmin
BackupLogViewerAdmin
MaintenanceLogViewerAdmin
SchedulerLogViewerAdmin
ServiceLogViewerAdmin
ApiLogViewerAdmin
ProfileLogViewerAdmin
AnalyticsLogViewerAdmin
MasterLogViewerAdmin
DjangoErrorLogViewerAdmin
```

## 53. Function Reference: Models

File:

```text
App/models.py
```

User and leave:

```text
CustomUser
Adds role and must_change_password to Django user.

Leave
Stores leave request, validates short/half rules, stores approval/rejection state.

LeaveBalance
Stores sick/earned/unpaid totals and remaining balance.

LeaveBalanceAudit
Tracks balance changes.
```

Audit:

```text
AdminAuditLog
Base admin audit table with truncation safeguards.

UserAdminAudit
ProfileAdminAudit
LeaveAdminAudit
HolidayAdminAudit
WorkFromHomeAdminAudit
DeleteAdminAudit
EmployeeCommunicationAudit
HRCommunicationAudit
AdminCommunicationAudit
Read/seen audit proxy models
```

Email/background:

```text
EmailDeliveryLog
AdminEmailJob
AdminEmailJobItem
```

Notifications/communications:

```text
Communication
CommunicationRead
CommunicationSeen
LeaveNotificationRead
LeaveNotificationSeen
Employee/HR proxy variants
```

System/support:

```text
PushSubscription
YearEndCarryForwardRun
CompanyHoliday
WorkFromHomeDay
Profile
LogViewer proxy models
Service/control proxy models
```

## 54. Forms Reference

File:

```text
App/forms.py
```

Forms:

```text
UserProfileForm
Used for phone/address/profile photo.

CustomPasswordChangeForm
Used on forced password change page.
Enforces:
- 8 characters
- uppercase
- number
- symbol
- confirmation match
Uses PasswordInput widgets so password fields are hidden by default.
```

Admin forms live mostly in `App/admin.py` because they are admin-specific.

Examples:

```text
BulkUserStatusActionForm
BulkUserReminderEmailForm
BulkUserOnboardingEmailForm
LoginLockAdminActionForm
LeaveAdminForm
LeaveBalanceAdminForm
ReportExportForm
AdminCommunicationComposeForm
```

## 55. Common "How Do I Do This?" Examples

Deploy one Python file:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show origin/main:"Leave Management/App/views.py" > App/views.py
python manage.py check
sudo systemctl restart gunicorn
```

Deploy one static JS file:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
git fetch origin
git show origin/main:"Leave Management/static/js/manage_all.js" > static/js/manage_all.js
python manage.py collectstatic
sudo systemctl restart gunicorn
```

Deploy scheduler change:

```bash
git fetch origin
git show origin/main:"Leave Management/App/services/scheduler.py" > App/services/scheduler.py
python manage.py check
sudo systemctl restart lms_scheduler
```

Deploy qcluster/background job change:

```bash
git fetch origin
git show origin/main:"Leave Management/App/services/admin_bulk_email_jobs.py" > App/services/admin_bulk_email_jobs.py
python manage.py check
sudo systemctl restart qcluster
```

Check if file really loaded:

```bash
grep -n "known text from new code" path/to/file.py
```

Check auto backup:

```bash
ls -lh ~/Leave_Management_MST/backups | tail -10
sudo journalctl -u lms_scheduler --since "2026-05-31 01:55:00" --no-pager
```

Check qcluster:

```bash
sudo systemctl status qcluster
pgrep -fc "manage.py qcluster"
```

Check scheduler:

```bash
sudo systemctl status lms_scheduler
sudo journalctl -u lms_scheduler -n 100 --no-pager
```

Check gunicorn error:

```bash
sudo journalctl -u gunicorn -n 200 --no-pager
```

## 56. Reading Errors Correctly

Do not assume the visible UI message is the true error. Always check logs.

Example:

```text
UI says session expired
gunicorn log says Internal Server Error
traceback says PostgreSQL FOR UPDATE error
```

Correct debugging order:

```bash
sudo journalctl -u gunicorn -n 200 --no-pager
```

Then search:

```bash
sudo journalctl -u gunicorn -n 200 --no-pager | grep -i "error\|traceback\|csrf\|forbidden"
```

For scheduler:

```bash
sudo journalctl -u lms_scheduler -n 100 --no-pager
```

For qcluster:

```bash
sudo journalctl -u qcluster -n 100 --no-pager
```

## 57. Mental Checklist Before Changing Code

Before making any change, ask:

```text
Is this user-facing?
Does it touch DB schema?
Does it touch background jobs?
Does it touch scheduled jobs?
Does it touch static JS/CSS?
Does it touch production system tools?
Does it need audit logging?
Does it need read/seen notification reset?
Does it need email delivery logging?
Does it need migration?
```

Examples:

```text
Change admin email job status logic
-> Python service/admin/template/static maybe
-> restart gunicorn/qcluster
-> collectstatic if JS/CSS changed

Change Leave model field
-> migration needed
-> migrate production
-> restart services

Change backup command
-> restart gunicorn and lms_scheduler
-> verify backup manually or next 02:00

Change notification JS
-> collectstatic
-> browser hard refresh may be needed
```

## 58. What To Remember Most

The most important production lessons from this project:

```text
Always git fetch before git show.
Always run python manage.py check after loading Python files.
Run collectstatic for static changes.
Restart the service that owns the changed code.
Check logs, not just UI messages.
Use exact journal dates if "today" fails.
Valid backup is .zip, not raw .sql.
qcluster has several processes; 6 is normal.
runtime/app_startup.json is only uptime display.
PATH override keeps venv first and adds /usr/bin for system tools.
```
