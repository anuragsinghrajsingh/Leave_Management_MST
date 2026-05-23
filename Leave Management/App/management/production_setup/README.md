# Production Setup Helpers

Run these scripts from the project root when preparing production secrets.

## Generate Everything

```bash
python App/management/production_setup/generate_all.py
```

This generates:

```text
DJANGO_SECRET_KEY
DB_PASSWORD
WEB_PUSH_VAPID_PUBLIC_KEY
WEB_PUSH_VAPID_PRIVATE_KEY
WEB_PUSH_VAPID_SUBJECT
```

It asks before updating `.env` and before overwriting existing values or Web Push key files.

## Individual Scripts

```bash
python App/management/production_setup/generate_django_secret_key.py
python App/management/production_setup/generate_database_password.py
python App/management/production_setup/generate_webpush_keys.py
```

## Web Push Files

`generate_webpush_keys.py` creates:

```text
runtime/webpush_private_key.pem
runtime/webpush_public_key.pem
```

Keep `runtime/webpush_private_key.pem` secret. Do not expose it through static files or share it publicly.

## Production Notes

Do not regenerate Web Push keys after users have enabled notifications unless you are okay with users enabling notifications again.

Email passwords must come from your email provider or hosting panel. These scripts do not generate `EMAIL_HOST_PASSWORD`.
