import os
import django
from datetime import date
from App.models import CompanyHoliday

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "your_project.settings")
django.setup()


holidays = [
    ("Republic Day", date(2026, 1, 26)),
    ("Independence Day", date(2026, 8, 15)),
    ("Gandhi Jayanti", date(2026, 10, 2)),
]

for name, d in holidays:
    obj, created = CompanyHoliday.objects.get_or_create(date=d, defaults={"name": name})
    print(f"{'Added' if created else 'Skipped'}: {name}")