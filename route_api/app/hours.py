"""Weekly opening-hours JSON parsing and visit interval validation.

Weekday time ranges in the source refer to the day of START. A range
['22:00','02:00'] ends on the following day. Empty [] means closed.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta

DAYS = ('mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun')
TIME = re.compile(r'^([01][0-9]|2[0-4]):([0-5][0-9])$')


def minute(time: str) -> int:
    match = TIME.fullmatch(time)
    if not match:
        raise ValueError(f'Invalid HH:MM time: {time!r}')
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour == 24 and minute != 0:
        raise ValueError(f'Invalid 24-hour terminal: {time!r}')
    return hour * 60 + minute


def parse_hours(text: str | None) -> dict[str, list[list[str]]] | None:
    if not text or not str(text).strip():
        return None
    try:
        hours = json.loads(text)
    except (ValueError, TypeError) as e:
        raise ValueError('opening_hours must be valid JSON') from e
    if not isinstance(hours, dict) or set(hours) != set(DAYS):
        raise ValueError('opening_hours must have mon,tue,wed,thu,fri,sat,sun')
    for key, intervals in hours.items():
        if not isinstance(intervals, list):
            raise ValueError(f'{key} must contain time intervals')
        for interval in intervals:
            if not isinstance(interval, list) or len(interval) != 2:
                raise ValueError(f'{key} has an invalid time interval')
            start, end = map(minute, interval)
            if start == 1440 or start == end:
                raise ValueError(f'{key}: invalid interval {interval}')
            # Overnight intervals are allowed; end earlier than start means next day.
    return hours


def is_open_for(hours: dict | None, start: datetime, duration_minutes: int) -> bool:
    if hours is None:
        return True  # not yet validated: e.g. accommodation, not restaurants
    if duration_minutes <= 0:
        return False
    end = start + timedelta(minutes=duration_minutes)
    for day_delta in (-1, 0):
        day = start.date() + timedelta(days=day_delta)
        day_base = datetime.combine(day, datetime.min.time(), tzinfo=start.tzinfo)
        for lower, upper in hours[DAYS[day.weekday()]]:
            a = minute(lower)
            b = minute(upper)
            if b <= a:
                b += 1440
            open_at = day_base + timedelta(minutes=a)
            close_at = day_base + timedelta(minutes=b)
            if open_at <= start and end <= close_at:
                return True
    return False
