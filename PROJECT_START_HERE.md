# Leave Management MST - Start Here

> Open this file first when you forget what the project does, how to deploy, or where to debug.

## 1. Main Documentation Files

| File | Use it for |
|---|---|
| `PROJECT_START_HERE.md` | Quick navigation and daily operating memory |
| `PROJECT_GUIDE.md` | Medium-size practical guide |
| `PROJECT_DEEP_DIVE_BOOK.md` | Full deep dive, function reference, runbooks, matrices, and debugging notes |
| `README.md` | Public/project overview and basic setup |

## 2. Fastest Paths In The Deep Dive Book

| Need | Open/Search |
|---|---|
| Full system overview | `PROJECT_DEEP_DIVE_BOOK.md:125` |
| Production services overview | `PROJECT_DEEP_DIVE_BOOK.md:144` |
| File inventory | `PROJECT_DEEP_DIVE_BOOK.md:179` |
| Admin code reference | `PROJECT_DEEP_DIVE_BOOK.md:4243` |
| Admin email jobs/qcluster | `PROJECT_DEEP_DIVE_BOOK.md:50785` |
| Force password | `PROJECT_DEEP_DIVE_BOOK.md:57115` |
| Login lock/unlock | `PROJECT_DEEP_DIVE_BOOK.md:59351` |
| Scheduler | `PROJECT_DEEP_DIVE_BOOK.md:70745` |
| Employee/HR views | `PROJECT_DEEP_DIVE_BOOK.md:81101` |
| Backups/restores | `PROJECT_DEEP_DIVE_BOOK.md:93779` |
| Practical runbooks | `PROJECT_DEEP_DIVE_BOOK.md:115893` |
| Production commands and matrices | `PROJECT_DEEP_DIVE_BOOK.md:117637` |

## 3. Most Important Production Commands

Always start from the production project root:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
python manage.py check
```

Check changed files in the latest GitHub main:

```bash
git fetch origin
git show --name-only --pretty=format:"%h %s" origin/main
```

Copy one pushed file into production:

```bash
git show origin/main:"Leave Management/App/views.py" > App/views.py
```

If Python code changed:

```bash
python manage.py check
sudo systemctl restart gunicorn
```

If models/migrations changed:

```bash
python manage.py migrate
python manage.py check
sudo systemctl restart gunicorn
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

If JS/CSS/static changed:

```bash
python manage.py collectstatic
sudo systemctl restart gunicorn
```

If background jobs changed:

```bash
sudo systemctl restart qcluster
sudo systemctl restart lms_scheduler
```

## 4. System Services

| Service | Work |
|---|---|
| `gunicorn` | Django web app, admin panel, employee/HR pages, admin backup UI |
| `qcluster` | Queued background jobs, bulk emails, scheduled task processing |
| `lms_scheduler` | Dedicated scheduler for backup, weekly report, public holiday sync, recovery |
| `postgresql` | Database |
| `nginx` | Public web server, static/media/proxy |

Check all critical services:

```bash
sudo systemctl status gunicorn
sudo systemctl status qcluster
sudo systemctl status lms_scheduler
sudo systemctl status postgresql
sudo systemctl status nginx
```

## 5. Log Commands

```bash
sudo journalctl -u gunicorn -n 120 --no-pager
sudo journalctl -u qcluster -n 120 --no-pager
sudo journalctl -u lms_scheduler -n 120 --no-pager
```

Specific time:

```bash
sudo journalctl -u lms_scheduler --since "2026-05-31 01:55:00" --no-pager
```

## 6. Backup Quick Check

```bash
ls -lh ~/Leave_Management_MST/backups | tail -20
python manage.py shell -c "from App.services.startup_checks import get_backup_catchup_status; print(get_backup_catchup_status())"
```

Tools that must exist:

```bash
which pg_dump
which psql
pg_dump --version
psql --version
```

Service PATH must include `/usr/bin`:

```bash
sudo systemctl show gunicorn -p Environment
sudo systemctl show qcluster -p Environment
sudo systemctl show lms_scheduler -p Environment
```

## 7. What To Do When A Bug Happens

1. Write down exact user action.
2. Write down exact time.
3. Check the owning service log.
4. Search the error text in `PROJECT_DEEP_DIVE_BOOK.md`.
5. Search the exact function in code with `rg`.
6. Fix code.
7. Run `python manage.py check`.
8. Run migration/collectstatic only if needed.
9. Restart the right service.
10. Verify from browser/admin/logs.

## 8. Critical Code-Backed Spot Check

This was checked against the current code while creating this start file.

| Area | Code path verified |
|---|---|
| Backup | `Leave Management/manage_backups.py` uses `pg_dump`, compresses zip, and removes incomplete raw backup on failure |
| Restore | `Leave Management/manage_backups.py` uses `psql` for PostgreSQL restore |
| Scheduler | `Leave Management/App/services/scheduler.py` schedules nightly backup, weekly report, public holiday sync, admin email job recovery, and keepalive |
| Startup checks | `Leave Management/App/services/startup_checks.py` runs missed backup/weekly/year-end checks |
| Admin bulk email jobs | `Leave Management/App/services/admin_bulk_email_jobs.py` creates `AdminEmailJob`/items, queues processing, and recovers stale running jobs |
| Background fallback | `Leave Management/App/services/background_tasks.py` uses qcluster first with thread fallback |
| Leave approve/reject | `Leave Management/App/views.py` uses `select_for_update(of=("self",))` for approval/rejection lock safety |
| Forced password | `Leave Management/App/views.py` and `templates/auth/force_password_change.html` handle forced password update flow |
| Login lock | `Leave Management/App/services/login_lock_service.py` and `App/views.py` handle wrong-password lock and admin lock/unlock |
| Admin job live status | `static/admin/js/admin_email_job_status.js` polls every 3000ms using the admin job status URL |

## 9. Deployment Rule

Do not deploy by memory.

Use this order:

```text
changed files -> required command -> service restart -> log check -> browser/admin verification
```

The detailed decision guide starts in:

```text
PROJECT_DEEP_DIVE_BOOK.md:118587
```

