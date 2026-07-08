# Production Setup Helpers

This folder contains helper scripts for generating production secrets and Web Push key files for the Leave Management MST project.

Run these scripts from the production project root:

```bash
cd ~/Leave_Management_MST
source venv/bin/activate
```

For local development from the repository root, run them from inside the Django project folder:

```bash
cd "Leave Management"
```

## What These Scripts Generate

The helper scripts can generate:

```text
DJANGO_SECRET_KEY
DB_PASSWORD
WEB_PUSH_VAPID_PUBLIC_KEY
WEB_PUSH_VAPID_PRIVATE_KEY
WEB_PUSH_VAPID_SUBJECT
```

They do not generate:

```text
EMAIL_HOST_PASSWORD
real email mailbox credentials
production domain/SSL config
PostgreSQL database/user creation
```

Email credentials must come from the email provider or hosting panel.

## Generate Everything

```bash
python App/management/production_setup/generate_all.py
```

This script prints/generates the important production secret values and asks before updating `.env` or overwriting existing Web Push key files.

Use this mainly during first production setup or controlled secret rotation.

## Individual Scripts

Generate only Django secret key:

```bash
python App/management/production_setup/generate_django_secret_key.py
```

Generate only database password:

```bash
python App/management/production_setup/generate_database_password.py
```

Generate only Web Push VAPID keys:

```bash
python App/management/production_setup/generate_webpush_keys.py
```

## Web Push Files

`generate_webpush_keys.py` creates:

```text
runtime/webpush_private_key.pem
runtime/webpush_public_key.pem
```

Production `.env` should point to the private key path:

```env
WEB_PUSH_VAPID_PUBLIC_KEY=generated-public-key
WEB_PUSH_VAPID_PRIVATE_KEY=runtime/webpush_private_key.pem
WEB_PUSH_VAPID_SUBJECT=mailto:admin@example.com
```

Keep this file secret:

```text
runtime/webpush_private_key.pem
```

Do not copy it into:

```text
static/
staticfiles/
media/
```

Do not expose it through nginx.

## Important Web Push Warning

Do not regenerate Web Push keys after users have enabled browser notifications unless you are okay with users subscribing again.

Changing VAPID keys can invalidate existing browser push subscriptions.

## Production `.env` Variables To Prepare

Core Django:

```env
DJANGO_SECRET_KEY=replace-this-with-a-long-random-production-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=mstleave.mstlabs.in
DJANGO_CSRF_TRUSTED_ORIGINS=https://mstleave.mstlabs.in
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000
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
EMAIL_HOST_PASSWORD=replace-with-real-mail-password
DEFAULT_FROM_EMAIL=leavedesk@mst-india.com
LEAVE_DESK_FROM_EMAIL=leavedesk@mst-india.com
LEAVE_RECORD_EMAILS=leave@mst-india.com
```

Security and leave rules:

```env
PASSWORD_INPUT_MAX_LENGTH=128
SHORT_HALF_LEAVE_MIN_NOTICE_MINUTES=15
SHORT_HALF_LEAVE_GRACE_MINUTES=5
SICK_LEAVE_SAME_DAY_CUTOFF_TIME=11:59
```

Background worker tuning:

```env
LMS_Q_WORKERS=2
LMS_Q_TIMEOUT=120
LMS_Q_RETRY=300
LMS_Q_QUEUE_LIMIT=100
LMS_Q_BULK=20
```

## Runtime Folders To Preserve

Production uses these project-root folders:

```text
runtime/             startup state and Web Push key files
backups/             compressed database backups
logs/                app/service/security logs
media/               uploaded files/profile photos
staticfiles/         collectstatic output
generated_pdfs/      weekly HR report PDFs
generated_reports/   report export output
```

Do not delete these during deployment unless you have a backup and a clear reason.

## After Editing `.env`

Run:

```bash
python manage.py check
```

Restart the services that use the changed values.

For web/settings changes:

```bash
sudo systemctl restart gunicorn
```

For background job settings:

```bash
sudo systemctl restart qcluster
```

For scheduler/backup/report settings:

```bash
sudo systemctl restart lms_scheduler
```

## Verification Commands

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

Web Push configured check can be done from code/service console, and production browser push also requires HTTPS and browser permission.

## Documentation Rule

If these scripts or generated env variables change, update:

```text
README.md
PROJECT_START_HERE.md
PROJECT_DEPLOYMENT_GUIDE.md
Leave Management/App/management/production_setup/README.md
```

## Safe Rotation Rules

Do not rotate secrets casually in production.

| Secret/value | If changed, what happens |
|---|---|
| `DJANGO_SECRET_KEY` | Existing sessions/password reset tokens may become invalid. Restart Gunicorn/qcluster/scheduler. |
| `DB_PASSWORD` | PostgreSQL user password and `.env` must match. Services cannot connect until both are updated. |
| `WEB_PUSH_VAPID_*` | Existing browser push subscriptions may stop working. Users may need to resubscribe. |
| `EMAIL_HOST_PASSWORD` | Email sending fails until the correct mailbox password is set. |
| `PORTAL_BASE_URL` | Email links/buttons point to the changed domain. |

## First-Time Production Secret Setup Flow

```text
1. Generate DJANGO_SECRET_KEY.
2. Generate DB_PASSWORD.
3. Create PostgreSQL user/database with that DB password.
4. Generate Web Push VAPID keys if browser push is required.
5. Get real EMAIL_HOST_PASSWORD from mail provider.
6. Fill production .env manually.
7. Run python manage.py check.
8. Start/restart services.
9. Verify login, email, backup, and push behavior.
```

## Do Not Commit These

Never commit:

```text
.env
runtime/webpush_private_key.pem
real database password
real email password
production backup files
logs with sensitive data
```

## If A Generated Value Is Changed Later

Record it in:

```text
PROJECT_DEPLOYMENT_GUIDE.md
PROJECT_START_HERE.md if daily commands/checks changed
README.md if setup instructions changed
```

Include:

```text
old behavior
new behavior
services restarted
verification command
rollback plan
```
