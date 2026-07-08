# Leave Management MST - Start Here

Open this file first when you forget what the project does, how to deploy, or where to debug.

Last updated: 2026-07-08

## 1. What This Project Is

Leave Management MST is a Django production system for:

```text
employee leave applications
HR approval/rejection workflow
admin user/leave/report management
email and browser notifications
communication center
weekly HR reports
public/company holiday and WFH bridge rules
backup/restore and maintenance operations
production scheduler and background jobs
```

Main roles:

```text
Admin
HR
EMPLOYEE
```

Main production URL:

```text
https://mstleave.mstlabs.in
```

Production directory:

```text
/home/mstleave/Leave_Management_MST
```

## 2. Documentation Map

| File | Use it for |
|---|---|
| `README.md` | Clean project overview, feature summary, local setup, production quick path. |
| `PROJECT_START_HERE.md` | This file. Quick memory and first commands. |
| `PROJECT_GUIDE.md` | Practical project behavior guide: roles, workflows, admin tools, service ownership. |
| `PROJECT_DEPLOYMENT_GUIDE.md` | Full production/Linux deployment guide: systemd, nginx, workers, backups, dev vs production. |
| `PROJECT_DEEP_DIVE_BOOK.md` | Very large deep technical reference and debugging book. |
| `Leave Management/App/management/production_setup/README.md` | Production secret/key generation helper documentation. |

## 3. Which File Should I Open?

| Situation | Open |
|---|---|
| I forgot what the app does | `README.md`, then `PROJECT_GUIDE.md` |
| I need to deploy code to Linux | `PROJECT_DEPLOYMENT_GUIDE.md` |
| I need exact production commands | `PROJECT_DEPLOYMENT_GUIDE.md` section `23`, `31`, `33`, `35` |
| I need to know if migrate/collectstatic/restart is required | `PROJECT_DEPLOYMENT_GUIDE.md` section `8` |
| I need to debug a production error | `PROJECT_GUIDE.md`, then `PROJECT_DEEP_DIVE_BOOK.md` |
| I need service/worker explanation | `PROJECT_DEPLOYMENT_GUIDE.md` section `29` |
| I need dev vs production differences | `PROJECT_DEPLOYMENT_GUIDE.md` section `34` |
| I need history of production problems/fixes | `PROJECT_DEPLOYMENT_GUIDE.md` section `30` |
| I need to add future feature docs | `PROJECT_DEPLOYMENT_GUIDE.md` section `26` and section `36` |

## 4. Most Important Production Commands

Always start from the production project root:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
python manage.py check
```

Fetch latest GitHub state:

```bash
git fetch origin
git show --name-only --pretty=format:"%h %s" origin/main
```

Copy one pushed file into production:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

Run migrations only if models/migration files changed:

```bash
python manage.py migrate
```

Run collectstatic only if static files changed:

```bash
python manage.py collectstatic
```

Restart web app:

```bash
sudo systemctl restart gunicorn
```

Restart background workers if background code/settings changed:

```bash
sudo systemctl restart qcluster
```

Restart scheduler if scheduler/startup/backup/report/job code/settings changed:

```bash
sudo systemctl restart lms_scheduler
```

## 5. Production Services

| Service | Work | Common reason to restart |
|---|---|---|
| `nginx` | Public web server, SSL/front layer, static/media/proxy | nginx config/static/media serving changes |
| `gunicorn` | Django web/admin/API requests | views, templates, forms, settings, admin, web services |
| `qcluster` | Django-Q background jobs | background task/email/push job code/settings |
| `lms_scheduler` | Timed jobs | scheduler/startup/backup/weekly report/recovery code/settings |
| `postgresql` | Database | rarely restart manually; required for DB server maintenance |

Check all:

```bash
sudo systemctl status nginx --no-pager
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
sudo systemctl status postgresql --no-pager
```

Auto-start check:

```bash
sudo systemctl is-enabled nginx
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
enabled
```

## 6. Logs To Check First

Web/app/admin/API:

```bash
sudo journalctl -u gunicorn -n 120 --no-pager
```

Background jobs:

```bash
sudo journalctl -u qcluster -n 120 --no-pager
```

Scheduler/backup/weekly report/recovery:

```bash
sudo journalctl -u lms_scheduler -n 120 --no-pager
```

Specific absolute time:

```bash
sudo journalctl -u lms_scheduler --since "2026-07-08 01:55:00" --no-pager
```

Do not rely on `today 01:55` if journalctl rejects it.

## 7. Current Known-Good Production Facts

```text
Gunicorn uses 1 master + 3 workers.
qcluster usually shows about 6 processes, with 2 real task workers.
lms_scheduler is one dedicated scheduler process.
Backups are valid when they are .zip files in backups/.
Zero-byte .sql files are failed/incomplete backups, not valid backups.
Systemd service PATH must include /usr/bin for pg_dump, psql, xclip.
Production uses HTTPS, so secure cookies and browser push can work.
```

## 8. Current Config Values To Remember

Leave timing:

```env
SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES=15
SHORT_HALF_LEAVE_GRACE_MINUTES=5
SICK_LEAVE_SAME_DAY_CUTOFF_TIME=11:59
```

Password max length:

```env
PASSWORD_INPUT_MAX_LENGTH=128
```

Record emails:

```env
LEAVE_RECORD_EMAILS=leave@mst-india.com
```

Portal URL:

```env
PORTAL_BASE_URL=https://mstleave.mstlabs.in
```

Cookie/security flags:

```env
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SESSION_COOKIE_SECURE=True
```

Web Push keys:

```env
WEB_PUSH_VAPID_PUBLIC_KEY=generated-public-key
WEB_PUSH_VAPID_PRIVATE_KEY=runtime/webpush_private_key.pem
WEB_PUSH_VAPID_SUBJECT=mailto:admin@example.com
```

qcluster tuning:

```env
LMS_Q_WORKERS=2
LMS_Q_TIMEOUT=120
LMS_Q_RETRY=300
LMS_Q_QUEUE_LIMIT=100
LMS_Q_BULK=20
```

## 9. Quick Verification Commands

Django health:

```bash
python manage.py check
```

Password max length:

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

Backup status:

```bash
ls -lh ~/Leave_Management_MST/backups | tail -20
python manage.py shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

Service PATH:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

## 10. First Debug Rule

Do not trust only the UI message.

Example we already faced:

```text
UI looked like session expired.
Gunicorn logs showed a PostgreSQL FOR UPDATE error.
```

Correct order:

```text
1. Record user action and exact time.
2. Check owning service log.
3. Search error/function in code with rg.
4. Apply smallest fix.
5. Run python manage.py check.
6. Restart owning service.
7. Verify same user action again.
```

## 11. Feature Ownership Map

| Feature/problem | Main owner |
|---|---|
| Login pages and sessions | `App/views.py`, `templates/*login.html`, `gunicorn` |
| Wrong password locks | `App/services/login_lock_service.py`, `App/views.py`, admin/service console |
| Password max length | `App/scripts/validators.py`, `App/views.py`, `App/forms.py`, `App/admin.py` |
| Apply/edit/delete leave | `App/views.py`, `App/models.py`, `templates/apply_leave.html`, `static/js/apply_leave.js`, `static/js/my_leave.js` |
| HR approve/reject | `App/views.py`, PostgreSQL row locks |
| Admin bulk emails | `App/services/admin_bulk_email_jobs.py`, `qcluster`, `lms_scheduler` recovery |
| Backups/restores | `manage_backups.py`, `pg_dump`, `psql`, `lms_scheduler` |
| Weekly report PDF | `App/services/weekly_report_service.py`, `App/services/pdf_generator.py`, Playwright Chromium |
| Push notifications | `App/services/push_notifications.py`, service worker, HTTPS, VAPID keys |
| Public holidays | `App/services/public_holidays.py`, scheduler/qcluster, runtime cache |
| Uptime display | `App/services/uptime_tracker.py`, `runtime/app_startup.json` |

## 12. How To Update Docs For New Features

Every new feature should update docs in this order:

```text
1. README.md if the overall feature list changed.
2. PROJECT_START_HERE.md if commands/navigation changed.
3. PROJECT_GUIDE.md if workflow or behavior changed.
4. PROJECT_DEPLOYMENT_GUIDE.md if deployment/services/env/static/migration behavior changed.
5. PROJECT_DEEP_DIVE_BOOK.md current-state addendum if debugging notes changed.
6. production_setup/README.md if env/key/secret generation changed.
```

Use this mini-template:

```text
Feature name:
User-facing behavior:
Files changed:
Environment variables:
Migration needed: yes/no
collectstatic needed: yes/no
Services to restart:
Verification command:
Rollback note:
```

## 13. Do Not Forget

```text
Always git fetch before git show.
Always run python manage.py check after Python/settings changes.
Run collectstatic for static changes.
Restart the service that owns the changed code.
Check logs after restart.
Valid backup is .zip, not raw .sql.
Do not overwrite production .env with .env.example.
Do not add random IPs to ALLOWED_HOSTS just because DisallowedHost appears.
```

## 14. If This Changed, Do This

| Changed thing | Production commands |
|---|---|
| Only Python view/admin/form/service code | `python manage.py check`, restart `gunicorn` |
| Background task code | `python manage.py check`, restart `qcluster` |
| Scheduler/startup/backup weekly job code | `python manage.py check`, restart `lms_scheduler` |
| Template HTML | restart `gunicorn` |
| Static JS/CSS/image | `python manage.py collectstatic`, restart `gunicorn`, hard refresh browser |
| Model field/table/migration | copy migration, `python manage.py migrate`, restart affected services |
| `.env` web setting | edit `.env`, `python manage.py check`, restart `gunicorn` |
| `.env` qcluster setting | edit `.env`, restart `qcluster` |
| `.env` scheduler setting | edit `.env`, restart `lms_scheduler` |
| Backup tool or pg_dump/psql issue | check `manage_backups.py`, service PATH, restart `gunicorn` and `lms_scheduler` |
| Nginx static/media/domain config | `sudo nginx -t`, restart `nginx` |

## 15. Common Problems And First Place To Look

| Symptom | First check |
|---|---|
| Page gives 500 | `sudo journalctl -u gunicorn -n 200 --no-pager` |
| Approval says session/redirect but fails | Gunicorn traceback around approval time |
| Static UI did not update | Was `collectstatic` run? Browser hard refresh? |
| Backup missing | `sudo journalctl -u lms_scheduler --since "YYYY-MM-DD 01:55:00" --no-pager` |
| Admin backup fails but terminal works | `sudo systemctl show gunicorn -p Environment` |
| Scheduler backup fails but terminal works | `sudo systemctl show lms_scheduler -p Environment` |
| Bulk email stuck | qcluster status, AdminEmailJob page, scheduler recovery logs |
| Push notifications fail | HTTPS, browser permission, VAPID keys, service worker |
| Login locked | login lock manager in admin or `python manage.py service_console` |
| Linux feels slow | `uptime`, `free -h`, `ps ... --sort=-%cpu`, `ps ... --sort=-%mem` |

## 16. Exact Production Verification Pack

Run after important deployments:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
python manage.py check
sudo systemctl status gunicorn --no-pager
sudo systemctl status qcluster --no-pager
sudo systemctl status lms_scheduler --no-pager
sudo journalctl -u gunicorn -n 80 --no-pager
sudo journalctl -u qcluster -n 80 --no-pager
sudo journalctl -u lms_scheduler -n 80 --no-pager
```

Optional deeper checks:

```bash
python manage.py shell -c "from django.conf import settings; print(settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_HTTPONLY, settings.SESSION_COOKIE_SAMESITE, settings.CSRF_COOKIE_SECURE)"
python manage.py shell -c "from django.conf import settings; from App.scripts.validators import get_password_input_max_length; print(settings.PASSWORD_INPUT_MAX_LENGTH, get_password_input_max_length())"
python manage.py shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

## 17. Future Feature Documentation Shortcut

When adding a new feature, search docs first:

```bash
rg -n "feature-name|related-function|related-file" *.md
```

Then update:

```text
README.md if it changes the project overview.
PROJECT_GUIDE.md if it changes how Admin/HR/Employee use the system.
PROJECT_DEPLOYMENT_GUIDE.md if deployment, services, env, migrations, or static files are affected.
PROJECT_DEEP_DIVE_BOOK.md current addendum if it changes debugging knowledge.
```
