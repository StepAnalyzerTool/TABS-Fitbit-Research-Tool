from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def now_utc():
    return datetime.now(timezone.utc)


def now_eastern():
    return now_utc().astimezone(EASTERN)


def parse_google_utc(value):
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def utc_to_eastern_naive(value):
    dt = parse_google_utc(value)
    if dt is None:
        return None
    return dt.astimezone(EASTERN).replace(tzinfo=None)


def eastern_display(dt):
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=EASTERN)
    return dt.astimezone(EASTERN).strftime("%Y-%m-%d %I:%M:%S %p %Z")


def utc_storage(dt=None):
    dt = dt or now_utc()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()
