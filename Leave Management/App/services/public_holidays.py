import json
import logging
from datetime import date
from pathlib import Path

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from ics import Calendar

logger = logging.getLogger("lms_scheduler")

HOLIDAY_CACHE_KEY = "public_holidays_india"
HOLIDAY_CACHE_TIMEOUT = 60 * 60 * 24 * 30
GOOGLE_INDIA_HOLIDAY_FEED_URL = "https://calendar.google.com/calendar/ical/en.indian%23holiday%40group.v.calendar.google.com/public/basic.ics"


def _holiday_cache_file():
    runtime_dir = Path(settings.BASE_DIR) / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    return runtime_dir / "public_holidays_india.json"


def fallback_public_holidays(year):
    return [
        {
            "date": f"{year}-01-26",
            "name": "Republic Day",
            "type": "Public",
        },
        {
            "date": f"{year}-08-15",
            "name": "Independence Day",
            "type": "Public",
        },
        {
            "date": f"{year}-10-02",
            "name": "Gandhi Jayanti",
            "type": "Public",
        },
    ]


def _read_holidays_from_file(year):
    try:
        data = json.loads(_holiday_cache_file().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    except Exception:
        logger.exception("PUBLIC_HOLIDAYS | CACHE_READ_FAILED")
        return []

    if data.get("year") != year:
        return []

    holidays = data.get("holidays")
    return holidays if isinstance(holidays, list) else []


def _write_holidays_to_file(year, holidays):
    payload = {
        "year": year,
        "fetched_at": timezone.now().isoformat(),
        "holidays": holidays,
    }
    _holiday_cache_file().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _fetch_google_public_holidays(year):
    response = requests.get(GOOGLE_INDIA_HOLIDAY_FEED_URL, timeout=5)
    response.raise_for_status()

    if "BEGIN:VCALENDAR" not in response.text:
        raise ValueError("Holiday feed did not return calendar data.")

    calendar = Calendar(response.text)
    holidays = []
    for event in calendar.events:
        if event.begin.year == year:
            holiday_name = getattr(event, "name", "") or getattr(event, "summary", "") or "Public holiday"
            holidays.append({
                "date": event.begin.strftime("%Y-%m-%d"),
                "name": holiday_name,
                "type": "Public",
            })

    return sorted(holidays, key=lambda item: item["date"])


def get_public_holidays(year=None):
    year = year or date.today().year
    cached_holidays = cache.get(HOLIDAY_CACHE_KEY)
    if cached_holidays:
        return cached_holidays

    stored_holidays = _read_holidays_from_file(year)
    if stored_holidays:
        cache.set(HOLIDAY_CACHE_KEY, stored_holidays, HOLIDAY_CACHE_TIMEOUT)
        return stored_holidays

    holidays = fallback_public_holidays(year)
    cache.set(HOLIDAY_CACHE_KEY, holidays, HOLIDAY_CACHE_TIMEOUT)
    return holidays


def sync_public_holidays(year=None):
    year = year or date.today().year
    try:
        holidays = _fetch_google_public_holidays(year)
        if not holidays:
            raise ValueError(f"No public holidays returned for {year}.")

        _write_holidays_to_file(year, holidays)
        cache.set(HOLIDAY_CACHE_KEY, holidays, HOLIDAY_CACHE_TIMEOUT)
        logger.info("PUBLIC_HOLIDAYS | SYNCED | Year=%s | Count=%s", year, len(holidays))
        return True
    except Exception:
        logger.exception("PUBLIC_HOLIDAYS | SYNC_FAILED | Year=%s", year)
        return False
